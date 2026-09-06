"""Short-term conversation memory.

Loads recent turns and compact them so image-heavy chats do not push earlier
user requests out of the context window.
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context_compact import apply_window, prune_text
from app.agent.goal import ATTACH_START
from app.core.config import settings
from app.database.models.enums import MessageRole
from app.llm.client import Message
from app.repositories.conversation_repo import ConversationRepository

_DATA_URL = re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+")
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_HTML_IMG = re.compile(r"<img\b[^>]*>", re.I)
_MAX_ASSISTANT_CHARS = 1800


def compact_history_text(role: str, content: str) -> str:
    """Keep intent, drop payloads that only inflate the context budget."""
    text = content or ""
    if role == "user" and ATTACH_START in text:
        text = text.split(ATTACH_START, 1)[0].rstrip()
    text = _DATA_URL.sub("[图片]", text)
    text = _MD_IMAGE.sub("[图片]", text)
    text = _HTML_IMG.sub("[图片]", text)
    if role == "tool":
        pruned, _ = prune_text(
            text,
            threshold=settings.compact_tool_threshold_chars,
            head=settings.compact_tool_head_chars,
            tail=settings.compact_tool_tail_chars,
        )
        return pruned
    if role != "user" and len(text) > _MAX_ASSISTANT_CHARS:
        text = text[: _MAX_ASSISTANT_CHARS - 12].rstrip() + "\n…(已省略)"
    return text


async def load_history(
    session: AsyncSession,
    conversation_id: str,
    *,
    max_turns: int | None = None,
    max_chars: int | None = None,
    existing_summary: str | None = None,
) -> list[Message]:
    """Return recent messages as LLM-compatible dicts, oldest first.

    Only user / assistant / tool roles are returned; system messages are
    injected separately by the prompt builder. Older turns that fall out of
    the budget become a ``<compacted-summary>`` checkpoint.
    """
    _max_turns = max_turns or settings.memory_max_turns
    _max_chars = max_chars or settings.memory_max_chars

    repo = ConversationRepository(session)
    # Fetch extra rows so compaction can keep more user turns.
    rows = await repo.list_messages(conversation_id, limit=max(_max_turns * 4, 80))

    allowed_roles = {MessageRole.USER, MessageRole.ASSISTANT, MessageRole.TOOL}
    messages: list[Message] = []

    for row in rows:
        if row.role not in allowed_roles:
            continue
        msg: Message = {
            "role": row.role,
            "content": compact_history_text(row.role, row.content or ""),
        }
        if row.tool_calls:
            msg["tool_calls"] = row.tool_calls
        if row.tool_call_id:
            msg["tool_call_id"] = row.tool_call_id
        messages.append(msg)

    trimmed, _checkpoint = apply_window(
        messages,
        max_chars=_max_chars,
        max_turns=_max_turns,
        existing_summary=existing_summary,
        checkpoint=bool(settings.compact_checkpoint_enabled),
    )
    return trimmed
