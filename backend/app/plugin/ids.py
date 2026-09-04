"""Stable plugin identifiers (npm / GitHub names → pack id)."""

from __future__ import annotations

import re

from app.skill.pack_names import validate_pack_id

_UNSAFE = re.compile(r"[^a-z0-9._-]+")


def npm_name_to_pack_id(name: str) -> str:
    """Turn ``@scope/pkg`` or ``pkg`` into a nous pack id."""
    raw = (name or "").strip().lower()
    if raw.startswith("@"):
        raw = raw[1:].replace("/", ".", 1)
    else:
        raw = raw.replace("/", ".")
    cleaned = _UNSAFE.sub("-", raw).strip(".-")
    if not cleaned:
        cleaned = "imported.plugin"
    if cleaned[0].isdigit():
        cleaned = f"p.{cleaned}"
    return validate_pack_id(cleaned[:127])
