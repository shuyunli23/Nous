"""检索相关 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.nexusmind.schemas.knowledge import KeywordOut


SearchMode = Literal["keyword", "fulltext", "hybrid", "vector"]


class SearchHit(BaseModel):
    """单条检索结果。"""

    id: str
    title: str
    summary: str | None = None
    category: str | None = None
    is_favorite: bool = False
    is_important: bool = False
    word_count: int = 0
    reading_minutes: int = 0
    analysis_status: str = "pending"
    attachment_count: int = 0
    keywords: list[KeywordOut] = Field(default_factory=list)
    created_time: datetime
    updated_time: datetime

    # 检索元信息
    score: float = 0
    match_fields: list[str] = Field(default_factory=list)
    snippet: str | None = None
    matched_keywords: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode = "hybrid"
    total: int = 0
    page: int = 1
    page_size: int = 20
    items: list[SearchHit] = Field(default_factory=list)
    # 扩展点说明，前端可展示
    note: str | None = None


class KeywordStatOut(BaseModel):
    id: str
    name: str
    slug: str
    usage_count: int
    # 可选：该关键词下最近更新的知识标题
    sample_title: str | None = None
