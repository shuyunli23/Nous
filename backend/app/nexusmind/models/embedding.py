"""知识向量索引 —— 本地语义检索（Phase 7）。

默认使用特征哈希 + jieba 分词，无需外置 Embedding / Milvus / Chroma。
向量以 JSON 浮点数组落在 SQLite，接口层可替换为远程 embedding。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.nexusmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeEmbedding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_embedding"

    knowledge_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # 归一化后的稠密向量（特征哈希）
    vector: Mapped[list[float]] = mapped_column(JSON, nullable=False, default=list)
    dim: Mapped[int] = mapped_column(Integer, nullable=False, default=384)
    # local_hash | remote_openai（预留）
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="local_hash")
    # 内容指纹，避免重复计算
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    # 可选：远程模型名
    model_name: Mapped[str | None] = mapped_column(String(128), default=None)
