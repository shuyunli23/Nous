"""Runtime shell-tool configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.agent.tools.shell_config import get_shell_store, resolve_shell
from app.agent.tools.shell_sandbox import MODES
from app.core.logging import get_logger
from app.schemas.shell_config import ShellConfigResponse, ShellConfigUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/shell", tags=["shell-config"])


def _config_response() -> ShellConfigResponse:
    store = get_shell_store()
    cfg = resolve_shell()
    return ShellConfigResponse(
        enabled=cfg.enabled,
        enabled_source=cfg.enabled_source,
        default_mode=cfg.default_mode,  # type: ignore[arg-type]
        default_mode_source=cfg.default_mode_source,
        max_mode=cfg.max_mode,  # type: ignore[arg-type]
        modes=[m for m in MODES],  # type: ignore[misc]
        workspace_path=cfg.workspace_path,
        os_sandbox=cfg.os_sandbox,
        enforcement=cfg.enforcement,  # type: ignore[arg-type]
        backend=cfg.backend,
        network=cfg.network,
        store_path=str(store.path),
    )


@router.get(
    "/config",
    response_model=ShellConfigResponse,
    summary="Current shell-tool enablement, standing mode and sandbox facts",
)
async def get_shell_config() -> ShellConfigResponse:
    return _config_response()


@router.put(
    "/config",
    response_model=ShellConfigResponse,
    summary="Enable/disable the shell tool and set its standing sandbox mode",
)
async def update_shell_config(payload: ShellConfigUpdate) -> ShellConfigResponse:
    changes = payload.changes()
    get_shell_store().update(changes)
    logger.info("shell_config_updated", fields=sorted(changes.keys()))
    return _config_response()


@router.post(
    "/reset",
    response_model=ShellConfigResponse,
    summary="Drop the runtime overlay so .env shell settings take over again",
)
async def reset_shell_config() -> ShellConfigResponse:
    get_shell_store().reset()
    logger.info("shell_config_reset")
    return _config_response()
