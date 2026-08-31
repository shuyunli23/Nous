"""One LLM completion, for token totals. No money."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, created_at_column, uuid_pk

if TYPE_CHECKING:
    from app.database.models.conversation import Conversation
    from app.database.models.user import User


class LlmUsageEvent(Base):
    __tablename__ = "llm_usage_events"
    __table_args__ = (
        Index("ix_llm_usage_user_created", "user_id", "created_at"),
        Index("ix_llm_usage_conversation", "conversation_id"),
        Index("ix_llm_usage_purpose_created", "purpose", "created_at"),
    )

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    provider_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider_label: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = created_at_column()

    user: Mapped["User | None"] = relationship()
    conversation: Mapped["Conversation | None"] = relationship()
