"""数据库引擎、会话工厂与初始化逻辑。"""

from __future__ import annotations

import logging
from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.nexusmind.config import settings
from app.nexusmind.db.base import Base

logger = logging.getLogger(__name__)

_is_sqlite = settings.database_url.startswith("sqlite")

engine: Engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    # SQLite 默认禁止跨线程复用连接，而 FastAPI 会在线程池中执行同步依赖
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
    """SQLite 连接级 PRAGMA。

    - foreign_keys: SQLite 默认不强制外键，需要显式打开才能让级联删除生效
    - journal_mode=WAL: 提升读写并发，避免阅读时被写操作阻塞
    """
    if not _is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def init_db() -> None:
    """建表。

    当前阶段用 `create_all` 足够；后续如需字段演进再引入 Alembic 迁移。
    """
    settings.ensure_dirs()
    # 必须先 import 全部模型，元数据里才有对应的表定义
    from app.nexusmind import models  # noqa: F401  pylint: disable=unused-import

    Base.metadata.create_all(bind=engine)
    logger.info("Database ready at %s", settings.database_url)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """脚本 / 后台任务中使用的事务上下文。"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
