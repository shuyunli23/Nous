"""Runtime web-search configuration.

Lets the Settings page pick a search backend and store API keys without
editing ``.env``. Empty runtime fields fall back to environment defaults.
DeepSeek official search is opt-in: ``auto`` never bills a model turn.
"""

from __future__ import annotations

import json
import os
import stat
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.llm.providers import mask_secret

logger = get_logger(__name__)

STORE_VERSION = 1

PROVIDERS = (
    "auto",
    "brave",
    "tavily",
    "serper",
    "deepseek",
    "ddgs",
    "ddg_html",
)

SECRET_FIELDS = (
    "brave_search_api_key",
    "tavily_api_key",
    "serper_api_key",
    "deepseek_api_key",
)

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com/anthropic/v1"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_DEEPSEEK_API_VERSION = "2023-06-01"

KeySource = Literal["runtime", "env", "llm", "unset"]
ProviderSource = Literal["runtime", "env"]


@dataclass(frozen=True)
class ResolvedSearch:
    """Effective search settings after merging the UI store and ``.env``."""

    provider: str
    provider_source: ProviderSource
    brave_search_api_key: str = ""
    tavily_api_key: str = ""
    serper_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    deepseek_model: str = DEFAULT_DEEPSEEK_MODEL
    deepseek_max_tokens: int = 4096
    deepseek_max_uses: int = 2
    deepseek_api_version: str = DEFAULT_DEEPSEEK_API_VERSION
    timeout_seconds: float = 15.0
    deepseek_timeout_seconds: float = 90.0
    ddgs_backends: str = "bing,duckduckgo,brave"
    key_sources: dict[str, KeySource] = field(default_factory=dict)

    def key(self, name: str) -> str:
        return str(getattr(self, name, "") or "").strip()


class SearchConfigStore:
    """Thread-safe JSON overlay for search settings."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self._loaded = False

    @property
    def path(self) -> Path:
        return self._path

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
            self._data = {}
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("web_search_store_unreadable", error=str(exc))
            self._data = {}
            return
        if not isinstance(raw, dict):
            self._data = {}
            return
        self._data = {k: v for k, v in raw.items() if k != "version"}
        logger.info("web_search_store_loaded", path=str(self._path))

    def _save(self) -> None:
        payload = {"version": STORE_VERSION, **self._data}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        try:
            os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        os.replace(tmp, self._path)

    def snapshot(self) -> dict[str, Any]:
        self._ensure_loaded()
        with self._lock:
            return dict(self._data)

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Apply a partial update. ``None`` / blank string clears an override."""
        self._ensure_loaded()
        with self._lock:
            if "provider" in changes:
                provider = _normalize_provider(changes["provider"])
                if provider is None:
                    self._data.pop("provider", None)
                else:
                    self._data["provider"] = provider

            for name in SECRET_FIELDS:
                if name not in changes:
                    continue
                value = changes[name]
                if value is None or (isinstance(value, str) and not value.strip()):
                    self._data.pop(name, None)
                else:
                    self._data[name] = str(value).strip()

            for name in ("deepseek_base_url", "deepseek_model"):
                if name not in changes:
                    continue
                value = changes[name]
                if value is None or (isinstance(value, str) and not value.strip()):
                    self._data.pop(name, None)
                else:
                    self._data[name] = str(value).strip()

            if "deepseek_max_uses" in changes:
                raw_uses = changes["deepseek_max_uses"]
                if raw_uses is None:
                    self._data.pop("deepseek_max_uses", None)
                else:
                    uses = int(raw_uses)
                    if uses < 1 or uses > 5:
                        raise ValidationError(
                            "deepseek_max_uses must be between 1 and 5.",
                            details={"deepseek_max_uses": uses},
                        )
                    self._data["deepseek_max_uses"] = uses

            self._save()
            return dict(self._data)

    def reset(self) -> None:
        self._ensure_loaded()
        with self._lock:
            self._data = {}
            if self._path.exists():
                try:
                    self._path.unlink()
                except OSError as exc:
                    logger.warning("web_search_store_reset_failed", error=str(exc))
                    self._save()


_store: SearchConfigStore | None = None
_store_lock = threading.Lock()


def get_search_store() -> SearchConfigStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = SearchConfigStore(settings.web_search_store_path)
    return _store


def reset_search_store() -> None:
    """Drop the singleton so the next access re-reads the path (tests only)."""
    global _store
    with _store_lock:
        _store = None


