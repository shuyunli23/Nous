"""Installed Skill Pack (nous-pack/2) rows and their local tools."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import (
    Base,
    JSONType,
    created_at_column,
    updated_at_column,
    uuid_pk,
)
from app.database.models.enums import SkillPackStatus

if TYPE_CHECKING:
    from app.database.models.skill import Skill
    from app.database.models.user import User


class SkillPack(Base):
    __tablename__ = "skill_packs"
    __table_args__ = (
        UniqueConstraint("user_id", "pack_id", "version", name="uq_skill_packs_user_pack_ver"),
        Index("ix_skill_packs_user_status", "user_id", "status"),
        Index("ix_skill_packs_user_pack_id", "user_id", "pack_id"),
    )

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    pack_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    format: Mapped[str] = mapped_column(String(32), nullable=False, default="nous-pack/2")

    # Permissions the user actually granted at install time.
    permissions: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    # Permissions declared by the pack (for UI / audit).
    permissions_requested: Mapped[list[str]] = mapped_column(
        JSONType, nullable=False, default=list
    )
    tags: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    license: Mapped[str | None] = mapped_column(String(64), nullable=True)
    min_nous: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Relative to backend root, e.g. ./data/skill_packs/{user}/{pack_id}/{version}
    install_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=SkillPackStatus.PENDING_REVIEW
    )
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    user: Mapped["User"] = relationship()
    tools: Mapped[list["SkillPackTool"]] = relationship(
        back_populates="pack",
        cascade="all, delete-orphan",
        order_by="SkillPackTool.name",
    )
    skills: Mapped[list["Skill"]] = relationship(back_populates="pack")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SkillPack {self.pack_id}@{self.version} {self.status}>"


class SkillPackTool(Base):
    __tablename__ = "skill_pack_tools"
    __table_args__ = (
        UniqueConstraint("pack_row_id", "name", name="uq_skill_pack_tools_pack_name"),
        Index("ix_skill_pack_tools_exposed", "exposed_name"),
    )

    id: Mapped[str] = uuid_pk()
    pack_row_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("skill_packs.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("skills.id", ondelete="SET NULL"), nullable=True
    )

    # Local short name from the pack (e.g. generate_image).
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # Always-namespaced name exposed to the model (pack__nous_image_gen__generate_image).
    exposed_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    runner: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    # Path relative to skill dir, as declared in tool.json.
    skill_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = created_at_column()

    pack: Mapped["SkillPack"] = relationship(back_populates="tools")
    skill: Mapped["Skill | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SkillPackTool {self.exposed_name} enabled={self.enabled}>"
