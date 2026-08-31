"""Chat mode — behavioral frame for a conversation (workbench / tutor / companion / custom)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, created_at_column, updated_at_column, uuid_pk

if TYPE_CHECKING:
    from app.database.models.conversation import Conversation
    from app.database.models.user import User


class ChatMode(Base):
    __tablename__ = "chat_modes"
    __table_args__ = (
        Index("ix_chat_modes_user", "user_id"),
        Index("ix_chat_modes_key", "key", unique=True),
    )

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="light")
    use_long_term_memory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    use_knowledge_memory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    user: Mapped["User | None"] = relationship(back_populates="chat_modes")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="mode")
