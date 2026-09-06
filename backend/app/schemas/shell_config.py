"""Schemas for the runtime shell-tool settings API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SandboxMode = Literal["read-only", "workspace-write", "danger-full-access"]
Source = Literal["runtime", "env"]


class ShellConfigUpdate(BaseModel):
    """Partial update. Omitted fields keep their stored overlay value."""

    enabled: bool | None = None
    default_mode: SandboxMode | None = None

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class ShellConfigResponse(BaseModel):
    enabled: bool
    enabled_source: Source
    default_mode: SandboxMode
    default_mode_source: Source
    max_mode: SandboxMode
    modes: list[SandboxMode]
    workspace_path: str
    os_sandbox: str
    enforcement: Literal["strict", "advisory"]
    backend: str | None = None
    network: bool
    store_path: str