def _normalize_provider(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text not in PROVIDERS:
        raise ValidationError(
            f"Unknown web search provider '{text}'.",
            details={"provider": text, "allowed": list(PROVIDERS)},
        )
    return text


def _looks_like_deepseek(base_url: str | None) -> bool:
    return "deepseek.com" in (base_url or "").lower()


def _deepseek_chat_key() -> str:
    """Reuse the chat DeepSeek key when the active chat endpoint is DeepSeek."""
    try:
        from app.llm.provider_store import resolve_llm

        cfg = resolve_llm(purpose="chat")
        key = (cfg.api_key or "").strip()
        if key and _looks_like_deepseek(cfg.base_url):
            return key
    except Exception:  # noqa: BLE001
        pass
    if _looks_like_deepseek(settings.llm_base_url):
        return (settings.llm_api_key or "").strip()
    return ""


def _pick_secret(
    runtime: dict[str, Any],
    field: str,
    env_value: str,
    *,
    extra: str = "",
    extra_fn=None,
    extra_source: KeySource = "llm",
) -> tuple[str, KeySource]:
    runtime_value = str(runtime.get(field) or "").strip()
    if runtime_value:
        return runtime_value, "runtime"
    env = (env_value or "").strip()
    if env:
        return env, "env"
    extra_value = extra
    if extra_fn is not None:
        extra_value = extra_fn()
    extra_value = (extra_value or "").strip()
    if extra_value:
        return extra_value, extra_source
    return "", "unset"


def resolve_search(runtime: dict[str, Any] | None = None) -> ResolvedSearch:
    """Merge the UI overlay with ``.env`` defaults."""
    overlay = runtime if runtime is not None else get_search_store().snapshot()
    env_provider = (settings.web_search_provider or "auto").strip().lower()
    if env_provider not in PROVIDERS:
        env_provider = "auto"
    runtime_provider = str(overlay.get("provider") or "").strip().lower()
    if runtime_provider in PROVIDERS:
        provider, provider_source = runtime_provider, "runtime"
    else:
        provider, provider_source = env_provider, "env"

    brave, brave_src = _pick_secret(
        overlay, "brave_search_api_key", settings.brave_search_api_key
    )
    tavily, tavily_src = _pick_secret(
        overlay, "tavily_api_key", settings.tavily_api_key
    )
    serper, serper_src = _pick_secret(
        overlay, "serper_api_key", settings.serper_api_key
    )
    deepseek, deepseek_src = _pick_secret(
        overlay,
        "deepseek_api_key",
        settings.deepseek_search_api_key,
        extra_fn=_deepseek_chat_key,
        extra_source="llm",
    )

    base = str(overlay.get("deepseek_base_url") or "").strip() or (
        settings.deepseek_search_base_url or DEFAULT_DEEPSEEK_BASE_URL
    )
    model = str(overlay.get("deepseek_model") or "").strip() or (
        settings.deepseek_search_model or DEFAULT_DEEPSEEK_MODEL
    )
    uses = overlay.get("deepseek_max_uses")
    if uses is None:
        uses = settings.deepseek_search_max_uses
    try:
        max_uses = max(1, min(int(uses), 5))
    except (TypeError, ValueError):
        max_uses = 2

    return ResolvedSearch(
        provider=provider,
        provider_source=provider_source,
        brave_search_api_key=brave,
        tavily_api_key=tavily,
        serper_api_key=serper,
        deepseek_api_key=deepseek,
        deepseek_base_url=base.rstrip("/"),
        deepseek_model=model,
        deepseek_max_tokens=max(256, int(settings.deepseek_search_max_tokens or 4096)),
        deepseek_max_uses=max_uses,
        timeout_seconds=float(settings.web_search_timeout_seconds or 15),
        deepseek_timeout_seconds=float(settings.deepseek_search_timeout_seconds or 90),
        ddgs_backends=settings.web_search_ddgs_backends or "bing,duckduckgo,brave",
        key_sources={
            "brave_search_api_key": brave_src,
            "tavily_api_key": tavily_src,
            "serper_api_key": serper_src,
            "deepseek_api_key": deepseek_src,
        },
    )


def planned_backends(cfg: ResolvedSearch | None = None) -> list[str]:
    """Backend names ``run_web_search`` will try, in order."""
    resolved = cfg or resolve_search()
    provider = resolved.provider
    paid: list[str] = []
    if resolved.brave_search_api_key:
        paid.append("brave")
    if resolved.tavily_api_key:
        paid.append("tavily")
    if resolved.serper_api_key:
        paid.append("serper")

    if provider == "brave":
        return ["brave"]
    if provider == "tavily":
        return ["tavily"]
    if provider == "serper":
        return ["serper"]
    if provider == "deepseek":
        return ["deepseek"]
    if provider == "ddgs":
        return ["ddg_html", "ddgs"]
    if provider == "ddg_html":
        return ["ddg_html"]
    # auto: paid search APIs, then free. DeepSeek is never auto-selected.
    return [*paid, "ddg_html", "ddgs"]


def public_key_view(cfg: ResolvedSearch, field: str) -> dict[str, Any]:
    value = cfg.key(field)
    source = cfg.key_sources.get(field, "unset")
    return {
        "configured": bool(value),
        "source": source if value else "unset",
        "masked": mask_secret(value) if value else None,
    }
