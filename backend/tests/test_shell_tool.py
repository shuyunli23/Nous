"""Tests for the confined run_command shell tool (no LLM, no network).

Covers the isolation policy (mode escalation, workspace confinement, command
denylist) plus a real foreground execution on the current platform.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from app.agent.tools import shell_sandbox as sb
from app.agent.tools.shell import run_command
from app.agent.tools.shell_config import reset_shell_store, resolve_shell
from app.core.config import settings

# Isolate the runtime overlay for the whole module: an empty (missing) file so
# every mode falls back to the settings.* the tests set directly.
_ISOLATED_STORE = Path(tempfile.gettempdir()) / "nous_test_shell_config.json"
_ISOLATED_STORE.unlink(missing_ok=True)
settings.shell_config_store = str(_ISOLATED_STORE)
reset_shell_store()


def _use_workspace(tmp: Path) -> None:
    settings.shell_workspace_dir = str(tmp)
    # Isolate the runtime overlay so a real UI toggle can't affect the test.
    settings.shell_config_store = str(tmp / "shell_config.json")
    reset_shell_store()


# ── mode escalation ────────────────────────────────────────────────────────


def test_default_mode_when_not_escalating() -> None:
    settings.shell_default_mode = "workspace-write"
    settings.shell_max_mode = "workspace-write"
    decision = sb.resolve_mode(sandbox_permissions=None, justification=None)
    assert decision.error is None
    assert decision.mode == "workspace-write"


def test_justification_without_permission_is_error() -> None:
    decision = sb.resolve_mode(sandbox_permissions=None, justification="because")
    assert decision.mode is None
    assert "only valid together" in (decision.error or "")


def test_escalation_requires_justification() -> None:
    settings.shell_default_mode = "read-only"
    settings.shell_max_mode = "workspace-write"
    decision = sb.resolve_mode(
        sandbox_permissions="workspace-write", justification=None
    )
    assert decision.mode is None
    assert "requires a justification" in (decision.error or "")


def test_escalation_up_to_ceiling_ok() -> None:
    settings.shell_default_mode = "read-only"
    settings.shell_max_mode = "workspace-write"
    decision = sb.resolve_mode(
        sandbox_permissions="workspace-write", justification="need to write output"
    )
    assert decision.error is None
    assert decision.mode == "workspace-write"


def test_escalation_beyond_ceiling_denied() -> None:
    settings.shell_default_mode = "read-only"
    settings.shell_max_mode = "workspace-write"
    decision = sb.resolve_mode(
        sandbox_permissions="danger-full-access", justification="trust me"
    )
    assert decision.mode is None
    assert "exceeds this deployment's ceiling" in (decision.error or "")


# ── command policy ─────────────────────────────────────────────────────────


def test_catastrophic_blocked_in_every_mode() -> None:
    for mode in sb.MODES:
        reason = sb.classify_command("rm -rf /", mode=mode, enforcement="strict")
        assert reason is not None, mode
    assert sb.classify_command(":(){ :|:& };:", mode="danger-full-access",
                               enforcement="advisory") is not None
    assert sb.classify_command("shutdown -h now", mode="workspace-write",
                               enforcement="advisory") is not None


def test_advisory_read_only_blocks_writes() -> None:
    assert sb.classify_command("echo hi > out.txt", mode="read-only",
                               enforcement="advisory") is not None
    assert sb.classify_command("rm file.txt", mode="read-only",
                               enforcement="advisory") is not None
    # A pure read is allowed.
    assert sb.classify_command("cat file.txt", mode="read-only",
                               enforcement="advisory") is None


def test_workspace_write_allows_writes() -> None:
    assert sb.classify_command("echo hi > out.txt", mode="workspace-write",
                               enforcement="advisory") is None


# ── workspace confinement ──────────────────────────────────────────────────


def test_workdir_inside_root_ok(tmp_path: Path) -> None:
    _use_workspace(tmp_path)
    decision = sb.resolve_workdir("sub/dir")
    assert decision.error is None
    assert decision.path is not None
    assert decision.path.resolve().is_relative_to(tmp_path.resolve())


def test_workdir_escape_denied(tmp_path: Path) -> None:
    _use_workspace(tmp_path)
    decision = sb.resolve_workdir("../../etc")
    assert decision.path is None
    assert "escapes the sandbox workspace" in (decision.error or "")


# ── real execution ─────────────────────────────────────────────────────────


def test_disabled_tool_refuses(tmp_path: Path) -> None:
    settings.shell_tool_enabled = False
    result = asyncio.run(run_command(command="echo hi"))
    assert result["ok"] is False
    assert "disabled" in result["error"].lower()


def test_execute_echo_succeeds(tmp_path: Path) -> None:
    _use_workspace(tmp_path)
    settings.shell_tool_enabled = True
    settings.shell_default_mode = "workspace-write"
    settings.shell_max_mode = "workspace-write"
    result = asyncio.run(run_command(command="echo nous_ok"))
    assert result["ok"] is True, result
    assert result["exit_code"] == 0
    assert "nous_ok" in result["stdout"]
    assert "[exit code: 0]" in result["text"]
    # cwd was confined to the workspace root.
    assert Path(result["workdir"]).resolve().is_relative_to(tmp_path.resolve())


def test_execute_nonzero_exit(tmp_path: Path) -> None:
    _use_workspace(tmp_path)
    settings.shell_tool_enabled = True
    settings.shell_default_mode = "workspace-write"
    result = asyncio.run(run_command(command="exit 3"))
    assert result["ok"] is False
    assert result["exit_code"] == 3
    assert "[exit code: 3]" in result["text"]


def test_runtime_overlay_overrides_env_enable(tmp_path: Path) -> None:
    _use_workspace(tmp_path)
    settings.shell_tool_enabled = False  # .env says off
    from app.agent.tools.shell_config import get_shell_store

    # UI turns it on at runtime.
    get_shell_store().update({"enabled": True})
    cfg = resolve_shell()
    assert cfg.enabled is True
    assert cfg.enabled_source == "runtime"
    # And the tool actually runs despite the .env default being off.
    result = asyncio.run(run_command(command="echo via_ui"))
    assert result["ok"] is True
    reset_shell_store()


def test_runtime_default_mode_cannot_exceed_ceiling(tmp_path: Path) -> None:
    _use_workspace(tmp_path)
    settings.shell_max_mode = "workspace-write"
    from app.agent.tools.shell_config import get_shell_store
    from app.core.exceptions import ValidationError

    try:
        get_shell_store().update({"default_mode": "danger-full-access"})
        raise AssertionError("expected ValidationError")
    except ValidationError:
        pass
    reset_shell_store()


def test_bash_chain_detection_ignores_quoted_operators() -> None:
    assert sb.has_bash_chain("cd agi-brief && python stats.py") is True
    assert sb.has_bash_chain("test -f a || echo missing") is True
    # Operators inside a quoted argument are data, not shell syntax.
    assert sb.has_bash_chain("python -c \"print('a && b')\"") is False
    assert sb.has_bash_chain("echo hello") is False


def test_windows_bash_chains_avoid_powershell_5() -> None:
    import os
    import shutil

    if os.name != "nt":
        return
    argv, name = sb.build_shell_argv("cd agi-brief && python stats.py")
    if shutil.which("pwsh"):
        # pwsh 7 understands the chain, so keep the UTF-8 preamble.
        assert name == "pwsh"
        assert argv[-1].startswith(sb._PS_UTF8_PREAMBLE)
    else:
        assert name == "cmd"
        assert argv[:3] == ["cmd.exe", "/d", "/s"]
    argv2, name2 = sb.build_shell_argv("echo hello")
    assert name2 in {"powershell", "pwsh", "cmd"}
    if name2 != "cmd":
        assert argv2[-1].startswith(sb._PS_UTF8_PREAMBLE)
        assert argv2[-1].endswith("echo hello")


def test_execute_blocked_command_does_not_run(tmp_path: Path) -> None:
    _use_workspace(tmp_path)
    settings.shell_tool_enabled = True
    result = asyncio.run(run_command(command="rm -rf /"))
    assert result["ok"] is False
    assert result.get("denied")
    assert result["exit_code"] is None
    assert "blocked by sandbox" in result["text"]


if __name__ == "__main__":
    import tempfile

    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            if "tmp_path" in fn.__code__.co_varnames[: fn.__code__.co_argcount]:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            print(f"ok   {name}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {name}: {exc}")
    raise SystemExit(1 if failures else 0)
