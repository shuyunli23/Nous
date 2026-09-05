"""Runtime web-search configuration endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter

from app.agent.search_config import (
    get_search_store,
    planned_backends,
    public_key_view,
    resolve_search,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.search_config import (
    SearchConfigResponse,
    SearchConfigUpdate,
    SearchKeyView,
    SearchTestRequest,
    SearchTestResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/search", tags=["search-config"])

_KEY_FIELDS = (
    "brave_search_api_key",
    "tavily_api_key",
    "serper_api_key",
    "deepseek_api_key",
)


def _config_response() -> SearchConfigResponse:
    store = get_search_store()
    cfg = resolve_search()
    return SearchConfigResponse(
        provider=cfg.provider,  # type: ignore[arg-type]
        provider_source=cfg.provider_source,
        env_provider=(settings.web_search_provider or "auto").strip().lower(),
        keys={
            name: SearchKeyView.model_validate(public_key_view(cfg, name))
            for name in _KEY_FIELDS
        },
        deepseek_base_url=cfg.deepseek_base_url,
        deepseek_model=cfg.deepseek_model,
        deepseek_max_uses=cfg.deepseek_max_uses,
        planned_backends=planned_backends(cfg),
        store_path=str(store.path),
    )


@router.get(
    "/config",
    response_model=SearchConfigResponse,
    summary="Current web-search provider, keys (masked) and fallback order",
)
async def get_search_config() -> SearchConfigResponse:
    return _config_response()


@router.put(
    "/config",
    response_model=SearchConfigResponse,
    summary="Save web-search settings. Omitted secrets keep their stored value.",
)
async def update_search_config(payload: SearchConfigUpdate) -> SearchConfigResponse:
    get_search_store().update(payload.changes())
    logger.info(
        "web_search_config_updated",
        fields=sorted(payload.changes().keys()),
    )
    return _config_response()


@router.post(
    "/reset",
    response_model=SearchConfigResponse,
    summary="Drop the runtime overlay so .env search settings take over again",
)
async def reset_search_config() -> SearchConfigResponse:
    get_search_store().reset()
    logger.info("web_search_config_reset")
    return _config_response()


@router.post(
    "/test",
    response_model=SearchTestResponse,
    summary="Run one web_search with the current settings",
)
async def test_search(payload: SearchTestRequest | None = None) -> SearchTestResponse:
    body = payload or SearchTestRequest()
    from app.agent.tools.web_search import run_web_search

    started = time.perf_counter()
    result = await run_web_search(query=body.query, max_results=body.max_results)
    latency_ms = int((time.perf_counter() - started) * 1000)
    rows = [
        {
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "snippet": str(item.get("snippet") or "")[:180],
        }
        for item in (result.get("results") or [])[: body.max_results]
        if isinstance(item, dict)
    ]
    return SearchTestResponse(
        ok=bool(result.get("ok")),
        query=str(result.get("query") or body.query),
        provider=result.get("provider"),
        count=int(result.get("count") or 0),
        results=rows,
        tried=list(result.get("tried") or []),
        latency_ms=latency_ms,
        error=result.get("error"),
    )
