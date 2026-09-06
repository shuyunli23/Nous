"""Conversation model - the short-term memory container."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    JSONType,
    created_at_column,
    updated_at_column,
    uuid_pk,
)
from app.database.models.enums import ConversationStatus, ExtractionStatus

if TYPE_CHECKING:
    from app.database.models.chat_mode import ChatMode
    from app.database.models.message import Message
    from app.database.models.user import User


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_updated", "user_id", "updated_time"),
        Index("ix_conversations_extraction", "extraction_status"),
    )

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="新会话")
    # True while Nous still owns the title. Manual rename (PATCH) sets this False.
    title_auto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ConversationStatus.ACTIVE
    )

    # Rolling summary produced by the extractor; also used to keep prompts small.
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Skill extraction state machine, lets background work be retried safely.
    extraction_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ExtractionStatus.PENDING
    )
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    mode_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("chat_modes.id", ondelete="SET NULL"), nullable=True
    )

    # Last todo_write snapshot for this conversation (Harness standing plan).
    todos: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONType, nullable=True
    )

    created_time: Mapped[datetime] = created_at_column()
    updated_time: Mapped[datetime] = updated_at_column()

    user: Mapped["User"] = relationship(back_populates="conversations")
    mode: Mapped["ChatMode | None"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.seq",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Conversation {self.id} {self.title!r}>"
