"""Open-vocabulary memory field (name + description). Items hang off field_key."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, created_at_column, updated_at_column, uuid_pk

if TYPE_CHECKING:
    from app.database.models.user import User


class MemoryFieldRecord(Base):
    __tablename__ = "memory_fields"
    __table_args__ = (
        UniqueConstraint("user_id", "lane", "field_key", name="uq_memory_fields_user_lane_key"),
        Index("ix_memory_fields_user_lane", "user_id", "lane"),
    )

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lane: Mapped[str] = mapped_column(String(16), nullable=False)
    field_key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    user: Mapped["User"] = relationship(back_populates="memory_fields")
