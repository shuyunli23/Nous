"""Helpers for export file URLs shown in chat."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote, unquote


def ascii_export_stem(title: str, *, fallback: str = "export") -> str:
    """Filesystem-safe ASCII stem (avoids broken localhost links with CJK)."""
    raw = (title or "").strip()
    ascii_part = re.sub(r"[^A-Za-z0-9\-]+", "_", raw).strip("_")
    if ascii_part:
        return ascii_part[:40]
    return fallback


def export_download_url(filename: str) -> str:
    """Relative URL that works via the Vite /api proxy or backend origin."""
    return f"/api/v1/files/exports/{quote(filename)}"


def export_user_message(*, kind: str, title: str, download_url: str, extra: str = "") -> str:
    """Tool message instructing the model how to present the link."""
    bits = [
        f"{kind} '{title}' ready.",
        f"download_url={download_url}",
        "In the reply, paste that download_url VERBATIM as a markdown relative link, "
        f"exactly: [打开文件]({download_url}) "
        "Do NOT also emit a markdown image ![]() for the same URL — the chat UI "
        "already previews image links. "
        "Do NOT invent a different filename. Do NOT rewrite it to "
        "http://127.0.0.1 or http://localhost.",
    ]
    if extra:
        bits.append(extra)
    return " ".join(bits)


EXPORT_URL_RE = re.compile(r"/api/v1/files/exports/[^\s)\]\"'<>]+")
_MD_EXPORT_RE = re.compile(r"\[[^\]]*\]\((/api/v1/files/exports/[^)]+)\)")


def rewrite_invented_export_links(text: str, trace: list[dict] | None) -> str:
    """Replace hallucinated export paths with URLs the tools actually produced."""
    if not text:
        return text
    real_by_ext: dict[str, str] = {}
    for step in trace or []:
        if step.get("kind") != "tool" or step.get("status") == "error":
            continue
        detail = str(step.get("detail") or "")
        for url in EXPORT_URL_RE.findall(detail):
            ext = Path(url.split("?", 1)[0]).suffix.lower()
            if ext:
                real_by_ext[ext] = url
    if not real_by_ext:
        return text

    def _replace(match: re.Match[str]) -> str:
        url = match.group(0)
        ext = Path(url.split("?", 1)[0]).suffix.lower()
        return real_by_ext.get(ext, url)

    return EXPORT_URL_RE.sub(_replace, text)


def strip_unbacked_export_links(text: str, trace: list[dict] | None) -> str:
    """Drop export links that neither a tool nor the exports folder can back."""
    if not text:
        return text
    from app.core.config import settings

    real = set()
    for step in trace or []:
        if step.get("kind") != "tool" or step.get("status") == "error":
            continue
        real.update(EXPORT_URL_RE.findall(str(step.get("detail") or "")))
    exports_dir = settings.resolve_path("./data/exports")

    def _backed(url: str) -> bool:
        if url in real:
            return True
        name = unquote(url.rsplit("/", 1)[-1].split("?", 1)[0])
        return bool(name) and (exports_dir / name).is_file()

    def _md(match: re.Match[str]) -> str:
        return match.group(0) if _backed(match.group(1)) else ""

    cleaned = _MD_EXPORT_RE.sub(_md, text)

    def _bare(match: re.Match[str]) -> str:
        url = match.group(0)
        return url if _backed(url) else ""

    return EXPORT_URL_RE.sub(_bare, cleaned)
