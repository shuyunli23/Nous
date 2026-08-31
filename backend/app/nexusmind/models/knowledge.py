"""知识条目模型 —— 系统的核心实体。"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.nexusmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.nexusmind.models.associations import knowledge_keyword

if TYPE_CHECKING:  # 仅用于类型标注，避免运行时循环导入
    from app.nexusmind.models.attachment import Attachment
    from app.nexusmind.models.keyword import Keyword


class KnowledgeSource(StrEnum):
    """知识条目的产生方式。"""

    MANUAL = "manual"      # 在编辑器里手写
    IMPORT = "import"      # 导入 .md 文件
    ARCHIVE = "archive"    # 导入 .md + 附件压缩包
    CHAT_DRAFT = "chat_draft"  # 学习会话抽出的待导入草稿
    CHAT = "chat"          # 用户确认导入后的学习笔记


class AnalysisStatus(StrEnum):
    """AI 分析状态机（Phase 4 使用，Phase 1 先建好字段）。"""

    PENDING = "pending"      # 尚未分析
    RUNNING = "running"      # 正在分析
    DONE = "done"            # LLM 分析成功
    FALLBACK = "fallback"    # 未配置模型或调用失败，已用本地算法兜底
    FAILED = "failed"        # 彻底失败


class Knowledge(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """一条知识 = Markdown 原文 + AI 提炼出的结构化元信息 + 附件。"""

    __tablename__ = "knowledge"

    # ------------------------------------------------------------ 内容
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 去掉 Markdown 语法后的纯文本，供全文检索使用（Phase 5）
    plain_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # ------------------------------------------------------------ 组织
    category: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_important: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # ------------------------------------------------------------ 来源
    source_type: Mapped[str] = mapped_column(
        String(16), default=KnowledgeSource.MANUAL.value, nullable=False
    )
    source_filename: Mapped[str | None] = mapped_column(String(255), default=None)

    # ------------------------------------------------------------ 解析产物
    # Markdown 结构化解析结果：标题树、代码块语言、图片/链接/表格统计等
    # 形如 {"toc": [...], "code_languages": [...], "counts": {...}}
    outline: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reading_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ------------------------------------------------------------ AI
    analysis_status: Mapped[str] = mapped_column(
        String(16), default=AnalysisStatus.PENDING.value, nullable=False, index=True
    )
    analysis_error: Mapped[str | None] = mapped_column(Text, default=None)
    # 记录本次分析使用的模型，便于回溯 "这条摘要是谁生成的"
    analyzed_by_model: Mapped[str | None] = mapped_column(String(128), default=None)

    # ------------------------------------------------------------ 扩展
    # 属性名不能叫 metadata（SQLAlchemy 声明式基类保留字），列名保持业务语义
    extra_meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    # ------------------------------------------------------------ 关系
    keywords: Mapped[list["Keyword"]] = relationship(
        secondary=knowledge_keyword,
        back_populates="knowledge_items",
        lazy="selectin",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="knowledge",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Attachment.created_time",
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"<Knowledge id={self.id[:8]} title={self.title!r}>"
