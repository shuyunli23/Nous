"""Naming helpers for nous-pack/2 tools.

Frozen decision: every pack tool is always exposed under a collision-free
namespaced name ``pack__{sanitized_pack_id}__{tool_name}`` (MCP-style).
"""

from __future__ import annotations

import re

_PACK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,126}$")
_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def validate_pack_id(pack_id: str) -> str:
    pid = (pack_id or "").strip()
    if not _PACK_ID_RE.match(pid):
        raise ValueError(
            "pack id must match [a-z0-9][a-z0-9._-]* (max 127 chars)"
        )
    return pid


def validate_tool_name(name: str) -> str:
    n = (name or "").strip()
    if not _TOOL_NAME_RE.match(n):
        raise ValueError(
            "tool name must match [a-z][a-z0-9_]{1,63}"
        )
    return n


def sanitize_pack_id_for_tool(pack_id: str) -> str:
    """Turn pack id into a function-name-safe segment."""
    return re.sub(r"[^a-z0-9_]", "_", pack_id.lower())


def exposed_tool_name(pack_id: str, tool_name: str) -> str:
    """Always-namespaced tool name for the model / registry."""
    return f"pack__{sanitize_pack_id_for_tool(pack_id)}__{validate_tool_name(tool_name)}"


def is_pack_tool_name(name: str) -> bool:
    return bool(name) and name.startswith("pack__")
