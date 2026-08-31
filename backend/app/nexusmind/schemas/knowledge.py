"""知识条目相关 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.nexusmind.schemas.attachment import AttachmentOut


class KeywordOut(BaseModel):
    """列表/详情中嵌套的关键词摘要。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    usage_count: int = 0


class KnowledgeCreate(BaseModel):
    """手动创建笔记。"""

    title: str = Field(..., min_length=1, max_length=255)
    markdown_content: str = ""
    summary: str | None = None
    category: str | None = Field(default=None, max_length=64)
    is_favorite: bool = False
    is_important: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        title = v.strip()
        if not title:
            raise ValueError("标题不能为空")
        return title

    @field_validator("category")
    @classmethod
    def _normalize_category(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned or None


class KnowledgeUpdate(BaseModel):
    """部分更新；未传字段保持不变。"""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    markdown_content: str | None = None
    summary: str | None = None
    category: str | None = Field(default=None, max_length=64)
    is_favorite: bool | None = None
    is_important: bool | None = None
    is_archived: bool | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        title = v.strip()
        if not title:
            raise ValueError("标题不能为空")
        return title

    @field_validator("category")
    @classmethod
    def _normalize_category(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned or None


class KnowledgeSummary(BaseModel):
    """列表卡片用的轻量视图（不含正文）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    summary: str | None = None
    category: str | None = None
    is_favorite: bool = False
    is_important: bool = False
    is_archived: bool = False
    source_type: str
    source_filename: str | None = None
    word_count: int = 0
    reading_minutes: int = 0
    analysis_status: str
    attachment_count: int = 0
    keywords: list[KeywordOut] = Field(default_factory=list)
    created_time: datetime
    updated_time: datetime


class KnowledgeDetail(BaseModel):
    """详情：含 Markdown 原文、大纲、附件。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    summary: str | None = None
    markdown_content: str
    category: str | None = None
    is_favorite: bool = False
    is_important: bool = False
    is_archived: bool = False
    source_type: str
    source_filename: str | None = None
    outline: dict[str, Any] = Field(default_factory=dict)
    word_count: int = 0
    reading_minutes: int = 0
    analysis_status: str
    analysis_error: str | None = None
    analyzed_by_model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_meta")
    keywords: list[KeywordOut] = Field(default_factory=list)
    attachments: list[AttachmentOut] = Field(default_factory=list)
    created_time: datetime
    updated_time: datetime


class KnowledgeImportResult(BaseModel):
    """导入结果。"""

    knowledge: KnowledgeDetail
    imported_attachments: int = 0
    warnings: list[str] = Field(default_factory=list)


class CategoryStat(BaseModel):
    name: str
    count: int
