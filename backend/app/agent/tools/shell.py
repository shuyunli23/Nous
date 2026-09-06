"""Model-facing ``run_command`` tool (Harness ``tool-bash`` shape).

Foreground command execution behind the sandbox seam in
:mod:`app.agent.tools.shell_sandbox`. Stateless per call: no shell state
persists between invocations, so the model passes ``workdir`` rather than
``cd``-ing around.
"""

from __future__ import annotations

from typing import Any

from app.agent.tools import shell_sandbox as sb
from app.core.logging import get_logger

logger = get_logger(__name__)


def shell_enabled() -> bool:
    from app.agent.tools.shell_config import resolve_shell

    return resolve_shell().enabled


async def run_command(
    *,
    command: str | None = None,
    description: str | None = None,
    workdir: str | None = None,
    timeout_ms: int | None = None,
    sandbox_permissions: str | None = None,
    justification: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    if not shell_enabled():
        return {
            "ok": False,
            "error": (
                "The run_command tool is disabled. An operator must set "
                "SHELL_TOOL_ENABLED=true to allow command execution."
            ),
        }

    # Tolerate common alias spellings from models.
    command = command or extra.get("cmd") or extra.get("script")
    if not command or not str(command).strip():
        return {"ok": False, "error": "invalid command: expected a non-empty string"}
    command = str(command)

    if timeout_ms is None:
        alias = extra.get("timeoutMs") or extra.get("timeout_ms") or extra.get("timeout")
        if alias is not None:
            try:
                timeout_ms = int(alias)
            except (TypeError, ValueError):
                return {"ok": False, "error": "invalid timeout_ms: expected a number"}
    sandbox_permissions = sandbox_permissions or extra.get("sandboxPermissions")
    workdir = workdir or extra.get("cwd")

    if extra.get("run_in_background") or extra.get("runInBackground"):
        return {
            "ok": False,
            "error": (
                "background execution is not supported yet; run the command in "
                "the foreground with an appropriate timeout_ms"
            ),
        }

    decision = sb.resolve_mode(
        sandbox_permissions=sandbox_permissions, justification=justification
    )
    if decision.error or decision.mode is None:
        return {"ok": False, "error": f"invalid escalation: {decision.error}"}

    wd = sb.resolve_workdir(workdir)
    if wd.error or wd.path is None:
        return {"ok": False, "error": wd.error}

    logger.info(
        "run_command_invoke",
        description=(description or "")[:120],
        mode=decision.mode,
        has_workdir=bool(workdir),
    )

    result = await sb.execute(
        command=command,
        mode=decision.mode,
        workdir=wd.path,
        timeout_ms=timeout_ms,
    )
    payload = result.to_dict()
    if description:
        payload["description"] = str(description)[:200]
    payload["message"] = payload.get("text")
    return payload
