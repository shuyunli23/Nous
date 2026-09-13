"""Session-owned todo list (ported from DeepSeek Harness ``todo_write``).

The model sends the ENTIRE list on every call — no partial updates, no ids.
``status`` is ``pending`` | ``in_progress`` | ``completed``. Nous enforces
exactly one ``in_progress`` item (Harness ``allowParallelInProgress: false``):
this agent is single-threaded, so concurrent active tasks are a lie.
"""

from __future__ import annotations

from typing import Any

STATUSES = ("pending", "in_progress", "completed")
MAX_ITEMS = 20
MAX_CONTENT = 200


def unfinished_todos(todos: list[dict[str, str]] | None) -> list[str]:
    """Contents still pending or in_progress (empty if the list is done)."""
    leftover: list[str] = []
    for item in todos or []:
        if item.get("status") in {"pending", "in_progress"}:
            content = str(item.get("content") or "").strip()
            if content:
                leftover.append(content)
    return leftover


def counts_of(todos: list[dict[str, str]]) -> dict[str, int]:
    counts = {"pending": 0, "in_progress": 0, "completed": 0}
    for item in todos:
        status = item.get("status")
        if status in counts:
            counts[status] += 1
    return counts


def validate_todos(raw: Any) -> tuple[list[dict[str, str]] | None, str | None]:
    """Return ``(todos, None)`` or ``(None, error)``. Extra keys fail loud."""
    if raw is None:
        return None, "invalid todos: expected a non-empty array"
    items = raw
    if isinstance(raw, str):
        import json

        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            return None, f"invalid todos: expected a JSON array ({exc})"
    if not isinstance(items, list) or not items:
        return None, "invalid todos: expected a non-empty array"
    if len(items) > MAX_ITEMS:
        return None, f"invalid todos: at most {MAX_ITEMS} items (got {len(items)})"

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            return None, f"invalid todo: item {index} is not an object"
        extra = set(item) - {"content", "status"}
        if extra:
            return None, (
                "invalid todo: only `content` and `status` are allowed "
                f"(got extra {sorted(extra)})"
            )
        content = str(item.get("content") or "").strip()
        if not content:
            return None, "invalid todo: `content` must be a non-empty string"
        if len(content) > MAX_CONTENT:
            content = content[: MAX_CONTENT - 1] + "…"
        if content.lower() in seen:
            return None, f'invalid todos: duplicate content "{content}"'
        seen.add(content.lower())
        status = str(item.get("status") or "pending").strip()
        if status not in STATUSES:
            return None, (
                f"invalid todo: status must be one of {', '.join(STATUSES)}"
            )
        out.append({"content": content, "status": status})

    active = sum(1 for item in out if item["status"] == "in_progress")
    if active > 1:
        return None, (
            f"invalid todos: at most one task may be in_progress (got {active})"
        )
    return out, None


def apply_todo_write(raw: Any) -> dict[str, Any]:
    todos, error = validate_todos(raw)
    if error or todos is None:
        return {"ok": False, "error": error}
    counts = counts_of(todos)
    return {
        "ok": True,
        "todos": todos,
        "counts": {
            "pending": counts["pending"],
            "inProgress": counts["in_progress"],
            "completed": counts["completed"],
        },
        "message": (
            f"Updated todo list: {counts['pending']} pending, "
            f"{counts['in_progress']} in progress, "
            f"{counts['completed']} completed."
        ),
    }


def format_todo_detail(todos: list[dict[str, str]]) -> str:
    marks = {"pending": "·", "in_progress": "›", "completed": "✓"}
    lines: list[str] = []
    for item in todos:
        mark = marks.get(item.get("status") or "", "·")
        lines.append(f"{mark} {item.get('content') or ''}")
    return " · ".join(lines)


def format_todos_for_prompt(todos: list[dict[str, str]]) -> str:
    if not todos:
        return ""
    marks = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}
    lines = ["## Current todo list (standing plan for this conversation)"]
    for item in todos:
        mark = marks.get(item.get("status") or "pending", "[ ]")
        lines.append(f"- {mark} {item.get('content')}")
    counts = counts_of(todos)
    lines.append(
        f"({counts['pending']} pending, {counts['in_progress']} in progress, "
        f"{counts['completed']} completed). "
        "Keep this list current with todo_write. "
        "If the user started a new task, replace the list wholesale."
    )
    return "\n".join(lines)


TODO_GUIDANCE = """
## Planning (todo_write)
For multi-step work (3+ steps, shell/git/build, research then an artifact, \
or anything that spans several tool calls), first call `todo_write` with the \
ENTIRE list. Each item is `{content, status}` where status is \
`pending` | `in_progress` | `completed`.
Rules:
- Send the full list every call — there are no partial updates.
- Exactly one item may be `in_progress` at a time.
- Mark the step you are about to do `in_progress`, then `completed` when it is done.
- Do not use todo_write for a one-shot question or a single tool call.
- A leftover list from a previous task must be replaced, not appended blindly.
""".strip()


def wants_structured_plan(goal: str, required_tools: list[str]) -> bool:
    """Heuristic: this turn is complex enough that a checklist helps."""
    if len(required_tools) >= 2:
        return True
    text = (goal or "").lower()
    hints = (
        "然后",
        "并且",
        "再",
        "分步",
        "先",
        "同时",
        "and then",
        "step by step",
        "git ",
        "初始化",
        "run_command",
        "多步",
    )
    return any(key in text for key in hints) and len(text) > 16
