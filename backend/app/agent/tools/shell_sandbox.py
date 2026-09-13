"""Isolation policy + executor for the model-facing shell tool.

Ported concepts from DeepSeek Harness ``sandbox/`` + ``shell/``:

- **SandboxMode vocabulary** (fail-safe order): ``read-only`` < ``workspace-write``
  < ``danger-full-access``. Default is the safest usable mode.
- **A single durable workspace root.** Every command runs with its cwd confined
  inside that root; ``cd`` does not persist between calls — the model passes
  ``workdir`` instead (the executor is stateless per call, exactly like Harness's
  ``bash`` tool).
- **Per-call escalation** (``sandbox_permissions`` + ``justification``), capped by
  an operator-controlled ceiling (``settings.shell_max_mode``). Nous has no
  interactive approval prompt, so the ceiling *is* the consent gate:
  ``danger-full-access`` is only reachable when an operator raises the ceiling.

Enforcement is defense-in-depth and honest about platform limits:

1. **Feature gate** (``settings.shell_tool_enabled``) — off by default.
2. **Workspace confinement** — cwd + ``workdir`` are resolved and kept under the
   root; traversal outside is refused before anything spawns.
3. **Command policy** — an always-on *catastrophic* denylist (rm -rf /, fork
   bombs, disk wipes, shutdown, …) applied in every mode, plus a *mutating*
   denylist enforced when ``read-only`` is only advisory.
4. **OS sandbox wrapper** (best-effort) — bubblewrap on Linux / ``sandbox-exec``
   on macOS give kernel-level filesystem confinement when present. When no
   backend exists (e.g. Windows) confinement degrades to cwd + denylist and the
   result reports ``enforcement="advisory"`` so nobody is misled.
5. **Scrubbed environment, timeout, and output caps** — the child inherits a
   minimal allowlisted env (no ambient credentials), a bounded runtime, and
   bounded output.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Fail-safe ordering; index is the "width" used for widening checks.
MODES: tuple[str, ...] = ("read-only", "workspace-write", "danger-full-access")
_RANK = {mode: i for i, mode in enumerate(MODES)}


def mode_rank(mode: str) -> int:
    return _RANK.get(mode, 0)


# ── Command policy ─────────────────────────────────────────────────────────
# Heuristic guards, NOT a complete security boundary. They stop the common
# foot-guns cheaply; real filesystem confinement comes from the OS backend
# (bubblewrap / sandbox-exec) when available.

# Blocked in EVERY mode, including danger-full-access.
_CATASTROPHIC: tuple[re.Pattern[str], ...] = (
    # rm -rf targeting a filesystem root / home / everything
    re.compile(r"\brm\b[^\n|;&]*\s-[a-zA-Z]*[rR][a-zA-Z]*[fF]|"
               r"\brm\b[^\n|;&]*\s-[a-zA-Z]*[fF][a-zA-Z]*[rR]", re.I),
    # classic fork bomb  :(){ :|:& };:
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),
    # writing raw block devices / making filesystems
    re.compile(r"\bmkfs\b|\bdd\b[^\n]*\bof=/dev/|>\s*/dev/(sd|nvme|hd|disk)", re.I),
    re.compile(r"\b(fdisk|parted|wipefs|blkdiscard|shred)\b", re.I),
    # power state
    re.compile(r"\b(shutdown|reboot|halt|poweroff|init\s+0|init\s+6)\b", re.I),
    # Windows destructive
    re.compile(r"\bformat\b[^\n]*[a-zA-Z]:|\bdel\b[^\n]*/[sS]\b[^\n]*[a-zA-Z]:\\?\s*$", re.I),
    re.compile(r"\b(Format-Volume|Clear-Disk|Remove-Item)\b[^\n]*-Recurse[^\n]*"
               r"[a-zA-Z]:\\?(\s|$)", re.I),
    re.compile(r"\brd\b[^\n]*/[sS]\b[^\n]*[a-zA-Z]:\\?", re.I),
    # recursive permission/ownership nukes from a root
    re.compile(r"\bchmod\b[^\n]*-R[^\n]*\s0*00\s+/|\bchown\b[^\n]*-R[^\n]*\s+/(\s|$)", re.I),
)

# Additionally blocked when read-only cannot be kernel-enforced (advisory).
# Keeps advisory read-only meaningfully "read-only-ish".
_MUTATING_HEADS: tuple[str, ...] = (
    "rm", "rmdir", "mv", "move", "cp", "copy", "dd", "tee", "truncate",
    "chmod", "chown", "chgrp", "mkdir", "md", "touch", "ln", "rename", "ren",
    "del", "erase", "shred", "install",
    "New-Item", "Remove-Item", "Set-Content", "Add-Content", "Out-File",
)
_REDIRECT_WRITE = re.compile(r"(?<![0-9>])>>?(?!\s*/dev/null|\s*\$null)", re.I)


def _first_word(command: str) -> str:
    stripped = command.strip().lstrip("(")
    match = re.match(r"[\"']?([\w./\\-]+)", stripped)
    return match.group(1) if match else ""


def classify_command(command: str, *, mode: str, enforcement: str) -> str | None:
    """Return a denial reason, or ``None`` if the command may run in ``mode``."""
    text = command.strip()
    if not text:
        return "empty command"
    for pattern in _CATASTROPHIC:
        if pattern.search(text):
            return (
                "matches a catastrophic-command guard (disk/root wipe, fork bomb, "
                "or power-state change) that is refused in every sandbox mode"
            )
    if mode == "read-only" and enforcement == "advisory":
        if _REDIRECT_WRITE.search(text):
            return (
                "output redirection (> / >>) is blocked under advisory read-only "
                "mode; escalate to workspace-write to write files"
            )
        # Inspect each simple segment's leading command word.
        for segment in re.split(r"[|;&\n]+", text):
            head = _first_word(segment)
            base = head.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            if base and any(base.lower() == h.lower() for h in _MUTATING_HEADS):
                return (
                    f"'{base}' can modify files and is blocked under advisory "
                    "read-only mode; escalate to workspace-write"
                )
    return None


# ── Escalation / mode resolution ───────────────────────────────────────────


@dataclass(frozen=True)
class ModeDecision:
    mode: str | None
    error: str | None = None


def resolve_mode(
    *,
    sandbox_permissions: str | None,
    justification: str | None,
) -> ModeDecision:
    """Resolve the effective per-call mode, honoring the escalation contract."""
    # Import here to avoid a module import cycle (shell_config imports us).
    from app.agent.tools.shell_config import resolve_shell

    resolved = resolve_shell()
    default_mode = resolved.default_mode
    ceiling = resolved.max_mode

    requested = (sandbox_permissions or "").strip() or None
    just = (justification or "").strip() or None

    if requested is None and just is not None:
        return ModeDecision(None, "justification is only valid together with "
                                  "sandbox_permissions")
    if requested is None:
        return ModeDecision(default_mode)

    if requested not in MODES:
        return ModeDecision(
            None, f"unknown sandbox_permissions '{requested}'; expected one of "
                  + ", ".join(MODES),
        )
    if just is None:
        return ModeDecision(None, "sandbox_permissions requires a justification")
    if mode_rank(requested) <= mode_rank(default_mode):
        # Not actually widening; just run at the standing default.
        return ModeDecision(default_mode)
    if mode_rank(requested) > mode_rank(ceiling):
        return ModeDecision(
            None,
            f"sandbox escalation to '{requested}' exceeds this deployment's "
            f"ceiling '{ceiling}' (raise settings.shell_max_mode to allow it)",
        )
    return ModeDecision(requested)


# ── Workspace confinement ──────────────────────────────────────────────────


def workspace_root() -> Path:
    root = settings.shell_workspace_path
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass(frozen=True)
class WorkdirDecision:
    path: Path | None
    error: str | None = None


def resolve_workdir(workdir: str | None) -> WorkdirDecision:
    root = workspace_root()
    if not workdir or not str(workdir).strip():
        return WorkdirDecision(root)
    raw = Path(str(workdir).strip())
    candidate = raw if raw.is_absolute() else (root / raw)
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError) as exc:
        return WorkdirDecision(None, f"invalid workdir: {exc}")
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        return WorkdirDecision(
            None,
            "workdir escapes the sandbox workspace root; pass a path inside "
            f"{root_resolved}",
        )
    resolved.mkdir(parents=True, exist_ok=True)
    return WorkdirDecision(resolved)


# ── OS sandbox backend detection (best-effort, kernel-level when present) ───


def detect_os_sandbox() -> str | None:
    """Return an available kernel sandbox backend name, or ``None``."""
    if settings.shell_os_sandbox == "off":
        return None
    if sys.platform.startswith("linux") and shutil.which("bwrap"):
        return "bwrap"
    if sys.platform == "darwin" and shutil.which("sandbox-exec"):
        return "sandbox-exec"
    return None


def _wrap_with_sandbox(
    argv: list[str], *, backend: str, mode: str, workspace: Path, network: bool
) -> list[str]:
    """Wrap the shell argv with a kernel confinement backend.

    Conservative bind sets: the whole filesystem is read-only; the workspace
    (and platform temp) become writable only under ``workspace-write`` /
    ``danger-full-access``.
    """
    if backend == "bwrap":
        wrap = ["bwrap", "--die-with-parent", "--ro-bind", "/", "/",
                "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp",
                "--chdir", str(workspace)]
        if mode in ("workspace-write", "danger-full-access"):
            wrap += ["--bind", str(workspace), str(workspace)]
        if not network and mode != "danger-full-access":
            wrap += ["--unshare-net"]
        return wrap + argv
    if backend == "sandbox-exec":
        writable = mode in ("workspace-write", "danger-full-access")
        if mode == "danger-full-access":
            return argv  # no confinement requested
        profile = (
            "(version 1)(allow default)"
            "(deny file-write*)"
            + (f'(allow file-write* (subpath "{workspace}"))' if writable else "")
            + '(allow file-write* (subpath "/private/var/folders"))'
            '(allow file-write* (literal "/dev/null"))'
        )
        return ["sandbox-exec", "-p", profile] + argv
    return argv


# ── Shell selection + environment ──────────────────────────────────────────


# PowerShell 5 `>` / Out-File defaults to UTF-16 LE (BOM ff fe). Python then
# dies with "Non-UTF-8 code starting with '\\xff'". Force utf8 for redirects.
_PS_UTF8_PREAMBLE = (
    "$PSDefaultParameterValues['Out-File:Encoding']='utf8';"
    "$PSDefaultParameterValues['Set-Content:Encoding']='utf8';"
    "$PSDefaultParameterValues['Add-Content:Encoding']='utf8';"
    "$OutputEncoding = [Console]::OutputEncoding = "
    "New-Object System.Text.UTF8Encoding $false; "
)

# No cmd.exe equivalent of the preamble exists: cmd parses the whole `/c` line
# in the codepage active at launch (936/GBK on a Chinese Windows), so a leading
# `chcp 65001` runs too late -- literals are already down-converted and `echo
# 中文 > f.txt` still lands as GBK. Hence pwsh 7 is preferred for chains below,
# and cmd stays a last resort that build_shell_argv cannot make UTF-8 safe.


def has_bash_chain(command: str) -> bool:
    """True if `&&` / `||` appears outside quotes (a real shell operator).

    Substring matching would send ``python -c "print('a && b')"`` to cmd.exe
    for no reason, so track quote state and only count bare operators.
    """
    quote = ""
    index = 0
    while index < len(command):
        char = command[index]
        if quote:
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
        elif command[index:index + 2] in {"&&", "||"}:
            return True
        index += 1
    return False


def build_shell_argv(command: str) -> tuple[list[str], str]:
    """Platform shell invocation. Stateless: one process per call."""
    if os.name == "nt":
        pwsh7 = shutil.which("pwsh")
        pwsh = pwsh7 or shutil.which("powershell")
        # PowerShell 5 rejects bash `&&` / `||` (the screenshot hang). pwsh 7
        # added them, so it can keep the UTF-8 preamble; only a box with just
        # PowerShell 5 has to fall back to cmd, encoding warts and all.
        if pwsh and (pwsh7 or not has_bash_chain(command)):
            return (
                [pwsh, "-NoProfile", "-NonInteractive", "-NoLogo",
                 "-Command", _PS_UTF8_PREAMBLE + command],
                Path(pwsh).stem.lower(),
            )
        return (["cmd.exe", "/d", "/s", "/c", command], "cmd")
    bash = shutil.which("bash")
    if bash:
        return ([bash, "-c", command], "bash")
    return (["/bin/sh", "-c", command], "sh")


def _scrub_env(*, network: bool, workspace: Path, workdir: Path) -> dict[str, str]:
    """Minimal allowlisted environment — no ambient credentials leak through."""
    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", ""),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": str(workspace),
        "USERPROFILE": str(workspace),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
        "SystemRoot": os.environ.get("SystemRoot", ""),
        "SystemDrive": os.environ.get("SystemDrive", ""),
        "COMSPEC": os.environ.get("COMSPEC", ""),
        "PATHEXT": os.environ.get("PATHEXT", ""),
        "NOUS_SHELL": "1",
        "NOUS_WORKSPACE": str(workspace),
        "NOUS_WORKDIR": str(workdir),
    }
    if network:
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
                    "http_proxy", "https_proxy", "no_proxy"):
            if key in os.environ:
                env[key] = os.environ[key]
    return {k: v for k, v in env.items() if v}


# ── Result ─────────────────────────────────────────────────────────────────


@dataclass
class ShellResult:
    ok: bool
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool
    workdir: str
    mode: str
    enforcement: str
    backend: str | None
    shell: str
    duration_ms: float
    error: str | None = None
    denied: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["text"] = render_text(self)
        return data


def _cap(raw: bytes, limit: int) -> tuple[str, bool]:
    truncated = len(raw) > limit
    text = raw[-limit:] if truncated else raw
    return text.decode("utf-8", errors="replace"), truncated


def render_text(result: ShellResult) -> str:
    """Harness-style rendering: output tail then explicit status markers."""
    parts: list[str] = []
    body = result.stdout.strip()
    parts.append(body if body else "(no output)")
    if result.stderr.strip():
        parts.append("[stderr]\n" + result.stderr.strip())
    if result.denied:
        return f"[blocked by sandbox: {result.denied}]"
    if result.truncated:
        parts.append("[output truncated; showing the tail only]")
    parts.append(
        f"[sandbox: {result.enforcement} {result.mode}"
        + (f" via {result.backend}" if result.backend else "")
        + f"; cwd={result.workdir}]"
    )
    if result.timed_out:
        parts.append("[timed out]")
    if result.error:
        parts.append(f"[error: {result.error}]")
    if result.exit_code is not None:
        parts.append(f"[exit code: {result.exit_code}]")
    return "\n".join(parts)


# ── Execution ──────────────────────────────────────────────────────────────


def _run_sync(
    argv: list[str], *, cwd: str, env: dict[str, str], timeout: float
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        argv,
        capture_output=True,
        cwd=cwd,
        env=env,
        timeout=timeout,
        check=False,
    )


async def execute(
    *,
    command: str,
    mode: str,
    workdir: Path,
    timeout_ms: int | None,
) -> ShellResult:
    """Run one confined command. Never raises for command failure."""
    workspace = workspace_root()
    backend = detect_os_sandbox()
    enforcement = "strict" if backend else "advisory"
    network = settings.shell_network_enabled

    default_s = settings.shell_timeout_seconds
    cap_s = settings.shell_timeout_cap_seconds
    if timeout_ms and timeout_ms > 0:
        timeout = min(max(timeout_ms / 1000.0, 0.1), float(cap_s))
    else:
        timeout = min(float(default_s), float(cap_s))

    denial = classify_command(command, mode=mode, enforcement=enforcement)
    if denial:
        return ShellResult(
            ok=False, exit_code=None, stdout="", stderr="", timed_out=False,
            truncated=False, workdir=str(workdir), mode=mode,
            enforcement=enforcement, backend=backend, shell="(none)",
            duration_ms=0.0, denied=denial,
        )

    argv, shell_name = build_shell_argv(command)
    if backend:
        argv = _wrap_with_sandbox(
            argv, backend=backend, mode=mode, workspace=workspace, network=network
        )
    env = _scrub_env(network=network, workspace=workspace, workdir=workdir)
    cap = settings.shell_stdout_cap_bytes

    started = time.perf_counter()
    try:
        completed = await asyncio.to_thread(
            _run_sync, argv, cwd=str(workdir), env=env, timeout=timeout
        )
        stdout, out_trunc = _cap(completed.stdout or b"", cap)
        stderr, err_trunc = _cap(completed.stderr or b"", min(cap, 64 * 1024))
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "shell_exec",
            shell=shell_name, mode=mode, enforcement=enforcement,
            backend=backend, exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
        return ShellResult(
            ok=completed.returncode == 0,
            exit_code=int(completed.returncode),
            stdout=stdout, stderr=stderr, timed_out=False,
            truncated=out_trunc or err_trunc, workdir=str(workdir),
            mode=mode, enforcement=enforcement, backend=backend,
            shell=shell_name, duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, out_trunc = _cap(exc.stdout or b"", cap)
        stderr, err_trunc = _cap(exc.stderr or b"", min(cap, 64 * 1024))
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.warning("shell_timeout", shell=shell_name, timeout=timeout)
        return ShellResult(
            ok=False, exit_code=None, stdout=stdout, stderr=stderr,
            timed_out=True, truncated=out_trunc or err_trunc,
            workdir=str(workdir), mode=mode, enforcement=enforcement,
            backend=backend, shell=shell_name, duration_ms=duration_ms,
            error=f"timed out after {int(timeout * 1000)}ms",
        )
    except Exception as exc:  # noqa: BLE001 - surface infra failure to the model
        logger.exception("shell_spawn_failed", shell=shell_name)
        return ShellResult(
            ok=False, exit_code=None, stdout="", stderr="", timed_out=False,
            truncated=False, workdir=str(workdir), mode=mode,
            enforcement=enforcement, backend=backend, shell=shell_name,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            error=f"failed to start command: {exc}",
        )
