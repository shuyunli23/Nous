"""Skill models - the long-term memory of the agent.

``Skill`` holds the current state of a capability; ``SkillVersion`` keeps an
immutable snapshot per edit so the lifecycle (create -> validate -> use ->
feedback -> optimise) stays auditable and revertible.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    JSONType,
    created_at_column,
    updated_at_column,
    uuid_pk,
)
from app.database.models.enums import SkillSource, SkillStatus

if TYPE_CHECKING:
    from app.database.models.skill_pack import SkillPack
    from app.database.models.skill_usage import SkillUsage
    from app.database.models.user import User


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        Index("ix_skills_user_status", "user_id", "status"),
        Index("ix_skills_user_name", "user_id", "name"),
        Index("ix_skills_pack_row", "pack_row_id"),
    )

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    pack_row_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("skill_packs.id", ondelete="SET NULL"), nullable=True
    )
    # Stable key inside an L2 pack (e.g. "image-gen") for upgrades.
    pack_skill_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    instruction: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Trigger surface used by the hybrid retriever.
    trigger_keywords: Mapped[list[str]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    trigger_intent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # [{"step": 1, "action": "...", "command": "...", "expect": "..."}]
    workflow: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    # [{"question": "...", "solution": "...", "conversation_id": "..."}]
    examples: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    tools: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SkillStatus.DRAFT
    )
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SkillSource.AUTO
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_from_conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )

    # Hash of the text that produced the current embedding; lets reindex skip
    # unchanged rows instead of re-embedding the whole library.
    embedding_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    user: Mapped["User"] = relationship(back_populates="skills")
    pack: Mapped["SkillPack | None"] = relationship(back_populates="skills")
    versions: Mapped[list["SkillVersion"]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="SkillVersion.version",
    )
    usages: Mapped[list["SkillUsage"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )

    @property
    def success_rate(self) -> float | None:
        """Derived, never stored: avoids two sources of truth."""
        rated = self.success_count + self.failure_count
        if rated == 0:
            return None
        return round(self.success_count / rated, 4)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Skill {self.name!r} v{self.version} {self.status}>"


class SkillVersion(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (Index("ix_skill_versions_skill", "skill_id", "version"),)

    id: Mapped[str] = uuid_pk()
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_column()

    skill: Mapped["Skill"] = relationship(back_populates="versions")
