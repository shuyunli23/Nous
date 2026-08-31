"""Message model - one turn inside a conversation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, JSONType, created_at_column, uuid_pk

if TYPE_CHECKING:
    from app.database.models.conversation import Conversation


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_messages_conversation_seq", "conversation_id", "seq"),
    )

    id: Mapped[str] = uuid_pk()
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )

    # Monotonic per-conversation ordinal. `created_at` alone is not a stable
    # sort key: turns written in the same request can share a timestamp, and
    # UUID ids do not tie-break chronologically.
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Populated for assistant turns that requested tools, and for tool results.
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONType, nullable=True
    )
    tool_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)

    # Skill ids injected into the prompt for this turn (audit trail for retrieval).
    used_skill_ids: Mapped[list[str] | None] = mapped_column(JSONType, nullable=True)

    # Compact agent steps for the chat UI (skills / tools / answer). Not LLM history.
    execution_trace: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONType, nullable=True
    )

    created_at: Mapped[datetime] = created_at_column()

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Message {self.role} {self.id}>"
