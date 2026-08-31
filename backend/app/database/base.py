"""Declarative base plus portable column helpers.

The schema must run on both PostgreSQL (docker compose) and SQLite (local dev),
so we avoid PG-only constructs: ``JSONB`` is used only where the dialect
supports it, arrays are stored as JSON lists, and UUIDs are 36-char strings.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# JSONB on Postgres, plain JSON elsewhere.
JSONType = JSON().with_variant(postgresql.JSONB(), "postgresql")


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    type_annotation_map = {dict[str, Any]: JSONType, list[Any]: JSONType}


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Timezone-aware UTC now (SQLite has no server-side ``now()`` with tz)."""
    return datetime.now(timezone.utc)


def uuid_pk() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=new_uuid)


def created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


def updated_at_column() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
