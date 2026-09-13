"""Runtime LLM provider store.

Lets the UI switch model providers without editing ``.env`` and restarting.
Providers live in a JSON file under ``backend/data/`` (gitignored) so a chosen
provider survives a restart; ``.env`` stays the fallback when nothing is active.

The file holds credentials in cleartext because there is no key management in a
single-user local tool. It is written with owner-only permissions and never
returned to a client unmasked -- see ``ProviderRecord.public_dict``.
"""

from __future__ import annotations

import json
import os
import stat
import threading
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.llm.token_limits import effective_max_tokens
from app.llm.providers import (
    IMAGE_CAPABLE_KINDS,
    IMAGE_ONLY_KINDS,
    ProviderInput,
    ProviderRecord,
    ResolvedLLM,
    utcnow,
)

logger = get_logger(__name__)

STORE_VERSION = 1

# Background jobs and chat can each point at a saved provider. Unmapped
# purposes still follow ``active_id`` (or ``.env``).
CHAT_PURPOSES = ("chat", "skill", "notes", "memory", "knowledge")
ROUTE_PURPOSES = (*CHAT_PURPOSES, "image")


class ProviderStore:
    """Thread-safe, file-backed collection of providers plus the active choice."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._providers: dict[str, ProviderRecord] = {}
        self._active_id: str | None = None
        self._routes: dict[str, str] = {}
        self._loaded = False

    # -- persistence -------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._load()
            self._loaded = True

    def _load(self) -> None:
        if not self._path.exists():
            self._providers = {}
            self._active_id = None
            self._routes = {}
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # A corrupt file must not take the whole app down; fall back to .env.
            logger.warning("llm_provider_store_unreadable", error=str(exc))
            self._providers = {}
            self._active_id = None
            self._routes = {}
            return

        providers: dict[str, ProviderRecord] = {}
        for item in raw.get("providers") or []:
            try:
                record = ProviderRecord.model_validate(item)
            except ValueError as exc:
                logger.warning(
                    "llm_provider_record_invalid",
                    provider_id=str(item.get("id")),
                    error=str(exc),
                )
                continue
            providers[record.id] = record

        self._providers = providers
        active = raw.get("active_id")
        self._active_id = active if active in providers else None
        routes: dict[str, str] = {}
        raw_routes = raw.get("routes") or {}
        if isinstance(raw_routes, dict):
            for purpose, pid in raw_routes.items():
                if (
                    purpose in ROUTE_PURPOSES
                    and isinstance(pid, str)
                    and pid in providers
                ):
                    routes[purpose] = pid
        self._routes = routes
        logger.info(
            "llm_provider_store_loaded",
            count=len(providers),
            active_id=self._active_id,
            routes=len(routes),
        )

    def _save(self) -> None:
        payload = {
            "version": STORE_VERSION,
            "active_id": self._active_id,
            "routes": dict(self._routes),
            "providers": [p.model_dump(mode="json") for p in self._providers.values()],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a sibling temp file then replace, so a crash mid-write cannot
        # truncate an existing config.
        tmp = self._path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        try:
            os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            # Best effort: Windows ignores POSIX modes.
            pass
        os.replace(tmp, self._path)

    # -- queries -----------------------------------------------------------

    @property
    def path(self) -> Path:
        return self._path

    def list(self) -> list[ProviderRecord]:
        self._ensure_loaded()
        with self._lock:
            return sorted(self._providers.values(), key=lambda p: p.created_at)

    def get(self, provider_id: str) -> ProviderRecord:
        self._ensure_loaded()
        with self._lock:
            record = self._providers.get(provider_id)
        if record is None:
            raise NotFoundError(
                f"LLM provider {provider_id} not found.",
                details={"provider_id": provider_id},
            )
        return record

    @property
    def active_id(self) -> str | None:
        self._ensure_loaded()
        return self._active_id

    def active(self) -> ProviderRecord | None:
        self._ensure_loaded()
        with self._lock:
            if self._active_id is None:
                return None
            return self._providers.get(self._active_id)

    def routes(self) -> dict[str, str]:
        """purpose → provider_id for purposes that do not follow the default."""
        self._ensure_loaded()
        with self._lock:
            return dict(self._routes)

    def route_for(self, purpose: str) -> str | None:
        self._ensure_loaded()
        with self._lock:
            return self._routes.get(purpose)

    def set_routes(self, updates: dict[str, str | None]) -> dict[str, str]:
        """Assign or clear purpose routes. ``None`` / empty means follow default."""
        self._ensure_loaded()
        with self._lock:
            for purpose, provider_id in updates.items():
                if purpose not in ROUTE_PURPOSES:
                    raise ValidationError(
                        f"Unknown LLM purpose '{purpose}'.",
                        details={"purpose": purpose, "allowed": list(ROUTE_PURPOSES)},
                    )
                if not provider_id:
                    self._routes.pop(purpose, None)
                    continue
                record = self._providers.get(provider_id)
                if record is None:
                    raise NotFoundError(
                        f"LLM provider {provider_id} not found.",
                        details={"provider_id": provider_id},
                    )
                if purpose == "image":
                    if record.kind not in IMAGE_CAPABLE_KINDS:
                        raise ValidationError(
                            "That provider cannot generate images.",
                            details={"provider_id": provider_id, "kind": record.kind},
                        )
                elif record.kind in IMAGE_ONLY_KINDS:
                    raise ValidationError(
                        "Image-only providers cannot be used for chat. "
                        "Assign them under models by purpose → image generation.",
                        details={"provider_id": provider_id, "purpose": purpose},
                    )
                self._routes[purpose] = provider_id
            self._save()
            result = dict(self._routes)
        logger.info("llm_routes_updated", routes=result)
        return result

    # -- mutations ---------------------------------------------------------

    def create(
        self, payload: ProviderInput, *, activate: bool = False
    ) -> ProviderRecord:
        self._ensure_loaded()
        with self._lock:
            if any(p.label == payload.label for p in self._providers.values()):
                raise ConflictError(
                    f"A provider named '{payload.label}' already exists.",
                    details={"label": payload.label},
                )
            now = utcnow()
            record = ProviderRecord(
                id=uuid.uuid4().hex[:12],
                created_at=now,
                updated_at=now,
                **payload.model_dump(),
            )
            self._providers[record.id] = record
            # Image-only records must not become the chat default, even when
            # they are the first saved provider or the client asked to activate.
            if record.kind not in IMAGE_ONLY_KINDS and (
                activate or self._active_id is None
            ):
                self._active_id = record.id
            self._save()
        logger.info(
            "llm_provider_created",
            provider_id=record.id,
            kind=record.kind,
            model=record.model,
            active=self._active_id == record.id,
        )
        return record

    def update(self, provider_id: str, changes: dict[str, Any]) -> ProviderRecord:
        """Apply a partial update.

        Only keys present in ``changes`` are touched, so omitting ``api_key``
        keeps the stored credential instead of wiping it. Pass an empty string
        to clear a field explicitly.
        """
        existing = self.get(provider_id)
        with self._lock:
            merged = existing.model_dump()
            merged.update(changes)
            # Re-run field and cross-field validation on the merged result.
            validated = ProviderInput.model_validate(
                {k: v for k, v in merged.items() if k in ProviderInput.model_fields}
            )
            if any(
                p.label == validated.label and p.id != provider_id
                for p in self._providers.values()
            ):
                raise ConflictError(
                    f"A provider named '{validated.label}' already exists.",
                    details={"label": validated.label},
                )
            record = ProviderRecord(
                id=existing.id,
                created_at=existing.created_at,
                updated_at=utcnow(),
                **validated.model_dump(),
            )
            self._providers[record.id] = record
            self._save()
        logger.info("llm_provider_updated", provider_id=record.id, kind=record.kind)
        return record

    def delete(self, provider_id: str) -> None:
        self.get(provider_id)
        with self._lock:
            del self._providers[provider_id]
            if self._active_id == provider_id:
                # Falling back to .env is safer than silently picking another key.
                self._active_id = None
            stale = [key for key, value in self._routes.items() if value == provider_id]
            for key in stale:
                del self._routes[key]
            self._save()
        logger.info("llm_provider_deleted", provider_id=provider_id)

    def activate(self, provider_id: str) -> ProviderRecord:
        record = self.get(provider_id)
        if record.kind in IMAGE_ONLY_KINDS:
            raise ValidationError(
                "Image-only providers cannot be the chat default. "
                "Assign them under models by purpose → image generation.",
                details={"provider_id": provider_id, "kind": record.kind},
            )
        with self._lock:
            self._active_id = record.id
            self._save()
        logger.info(
            "llm_provider_activated", provider_id=record.id, model=record.model
        )
        return record

    def deactivate(self) -> None:
        """Drop the runtime override so ``.env`` takes over again."""
        self._ensure_loaded()
        with self._lock:
            self._active_id = None
            self._save()
        logger.info("llm_provider_deactivated")

    def reload(self) -> None:
        """Re-read the file from disk (used by tests)."""
        with self._lock:
            self._loaded = False
            self._ensure_loaded()


_store: ProviderStore | None = None
_store_lock = threading.Lock()


def get_provider_store() -> ProviderStore:
    """Process-wide store singleton."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = ProviderStore(settings.llm_provider_store_path)
    return _store


