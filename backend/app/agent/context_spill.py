"""Spill oversized tool results to disk (Harness ``spill-policy``).

Keeps ``ok`` / ``download_url`` / ``inspect`` inline so Nous artifact tools
stay usable after a spill. The full JSON is written under ``data/spills/``.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_KEEP_KEYS = (
    "ok",
    "error",
    "download_url",
    "open_url",
    "filename",
    "title",
    "inspect",
    "message",
)

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def _spill_dir() -> Path:
    path = settings.resolve_path(settings.spill_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _head_tail(text: str, *, budget: int) -> str:
    if len(text) <= budget:
        return text
    head = max(64, int(budget * 0.75))
    tail = max(32, budget - head - 40)
    return (
        text[:head]
        + "\n\n[... tool result middle pruned ...]\n\n"
        + text[-tail:]
    )


def maybe_spill(
    result: dict[str, Any],
    *,
    tool: str,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Replace an oversized result with a preview + locator. Never raises."""
    cap = int(settings.spill_max_inline_bytes or 0)
    if cap <= 0:
        return result
    try:
        raw = json.dumps(result, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return result
    size = len(raw.encode("utf-8"))
    if size <= cap:
        return result

    safe_tool = _SAFE.sub("-", (tool or "tool"))[:40] or "tool"
    conv = (conversation_id or "session")[:8]
    name = f"{conv}_{safe_tool}_{uuid.uuid4().hex[:10]}.json"
    path = _spill_dir() / name
    try:
        path.write_text(raw, encoding="utf-8")
    except OSError as exc:
        logger.warning("spill_write_failed", tool=tool, error=str(exc))
        return result

    notice = (
        f"(Omitted {size} bytes. Full formatted result stored at: {path}. "
        "Re-read only the fields you still need; do not ask to dump the file.)"
    )
    reserved = len(notice.encode("utf-8")) + 80
    preview_budget = max(120, cap - reserved)
    preview = _head_tail(raw, budget=preview_budget)

    slim: dict[str, Any] = {
        "spilled": True,
        "omitted_bytes": size,
        "spill_path": str(path),
        "preview": preview,
        "notice": notice,
    }
    for key in _KEEP_KEYS:
        if key in result:
            slim[key] = result[key]
    slim.setdefault("ok", result.get("ok", True))
    logger.info(
        "tool_result_spilled",
        tool=tool,
        omitted_bytes=size,
        path=str(path),
    )
    return slim
