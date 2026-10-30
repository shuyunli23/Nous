"""Resolve material inputs inside Nous' uploaded/generated file directories.

Document builders must not fetch arbitrary URLs or read arbitrary server files.
The returned path is resolved before the containment check, including symlinks.
Callers decide which file formats and size limits they support.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlsplit

from app.core.config import settings


def resolve_material_asset(source: str) -> Path:
    """Resolve an existing exports/uploads path or local files API URL.

    Raises ``ValueError`` for remote URLs, traversal, missing files and paths
    outside the two managed roots. No network request is made.
    """
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Material asset must be a non-empty local file reference.")
    raw = source.strip()
    if "\x00" in raw:
        raise ValueError("Material asset reference contains an invalid character.")
    roots = {
        name: settings.resolve_path(f"./data/{name}").resolve()
        for name in ("exports", "uploads")
    }
    prefixes = {f"{settings.api_prefix.rstrip('/')}/files/", "/api/v1/files/"}
    original = Path(raw)
    if original.is_absolute() and not any(raw.replace("\\", "/").startswith(prefix) for prefix in prefixes):
        candidate = original.resolve()
        if not any(candidate.is_relative_to(root) for root in roots.values()):
            raise ValueError("Material asset must be inside data/exports or data/uploads.")
    else:
        parsed = urlsplit(raw)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("Material assets must be local exports/uploads references, not remote URLs.")
        decoded = unquote(parsed.path).replace("\\", "/")
        relative = decoded
        for prefix in prefixes:
            if decoded.startswith(prefix):
                relative = decoded[len(prefix):]
                break
        pieces = relative.split("/")
        if len(pieces) < 2 or pieces[0] not in roots:
            raise ValueError("Use /api/v1/files/exports/<file> or /api/v1/files/uploads/<file>.")
        if any(part in {"", ".", ".."} or ":" in part for part in pieces[1:]):
            raise ValueError("Material asset reference must not contain path traversal.")
        root = roots[pieces[0]]
        candidate = root.joinpath(*pieces[1:]).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("Material asset resolves outside its managed directory.")
    if not candidate.is_file():
        raise ValueError(f"Material asset does not exist: {candidate.name}")
    return candidate
