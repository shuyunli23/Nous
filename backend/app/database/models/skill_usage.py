"""SkillUsage - one row per skill injected into one answered turn.

This is the feedback ledger that drives ``success_rate`` and the automatic
demotion of skills that keep failing.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, created_at_column, uuid_pk

if TYPE_CHECKING:
    from app.database.models.skill import Skill


class SkillUsage(Base):
    __tablename__ = "skill_usages"
    __table_args__ = (
        Index("ix_skill_usages_skill_created", "skill_id", "created_at"),
        Index("ix_skill_usages_message", "message_id"),
    )

    id: Mapped[str] = uuid_pk()
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    message_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = created_at_column()

    skill: Mapped["Skill"] = relationship(back_populates="usages")
