"""Runtime LLM provider configuration endpoints.

Lets the UI point the agent at a different model provider without editing
``.env`` or restarting. ``.env`` remains the fallback when nothing is active.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, status

from app.core.config import settings
from app.core.exceptions import AppError, LLMError, ValidationError
from app.core.logging import get_logger
from app.llm.provider_store import (
    ROUTE_PURPOSES,
    get_provider_store,
    resolve_draft,
    resolve_from_record,
    resolve_llm,
)
from app.llm.providers import IMAGE_ONLY_KINDS, PRESETS, ProviderRecord, ResolvedLLM
from app.schemas.common import OkResponse
from app.schemas.llm_config import (
    ActiveLLMView,
    EnvDefaultsView,
    LLMConfigResponse,
    LLMRoutesUpdate,
    PresetView,
    ProviderCreate,
    ProviderTestRequest,
    ProviderTestResponse,
    ProviderUpdate,
    ProviderView,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/llm", tags=["llm-config"])


def _require_enabled() -> None:
    if not settings.runtime_llm_config_enabled:
        raise ValidationError(
            "Runtime LLM configuration is disabled on this server.",
            details={"hint": "Set RUNTIME_LLM_CONFIG_ENABLED=true to allow it."},
        )


def _to_view(record: ProviderRecord, active_id: str | None) -> ProviderView:
    data = record.public_dict()
    data["is_active"] = record.id == active_id
    data["has_credentials"] = resolve_from_record(record).configured
    return ProviderView.model_validate(data)


def _active_view(cfg: ResolvedLLM) -> ActiveLLMView:
    return ActiveLLMView(
        source=cfg.source,
        kind=cfg.kind,
        label=cfg.label,
        model=cfg.model,
        provider_id=cfg.provider_id,
        base_url=cfg.base_url,
        aws_region=cfg.aws_region,
        configured=cfg.configured,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
    )


def _routes_view() -> dict[str, str | None]:
    stored = get_provider_store().routes()
    return {purpose: stored.get(purpose) for purpose in ROUTE_PURPOSES}


def _config_response() -> LLMConfigResponse:
    store = get_provider_store()
    active_id = store.active_id
    return LLMConfigResponse(
        enabled=settings.runtime_llm_config_enabled,
        active=_active_view(resolve_llm()),
        env_defaults=EnvDefaultsView(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            has_api_key=bool(settings.llm_api_key),
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        ),
        providers=[_to_view(r, active_id) for r in store.list()],
        presets=[PresetView.model_validate(p.model_dump()) for p in PRESETS],
        routes=_routes_view(),
        store_path=str(store.path),
    )


@router.get(
    "/config",
    response_model=LLMConfigResponse,
    summary="Current LLM configuration, saved providers and vendor presets",
)
async def get_llm_config() -> LLMConfigResponse:
    return _config_response()


@router.post(
    "/providers",
    response_model=LLMConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a new provider",
)
async def create_provider(payload: ProviderCreate) -> LLMConfigResponse:
    _require_enabled()
    get_provider_store().create(payload.to_input(), activate=payload.activate)
    return _config_response()


@router.put(
    "/providers/{provider_id}",
    response_model=LLMConfigResponse,
    summary="Update a provider (omitted fields keep their stored value)",
)
async def update_provider(
    provider_id: str, payload: ProviderUpdate
) -> LLMConfigResponse:
    _require_enabled()
    changes = payload.changes()
    if not changes:
        raise ValidationError("No fields to update.")
    get_provider_store().update(provider_id, changes)
    _invalidate_bedrock_clients()
    return _config_response()


@router.delete(
    "/providers/{provider_id}",
    response_model=LLMConfigResponse,
    summary="Delete a provider",
)
async def delete_provider(provider_id: str) -> LLMConfigResponse:
    _require_enabled()
    get_provider_store().delete(provider_id)
    _invalidate_bedrock_clients()
    return _config_response()


@router.post(
    "/providers/{provider_id}/activate",
    response_model=LLMConfigResponse,
    summary="Make a provider active",
)
async def activate_provider(provider_id: str) -> LLMConfigResponse:
    _require_enabled()
    get_provider_store().activate(provider_id)
    return _config_response()


@router.post(
    "/deactivate",
    response_model=LLMConfigResponse,
    summary="Drop the runtime override and fall back to .env",
)
async def deactivate_provider() -> LLMConfigResponse:
    _require_enabled()
    get_provider_store().deactivate()
    return _config_response()


@router.put(
    "/routes",
    response_model=LLMConfigResponse,
    summary="Assign saved providers to chat, skill, notes, memory, knowledge, image",
)
async def update_routes(payload: LLMRoutesUpdate) -> LLMConfigResponse:
    _require_enabled()
    changes = payload.changes()
    if not changes:
        raise ValidationError("No routes to update.")
    get_provider_store().set_routes(changes)
    return _config_response()


@router.post(
    "/test",
    response_model=ProviderTestResponse,
    summary="Send a one-token probe to verify credentials",
)
async def test_provider(payload: ProviderTestRequest) -> ProviderTestResponse:
    """Verify a provider without saving it.

    Returns HTTP 200 even when the upstream call fails: the failure detail is
    the useful part of the result, not an error condition for this endpoint.
    """
    cfg = _resolve_test_target(payload)
    started = time.perf_counter()

    if cfg.kind in IMAGE_ONLY_KINDS:
        return await _test_huggingface_image(cfg, started)

    # Imported here so patching app.llm.client in tests still affects this path.
    from app.llm.client import chat_complete
    from app.llm.usage import PURPOSE_PROBE, usage_scope

    try:
        with usage_scope(purpose=PURPOSE_PROBE):
            result = await chat_complete(
                [{"role": "user", "content": payload.prompt}],
                max_tokens=64,
                temperature=0.0,
                config=cfg,
            )
    except AppError as exc:
        logger.info(
            "llm_provider_test_failed",
            provider=cfg.label,
            kind=cfg.kind,
            code=exc.code,
        )
        return ProviderTestResponse(
            ok=False,
            label=cfg.label,
            kind=cfg.kind,
            model=cfg.model,
            source=cfg.source,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error_code=exc.code,
            error_message=exc.message,
            error_details=exc.details or None,
        )
    except Exception as exc:
        logger.warning(
            "llm_provider_test_error", provider=cfg.label, error=str(exc)[:200]
        )
        return ProviderTestResponse(
            ok=False,
            label=cfg.label,
            kind=cfg.kind,
            model=cfg.model,
            source=cfg.source,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error_code="unexpected_error",
            error_message=str(exc)[:300],
        )

    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "llm_provider_test_ok",
        provider=cfg.label,
        kind=cfg.kind,
        model=cfg.model,
        latency_ms=latency_ms,
    )
    return ProviderTestResponse(
        ok=True,
        label=cfg.label,
        kind=cfg.kind,
        model=cfg.model,
        source=cfg.source,
        latency_ms=latency_ms,
        content=(result.content or "").strip()[:300],
        total_tokens=result.usage.total_tokens or None,
    )


@router.post(
    "/bedrock/check",
    response_model=OkResponse,
    summary="Report whether the optional AWS SDK is installed",
)
async def bedrock_check() -> OkResponse:
    try:
        import boto3  # noqa: PLC0415
    except ImportError:
        return OkResponse(
            ok=False,
            message=(
                "boto3 未安装，AWS Bedrock 不可用。"
                "在 backend 目录运行：pip install -r requirements-aws.txt"
            ),
        )
    return OkResponse(ok=True, message=f"boto3 {boto3.__version__} 已安装。")


async def _test_huggingface_image(
    cfg: ResolvedLLM, started: float
) -> ProviderTestResponse:
    """Probe an HF token without running a full (paid) image generation."""
    import asyncio

    if not cfg.api_key:
        return ProviderTestResponse(
            ok=False,
            label=cfg.label,
            kind=cfg.kind,
            model=cfg.model,
            source=cfg.source,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error_code="missing_credentials",
            error_message="HF Token is required to test this provider.",
        )

    def _whoami() -> str:
        from huggingface_hub import HfApi

        info = HfApi(token=cfg.api_key).whoami()
        if isinstance(info, dict):
            return str(info.get("name") or info.get("email") or "ok")
        return "ok"

    try:
        name = await asyncio.to_thread(_whoami)
    except Exception as exc:  # noqa: BLE001
        logger.info(
            "llm_provider_test_failed",
            provider=cfg.label,
            kind=cfg.kind,
            code="hf_auth_failed",
        )
        return ProviderTestResponse(
            ok=False,
            label=cfg.label,
            kind=cfg.kind,
            model=cfg.model,
            source=cfg.source,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error_code="hf_auth_failed",
            error_message=str(exc)[:300],
        )
    return ProviderTestResponse(
        ok=True,
        label=cfg.label,
        kind=cfg.kind,
        model=cfg.model,
        source=cfg.source,
        latency_ms=int((time.perf_counter() - started) * 1000),
        content=f"HF account: {name}",
    )


def _resolve_test_target(payload: ProviderTestRequest) -> ResolvedLLM:
    if payload.draft is not None:
        return resolve_draft(payload.draft)
    if payload.provider_id:
        return resolve_from_record(get_provider_store().get(payload.provider_id))
    cfg = resolve_llm()
    if not cfg.configured and cfg.source == "env" and not settings.llm_api_key:
        raise LLMError(
            "No provider configured yet. Add one first, or fill LLM_API_KEY in .env.",
            details={"hint": "POST /api/v1/llm/providers"},
        )
    return cfg


def _invalidate_bedrock_clients() -> None:
    """Drop cached boto3 clients so credential edits take effect at once."""
    from app.llm.bedrock import clear_client_cache

    clear_client_cache()
