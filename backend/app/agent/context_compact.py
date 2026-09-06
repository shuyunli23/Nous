"""Model-free history compaction (Harness pruner + checkpoint framing).

Two cheap passes, no extra LLM call:

1. **Tool-result prune** — rewrite an oversized tool/assistant blob to
   head + omission marker + tail.
2. **Checkpoint** — when older turns are dropped to stay under the char
   budget, prepend a ``<compacted-summary>`` so the model still sees goals
   and artifacts instead of a silent hole.
"""

from __future__ import annotations

from typing import Any

from app.llm.client import Message

PRUNE_MARK = "\n\n[... tool result middle pruned ...]\n\n"
CHECKPOINT_PREAMBLE = (
    "This is an automatically generated checkpoint condensing an earlier "
    "span of the conversation to free up context. Treat the captured context "
    "as established background and build on it without restating it. "
    "Continue the task directly from the messages that follow, without "
    "acknowledging this checkpoint."
)


def prune_text(
    text: str,
    *,
    threshold: int,
    head: int,
    tail: int,
) -> tuple[str, bool]:
    """Return ``(text, pruned)``. Never grows the input."""
    if threshold <= 0 or len(text) <= threshold:
        return text, False
    head = max(0, head)
    tail = max(0, tail)
    marker = PRUNE_MARK
    if head + tail + len(marker) >= len(text):
        return text, False
    kept = text[:head] + marker + (text[-tail:] if tail else "")
    if len(kept) >= len(text):
        return text, False
    return kept, True


def extract_checkpoint(
    dropped: list[Message],
    *,
    existing_summary: str | None = None,
    limit: int = 1200,
) -> str:
    """Extractive checkpoint from messages that will leave the window."""
    goals: list[str] = []
    artifacts: list[str] = []
    for msg in dropped:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user" and len(goals) < 4:
            line = content.replace("\n", " ")
            goals.append(line[:160])
        if role == "assistant":
            for token in content.split():
                if "/api/v1/files/" in token and token not in artifacts:
                    artifacts.append(token.strip("()[].,"))
            if len(artifacts) >= 6:
                break

    lines = [CHECKPOINT_PREAMBLE, "", "<compacted-summary>"]
    prior = (existing_summary or "").strip()
    if prior:
        lines += ["## Prior summary", prior[:400], ""]
    lines.append("## Primary Request and Intent")
    if goals:
        lines.extend(f"- {item}" for item in goals)
    else:
        lines.append("- (none)")
    lines.append("## Files and Code")
    if artifacts:
        lines.extend(f"- {item}" for item in artifacts[:6])
    else:
        lines.append("- (none)")
    lines.append("</compacted-summary>")
    text = "\n".join(lines)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def apply_window(
    messages: list[Message],
    *,
    max_chars: int,
    max_turns: int,
    existing_summary: str | None = None,
    checkpoint: bool = True,
) -> tuple[list[Message], str | None]:
    """Keep a recent tail under ``max_chars`` / ``max_turns``.

    User turns are preferred when the budget is tight (follow-ups like
    「再试试」need the original request). Dropped prefix becomes a checkpoint.
    """
    trimmed: list[Message] = []
    total = 0
    dropped: list[Message] = []
    # Walk newest-first, then reverse.
    for msg in reversed(messages):
        size = len(msg.get("content") or "")
        role = msg.get("role")
        over = total + size > max_chars and trimmed
        if over and role == "user":
            content = msg.get("content") or ""
            if len(content) > 400:
                msg = {**msg, "content": content[:400]}
                size = 400
            if total + size > max_chars * 2:
                dropped.append(msg)
                continue
        elif over:
            dropped.append(msg)
            continue
        if len(trimmed) >= max_turns:
            dropped.append(msg)
            continue
        trimmed.insert(0, msg)
        total += size

    dropped.reverse()
    note: str | None = None
    if checkpoint and dropped:
        note = extract_checkpoint(dropped, existing_summary=existing_summary)
        trimmed.insert(0, {"role": "user", "content": note})
    return trimmed, note