def reset_provider_store() -> None:
    """Drop the singleton so the next access re-reads settings (tests only)."""
    global _store
    with _store_lock:
        _store = None


def env_resolved() -> ResolvedLLM:
    """The configuration implied by ``.env`` alone."""
    return ResolvedLLM(
        source="env",
        kind="openai_compatible",
        model=settings.llm_model,
        # ASCII so log lines stay readable in any console encoding; the UI
        # renders its own localised name for the env source.
        label=".env defaults",
        base_url=settings.llm_base_url.rstrip("/"),
        api_key=settings.llm_api_key or None,
        temperature=settings.llm_temperature,
        max_tokens=effective_max_tokens(
            "openai_compatible", settings.llm_model, settings.llm_max_tokens
        ),
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def resolve_from_record(record: ProviderRecord) -> ResolvedLLM:
    """Build a call configuration from a stored provider."""
    return ResolvedLLM(
        source="runtime",
        provider_id=record.id,
        label=record.label,
        kind=record.kind,
        model=record.model,
        base_url=record.base_url,
        api_key=record.api_key,
        hf_provider=record.hf_provider,
        aws_region=record.aws_region,
        aws_profile_name=record.aws_profile_name,
        aws_access_key_id=record.aws_access_key_id,
        aws_secret_access_key=record.aws_secret_access_key,
        aws_session_token=record.aws_session_token,
        temperature=(
            record.temperature
            if record.temperature is not None
            else settings.llm_temperature
        ),
        max_tokens=effective_max_tokens(
            record.kind, record.model, record.max_tokens
        ),
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def resolve_llm(
    *,
    purpose: str | None = None,
    provider_id: str | None = None,
) -> ResolvedLLM:
    """LLM configuration for a call.

    Order: explicit ``provider_id`` (chat picker) → purpose route in Settings
    → the active/default provider → ``.env``.
    """
    if not settings.runtime_llm_config_enabled:
        return env_resolved()
    store = get_provider_store()
    if provider_id:
        record = store.get(provider_id)
        if record.kind in IMAGE_ONLY_KINDS and purpose != "image":
            logger.warning(
                "llm_image_provider_skipped_for_chat",
                provider_id=provider_id,
                purpose=purpose,
            )
        else:
            return resolve_from_record(record)
    if purpose in ROUTE_PURPOSES:
        routed = store.route_for(purpose)
        if routed:
            try:
                record = store.get(routed)
            except NotFoundError:
                logger.warning(
                    "llm_route_missing_provider",
                    purpose=purpose,
                    provider_id=routed,
                )
            else:
                if purpose == "image" or record.kind not in IMAGE_ONLY_KINDS:
                    return resolve_from_record(record)
    # Image generation without an explicit route follows .env IMAGE_* / HF_TOKEN,
    # not the active chat model.
    if purpose == "image":
        return env_resolved()
    record = store.active()
    if record is None or record.kind in IMAGE_ONLY_KINDS:
        return env_resolved()
    return resolve_from_record(record)


def resolve_draft(payload: ProviderInput) -> ResolvedLLM:
    """Build a throwaway configuration for "test before saving"."""
    if payload.kind == "openai_compatible" and not payload.base_url:
        raise ValidationError("base_url is required to test this provider.")
    return resolve_from_record(
        ProviderRecord(
            id="draft",
            created_at=utcnow(),
            updated_at=utcnow(),
            **payload.model_dump(),
        )
    )
