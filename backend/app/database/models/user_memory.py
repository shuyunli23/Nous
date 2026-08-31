"""Per-user long-term memory: two lanes that never mix.

``persona`` — companion (and custom modes that opt in): habits, people, mood.
``knowledge`` — tutor (optional) and custom modes that opt in: what you already
know. No emotions, relationships, or social history.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    JSONType,
    created_at_column,
    updated_at_column,
    uuid_pk,
)

if TYPE_CHECKING:
    from app.database.models.user import User


class UserMemory(Base):
    __tablename__ = "user_memories"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    persona_data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    knowledge_data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    persona_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    knowledge_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    user: Mapped["User"] = relationship(back_populates="memory")
