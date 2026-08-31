"""SQLAlchemy 声明式基类与公共列约定。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """统一使用带时区的 UTC 时间，避免 SQLite 里出现裸 naive 时间戳。"""
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    """32 位无连字符 UUID，作为业务主键（比自增 ID 更利于后续数据合并/同步）。"""
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


class UUIDPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_uuid)


class TimestampMixin:
    """创建/更新时间。onupdate 由 SQLAlchemy 在 flush 时自动写入。"""

    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    updated_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False, index=True
    )
