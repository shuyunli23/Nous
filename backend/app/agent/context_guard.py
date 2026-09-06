"""Repeat-tool reminder (ported from DeepSeek Harness ``repeat-tool-reminder``).

Advisory only: never blocks or rewrites a call. Counts consecutive identical
``(tool, canonical args)`` and at configured thresholds injects a reminder
telling the model to change approach. Bookkeeping tools (``todo_write``) are
transparent to the chain so they cannot launder a loop.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings

FIRST_REMINDER = (
    "You are repeating the exact same tool call with identical arguments. "
    "Carefully analyze the previous result before calling again: if the task "
    "is not complete, try a different approach or different arguments instead "
    "of repeating the call."
)

LATER_REMINDER = (
    "Repeated tool call detected:\n"
    "- tool: {tool}\n"
    "- consecutive_calls: {count}\n"
    "- arguments: {arguments}\n"
    "The repeated calls are not making progress. Do not call this tool with "
    "these exact arguments again. Inspect the latest result and choose a "
    "different action, different arguments, or finish the task if enough "
    "evidence has been gathered."
)


def parse_thresholds(raw: str | None = None) -> list[int]:
    text = (raw if raw is not None else settings.guard_repeat_thresholds) or "3,5,8"
    out: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        value = int(part)
        if value < 2 or value in out:
            continue
        out.append(value)
    return sorted(out) or [3, 5, 8]


def excluded_tools() -> set[str]:
    raw = settings.guard_repeat_exclude or "todo_write"
    return {item.strip() for item in raw.split(",") if item.strip()}


def canonicalize_args(raw: Any) -> str:
    if raw is None:
        return "{}"
    if isinstance(raw, str):
        text = raw.strip() or "{}"
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text
    else:
        data = raw
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def note_call(
    chain: dict[str, Any] | None,
    *,
    name: str,
    raw_args: Any,
) -> tuple[dict[str, Any], str | None]:
    """Update the in-memory chain. Returns ``(chain, reminder_or_none)``."""
    if not settings.guard_repeat_enabled:
        return dict(chain or {}), None
    if name in excluded_tools():
        return dict(chain or {}), None

    key = f"{name}\n{canonicalize_args(raw_args)}"
    current = dict(chain or {})
    if current.get("key") == key:
        count = int(current.get("count") or 1) + 1
    else:
        count = 1
    current = {"key": key, "tool": name, "count": count, "args": canonicalize_args(raw_args)}

    thresholds = parse_thresholds()
    if count not in thresholds:
        return current, None
    if count == thresholds[0]:
        return current, FIRST_REMINDER
    preview = current["args"]
    cap = max(1, int(settings.guard_repeat_preview_chars or 500))
    if len(preview) > cap:
        preview = preview[:cap] + f"… (+{len(current['args']) - cap} more chars)"
    return current, LATER_REMINDER.format(tool=name, count=count, arguments=preview)
