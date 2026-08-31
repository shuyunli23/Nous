"""Async engine and session management."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _ensure_sqlite_dir(url: str) -> None:
    """Create the parent folder for a file-backed SQLite database."""
    marker = ":///"
    if marker not in url:
        return
    raw_path = url.split(marker, 1)[1]
    if not raw_path or raw_path == ":memory:":
        return
    path = settings.resolve_path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)


def create_engine() -> AsyncEngine:
    """Build the async engine, applying dialect-specific tuning."""
    kwargs: dict[str, Any] = {"echo": settings.db_echo, "future": True}

    if settings.is_sqlite:
        _ensure_sqlite_dir(settings.database_url)
        # SQLite + asyncio: one connection reused, no pool pre-ping needed.
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(pool_size=10, max_overflow=20, pool_pre_ping=True)

    engine = create_async_engine(settings.database_url, **kwargs)

    if settings.is_sqlite:
        # SQLite ignores FK constraints unless explicitly enabled per connection.
        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine: AsyncEngine = create_engine()

SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session, rolling back on error."""
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Standalone session context for background tasks and scripts."""
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_database() -> bool:
    """Lightweight connectivity probe used by the health endpoint."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("database_unreachable", error=str(exc))
        return False


async def dispose_engine() -> None:
    await engine.dispose()
