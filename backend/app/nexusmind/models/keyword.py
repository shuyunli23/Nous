"""关键词模型 —— 知识检索的索引层。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.nexusmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.nexusmind.models.associations import knowledge_keyword

if TYPE_CHECKING:
    from app.nexusmind.models.knowledge import Knowledge


def normalize_keyword(raw: str) -> str:
    """归一化关键词，用于去重。

    大小写不敏感（Vue3 / vue3 视为同一个），并压缩首尾空白。
    中文不受影响。
    """
    return " ".join(raw.strip().split()).lower()


class Keyword(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """全局唯一的关键词。多条知识共享同一个关键词实体。"""

    __tablename__ = "keyword"

    # 展示用原文，保留用户/LLM 给出的大小写，例如 "Vue3"
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 归一化后的唯一键，例如 "vue3"
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    # 反范式的引用计数，用于「热门标签」展示，避免每次 COUNT 关联表
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)

    knowledge_items: Mapped[list["Knowledge"]] = relationship(
        secondary=knowledge_keyword,
        back_populates="keywords",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Keyword {self.name} x{self.usage_count}>"
