"""Runtime configuration for the shell tool.

Lets the Settings page enable/disable ``run_command`` and pick the standing
sandbox mode without editing ``.env``. The overlay is stored as a small JSON
file; empty/omitted fields fall back to the ``.env`` defaults.

Security boundary: the UI may toggle ``enabled`` and choose ``default_mode``,
but the escalation **ceiling** (``max_mode``) stays ``.env``-only. The UI can
never widen the ceiling, so it cannot grant ``danger-full-access`` on its own.
"""

from __future__ import annotations

import json
import os
import stat
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.agent.tools.shell_sandbox import MODES, detect_os_sandbox, mode_rank
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

STORE_VERSION = 1
Source = Literal["runtime", "env"]


@dataclass(frozen=True)
class ResolvedShell:
    enabled: bool
    enabled_source: Source
    default_mode: str
    default_mode_source: Source
    max_mode: str
    workspace_path: str
    os_sandbox: str
    network: bool
    enforcement: str
    backend: str | None


class ShellConfigStore:
    """Thread-safe JSON overlay for the shell tool settings."""

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
            logger.warning("shell_store_unreadable", error=str(exc))
            self._data = {}
            return
        self._data = (
            {k: v for k, v in raw.items() if k != "version"}
            if isinstance(raw, dict)
            else {}
        )

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
        """Apply a partial update. ``None`` clears an override."""
        self._ensure_loaded()
        with self._lock:
            if "enabled" in changes:
                value = changes["enabled"]
                if value is None:
                    self._data.pop("enabled", None)
                else:
                    self._data["enabled"] = bool(value)

            if "default_mode" in changes:
                value = changes["default_mode"]
                if value is None or (isinstance(value, str) and not value.strip()):
                    self._data.pop("default_mode", None)
                else:
                    mode = str(value).strip()
                    if mode not in MODES:
                        raise ValidationError(
                            f"Unknown sandbox mode '{mode}'.",
                            details={"mode": mode, "allowed": list(MODES)},
                        )
                    # Never let the UI standing mode exceed the .env ceiling.
                    if mode_rank(mode) > mode_rank(settings.shell_max_mode):
                        raise ValidationError(
                            f"default_mode '{mode}' exceeds the deployment "
                            f"ceiling '{settings.shell_max_mode}'.",
                            details={"max_mode": settings.shell_max_mode},
                        )
                    self._data["default_mode"] = mode

            self._save()
            return dict(self._data)

    def reset(self) -> None:
        self._ensure_loaded()
        with self._lock:
            self._data = {}
            if self._path.exists():
                try:
                    self._path.unlink()
                except OSError:
                    self._save()


_store: ShellConfigStore | None = None
_store_lock = threading.Lock()


def get_shell_store() -> ShellConfigStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = ShellConfigStore(settings.shell_config_store_path)
    return _store


def reset_shell_store() -> None:
    """Drop the singleton so the next access re-reads the path (tests only)."""
    global _store
    with _store_lock:
        _store = None


def resolve_shell(runtime: dict[str, Any] | None = None) -> ResolvedShell:
    """Merge the UI overlay with ``.env`` defaults."""
    overlay = runtime if runtime is not None else get_shell_store().snapshot()

    if "enabled" in overlay:
        enabled, enabled_source = bool(overlay["enabled"]), "runtime"
    else:
        enabled, enabled_source = bool(settings.shell_tool_enabled), "env"

    ceiling = settings.shell_max_mode
    raw_default = str(overlay.get("default_mode") or "").strip()
    if raw_default in MODES:
        default_mode, default_source = raw_default, "runtime"
    else:
        default_mode, default_source = settings.shell_default_mode, "env"
    # Clamp the standing mode to the ceiling regardless of source.
    if mode_rank(default_mode) > mode_rank(ceiling):
        default_mode = ceiling

    backend = detect_os_sandbox()
    return ResolvedShell(
        enabled=enabled,
        enabled_source=enabled_source,  # type: ignore[arg-type]
        default_mode=default_mode,
        default_mode_source=default_source,  # type: ignore[arg-type]
        max_mode=ceiling,
        workspace_path=str(settings.shell_workspace_path),
        os_sandbox=settings.shell_os_sandbox,
        network=bool(settings.shell_network_enabled),
        enforcement="strict" if backend else "advisory",
        backend=backend,
    )
