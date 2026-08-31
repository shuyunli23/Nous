"""Sandboxed execution of nous-pack/2 Python tools.

Protocol: JSON on stdin → JSON on stdout. Auto-run after install grant;
every invocation is audited via structlog (no per-call UI confirm in v2.0).

On Windows, uvicorn often runs a loop that does not support
``asyncio.create_subprocess_exec`` (raises ``NotImplementedError``). We therefore
run ``subprocess.run`` in a worker thread via ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from app.core.config import BACKEND_ROOT, settings
from app.core.logging import get_logger
from app.database.models import SkillPack, SkillPackTool

logger = get_logger(__name__)


def _safe_env(allow: list[str], *, network: bool) -> dict[str, str]:
    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "SystemRoot": os.environ.get("SystemRoot", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
        "NOUS_BACKEND_ROOT": str(BACKEND_ROOT),
    }
    # Strip proxy vars unless network is granted
    if network:
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy"):
            if key in os.environ:
                env[key] = os.environ[key]
    for name in allow:
        if name in os.environ:
            env[name] = os.environ[name]
    # Drop empty Windows-only keys on non-Windows
    return {k: v for k, v in env.items() if v}


def _run_script_sync(
    *,
    executable: str,
    script_path: str,
    cwd: str,
    env: dict[str, str],
    stdin_data: bytes,
    timeout: int,
    stdout_cap: int,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [executable, script_path],
        input=stdin_data,
        capture_output=True,
        cwd=cwd,
        env=env,
        timeout=timeout,
        check=False,
    )


async def execute_pack_tool(
    *,
    pack: SkillPack,
    tool: SkillPackTool,
    arguments: dict[str, Any],
    request_id: str | None = None,
) -> dict[str, Any]:
    """Run a pack-local Python tool and return a JSON-serialisable result."""
    if pack.status != "active" or not tool.enabled:
        return {"ok": False, "error": "Pack tool is disabled or pack is not active."}

    granted = set(pack.permissions or [])
    if "script.python" not in granted:
        return {"ok": False, "error": "Missing granted permission: script.python"}

    runner = tool.runner or {}
    if runner.get("kind") != "python":
        return {"ok": False, "error": f"Unsupported runner kind: {runner.get('kind')}"}

    needs_network = bool(runner.get("network"))
    if needs_network and "network" not in granted:
        return {"ok": False, "error": "Tool requires network but permission was not granted."}

    pack_dir = settings.resolve_path(pack.install_path)
    skill_rel = (tool.skill_key or ".").strip() or "."
    skill_dir = pack_dir if skill_rel in (".", "") else (pack_dir / skill_rel)
    skill_dir = skill_dir.resolve()
    try:
        skill_dir.relative_to(pack_dir.resolve())
    except ValueError:
        return {"ok": False, "error": "Skill directory escapes pack."}

    entry = str(runner.get("entry") or "")
    script_path = (skill_dir / entry).resolve()
    try:
        script_path.relative_to(pack_dir.resolve())
    except ValueError:
        return {"ok": False, "error": "Script path escapes pack directory."}
    if not script_path.is_file():
        return {"ok": False, "error": f"Script not found: {entry}"}

    exports_dir = settings.resolve_path("./data/exports")
    exports_dir.mkdir(parents=True, exist_ok=True)

    timeout = min(
        int(runner.get("timeout_sec") or 60),
        settings.skill_pack_tool_timeout_cap_sec,
    )
    env_allow = list(runner.get("env_allow") or [])
    for perm in granted:
        if perm.startswith("env."):
            env_allow.append(perm[4:])

    pythonpath_extra: list[str] = []
    for rel in runner.get("pythonpath") or []:
        p = (skill_dir / rel).resolve()
        try:
            p.relative_to(pack_dir.resolve())
            pythonpath_extra.append(str(p))
        except ValueError:
            continue
    shared_lib = pack_dir / "shared" / "lib"
    if shared_lib.is_dir():
        pythonpath_extra.append(str(shared_lib.resolve()))

    env = _safe_env(env_allow, network=needs_network and "network" in granted)
    # Always expose the backend package to pack scripts (shared helpers / image_gen).
    path_parts = [str(BACKEND_ROOT)]
    if pythonpath_extra:
        path_parts.extend(pythonpath_extra)
    existing = env.get("PYTHONPATH")
    if existing:
        path_parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(path_parts)
    env["NOUS_BACKEND_ROOT"] = str(BACKEND_ROOT)

    payload = {
        **arguments,
        "_nous": {
            "pack_id": pack.pack_id,
            "pack_version": pack.version,
            "pack_row_id": pack.id,
            "tool_name": tool.name,
            "exposed_name": tool.exposed_name,
            "pack_dir": str(pack_dir),
            "skill_dir": str(skill_dir),
            "exports_dir": str(exports_dir),
            "request_id": request_id,
        },
    }

    started = time.perf_counter()
    stdout = b""
    stderr = b""
    returncode = -1

    with tempfile.TemporaryDirectory(prefix="nous-tool-") as tmp:
        workdir = Path(tmp)
        payload["_nous"]["workdir"] = str(workdir)
        stdin_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        stdout_cap = settings.skill_pack_tool_stdout_cap_bytes

        try:
            completed = await asyncio.to_thread(
                _run_script_sync,
                executable=sys.executable,
                script_path=str(script_path),
                cwd=str(skill_dir),
                env=env,
                stdin_data=stdin_data,
                timeout=timeout,
                stdout_cap=stdout_cap,
            )
            stdout = completed.stdout or b""
            stderr = completed.stderr or b""
            returncode = int(completed.returncode)
        except subprocess.TimeoutExpired:
            logger.warning(
                "pack_tool_timeout",
                tool=tool.exposed_name,
                pack_id=pack.pack_id,
                timeout=timeout,
            )
            return {"ok": False, "error": f"Tool timed out after {timeout}s"}
        except Exception as exc:  # noqa: BLE001
            logger.exception("pack_tool_spawn_failed", tool=tool.exposed_name)
            return {"ok": False, "error": f"Failed to start tool: {exc}"}

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    stdout_text = stdout[: settings.skill_pack_tool_stdout_cap_bytes].decode(
        "utf-8", errors="replace"
    )
    stderr_text = stderr[: 4000].decode("utf-8", errors="replace")

    logger.info(
        "pack_tool_audit",
        tool=tool.exposed_name,
        pack_id=pack.pack_id,
        exit_code=returncode,
        duration_ms=duration_ms,
        stdout_bytes=len(stdout),
        stderr_bytes=len(stderr),
        request_id=request_id,
    )

    if not stdout_text.strip():
        return {
            "ok": False,
            "error": "Tool produced empty stdout",
            "exit_code": returncode,
            "stderr": stderr_text,
        }

    try:
        result = json.loads(stdout_text)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": "invalid tool stdout (expected JSON)",
            "raw": stdout_text[:2000],
            "stderr": stderr_text,
            "exit_code": returncode,
        }

    if not isinstance(result, dict):
        return {"ok": True, "result": result, "exit_code": returncode}
    if "ok" not in result:
        result = {"ok": True, **result}
    if returncode not in (0,) and result.get("ok") is True:
        result.setdefault("exit_code", returncode)
    if stderr_text and not result.get("ok"):
        result.setdefault("stderr", stderr_text)
    return result
