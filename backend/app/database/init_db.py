"""Database initialisation.

``DB_AUTO_CREATE=true`` (default) creates missing tables on startup so the app
runs out of the box. Alembic remains the source of truth for schema changes in
production - see ``backend/alembic``.
"""

from __future__ import annotations

from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.database.base import Base
from app.database.models import User  # noqa: F401  (registers all tables)
from app.database.session import SessionFactory, engine

logger = get_logger(__name__)


async def create_tables() -> None:
    """Create any tables that do not exist yet."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_skill_pack_columns)
        await conn.run_sync(_ensure_message_trace_column)
        await conn.run_sync(_ensure_chat_mode_columns)
        await conn.run_sync(_ensure_knowledge_memory_column)
        await conn.run_sync(_ensure_structured_memory_columns)
        await conn.run_sync(_ensure_conversation_title_auto)
        await conn.run_sync(_ensure_conversation_todos_column)
    logger.info("database_tables_ready", tables=len(Base.metadata.tables))


def _ensure_skill_pack_columns(sync_conn) -> None:
    """Add L2 columns to pre-existing DBs (create_all does not ALTER)."""
    insp = inspect(sync_conn)
    if "skills" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("skills")}
    dialect = sync_conn.dialect.name
    statements: list[str] = []
    if "pack_row_id" not in cols:
        if dialect == "sqlite":
            statements.append(
                "ALTER TABLE skills ADD COLUMN pack_row_id VARCHAR(36)"
            )
        else:
            statements.append(
                "ALTER TABLE skills ADD COLUMN pack_row_id VARCHAR(36) "
                "REFERENCES skill_packs(id) ON DELETE SET NULL"
            )
    if "pack_skill_key" not in cols:
        statements.append(
            "ALTER TABLE skills ADD COLUMN pack_skill_key VARCHAR(128)"
        )
    for stmt in statements:
        sync_conn.execute(text(stmt))
        logger.info("schema_column_added", sql=stmt)


def _ensure_message_trace_column(sync_conn) -> None:
    """Add execution_trace to messages for chat UI step timeline."""
    insp = inspect(sync_conn)
    if "messages" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("messages")}
    if "execution_trace" in cols:
        return
    dialect = sync_conn.dialect.name
    if dialect == "sqlite":
        stmt = "ALTER TABLE messages ADD COLUMN execution_trace JSON"
    else:
        stmt = "ALTER TABLE messages ADD COLUMN execution_trace JSONB"
    sync_conn.execute(text(stmt))
    logger.info("schema_column_added", sql=stmt)


def _ensure_chat_mode_columns(sync_conn) -> None:
    """Add conversations.mode_id on DBs created before chat modes existed."""
    insp = inspect(sync_conn)
    if "conversations" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("conversations")}
    if "mode_id" in cols:
        return
    dialect = sync_conn.dialect.name
    if dialect == "sqlite":
        stmt = "ALTER TABLE conversations ADD COLUMN mode_id VARCHAR(36)"
    else:
        stmt = (
            "ALTER TABLE conversations ADD COLUMN mode_id VARCHAR(36) "
            "REFERENCES chat_modes(id) ON DELETE SET NULL"
        )
    sync_conn.execute(text(stmt))
    logger.info("schema_column_added", sql=stmt)


def _ensure_knowledge_memory_column(sync_conn) -> None:
    """Add chat_modes.use_knowledge_memory on DBs created before Phase 3."""
    insp = inspect(sync_conn)
    if "chat_modes" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("chat_modes")}
    if "use_knowledge_memory" in cols:
        return
    dialect = sync_conn.dialect.name
    if dialect == "sqlite":
        stmt = (
            "ALTER TABLE chat_modes ADD COLUMN use_knowledge_memory "
            "BOOLEAN NOT NULL DEFAULT 0"
        )
    else:
        stmt = (
            "ALTER TABLE chat_modes ADD COLUMN use_knowledge_memory "
            "BOOLEAN NOT NULL DEFAULT FALSE"
        )
    sync_conn.execute(text(stmt))
    logger.info("schema_column_added", sql=stmt)


def _ensure_structured_memory_columns(sync_conn) -> None:
    """Summaries + field_key + memory_fields for open-vocabulary LTM."""
    insp = inspect(sync_conn)
    dialect = sync_conn.dialect.name
    tables = set(insp.get_table_names())
    if "user_memories" in tables:
        cols = {c["name"] for c in insp.get_columns("user_memories")}
        for name in ("persona_summary", "knowledge_summary"):
            if name in cols:
                continue
            stmt = f"ALTER TABLE user_memories ADD COLUMN {name} TEXT NOT NULL DEFAULT ''"
            sync_conn.execute(text(stmt))
            logger.info("schema_column_added", sql=stmt)
    if "memory_items" in tables:
        cols = {c["name"] for c in insp.get_columns("memory_items")}
        if "field_key" not in cols:
            stmt = (
                "ALTER TABLE memory_items ADD COLUMN field_key "
                "VARCHAR(80) NOT NULL DEFAULT ''"
            )
            sync_conn.execute(text(stmt))
            logger.info("schema_column_added", sql=stmt)
            sync_conn.execute(
                text(
                    "UPDATE memory_items SET field_key = category "
                    "WHERE field_key = '' OR field_key IS NULL"
                )
            )
    if "memory_fields" in tables:
        return
    ts = "DATETIME" if dialect == "sqlite" else "TIMESTAMPTZ"
    sync_conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS memory_fields ("
            "id VARCHAR(36) PRIMARY KEY, "
            "user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
            f"lane VARCHAR(16) NOT NULL, "
            "field_key VARCHAR(80) NOT NULL, "
            "name VARCHAR(80) NOT NULL DEFAULT '', "
            "description TEXT NOT NULL DEFAULT '', "
            f"created_at {ts} NOT NULL, "
            f"updated_at {ts} NOT NULL, "
            "UNIQUE (user_id, lane, field_key)"
            ")"
        )
    )
    sync_conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_memory_fields_user_lane "
            "ON memory_fields (user_id, lane)"
        )
    )
    logger.info("schema_table_added", table="memory_fields")


def _ensure_conversation_title_auto(sync_conn) -> None:
    """Track whether Nous may still rewrite the conversation title."""
    insp = inspect(sync_conn)
    if "conversations" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("conversations")}
    if "title_auto" in cols:
        return
    dialect = sync_conn.dialect.name
    if dialect == "sqlite":
        stmt = (
            "ALTER TABLE conversations ADD COLUMN title_auto "
            "BOOLEAN NOT NULL DEFAULT 1"
        )
    else:
        stmt = (
            "ALTER TABLE conversations ADD COLUMN title_auto "
            "BOOLEAN NOT NULL DEFAULT TRUE"
        )
    sync_conn.execute(text(stmt))
    logger.info("schema_column_added", sql=stmt)


def _ensure_conversation_todos_column(sync_conn) -> None:
    """Add conversations.todos for the session-owned todo_write list."""
    insp = inspect(sync_conn)
    if "conversations" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("conversations")}
    if "todos" in cols:
        return
    dialect = sync_conn.dialect.name
    stmt = (
        "ALTER TABLE conversations ADD COLUMN todos JSON"
        if dialect == "sqlite"
        else "ALTER TABLE conversations ADD COLUMN todos JSONB"
    )
    sync_conn.execute(text(stmt))
    logger.info("schema_column_added", sql=stmt)


async def ensure_default_user(session: AsyncSession) -> User:
    """Idempotently return the local dev user, creating it on first call."""
    external_id = settings.default_user_external_id
    result = await session.execute(select(User).where(User.external_id == external_id))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(external_id=external_id, display_name="Local User")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info("default_user_created", user_id=user.id, external_id=external_id)
    return user


async def init_database() -> None:
    """Full startup routine: tables + seed data."""
    if settings.db_auto_create:
        await create_tables()
    async with SessionFactory() as session:
        await ensure_default_user(session)
        from app.services.chat_mode_service import ensure_builtin_modes

        await ensure_builtin_modes(session)
