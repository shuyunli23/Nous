"""User model.

Auth is out of scope for this system; a single ``external_id`` keyed user row is
enough to scope conversations and skills per person and to leave room for a real
identity provider later.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, created_at_column, uuid_pk

if TYPE_CHECKING:
    from app.database.models.chat_mode import ChatMode
    from app.database.models.conversation import Conversation
    from app.database.models.skill import Skill
    from app.database.models.memory_field import MemoryFieldRecord
    from app.database.models.memory_item import MemoryItem
    from app.database.models.user_memory import UserMemory


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = uuid_pk()
    external_id: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = created_at_column()

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    skills: Mapped[list["Skill"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chat_modes: Mapped[list["ChatMode"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    memory: Mapped["UserMemory | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    memory_items: Mapped[list["MemoryItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    memory_fields: Mapped[list["MemoryFieldRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User {self.external_id}>"
