"""AI 助手 Schema。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str = Field(..., min_length=1, max_length=8000)


class AssistantAskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    history: list[ChatMessage] = Field(default_factory=list)
    model_id: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=12)


class CitationOut(BaseModel):
    id: str
    title: str
    summary: str | None = None
    score: float = 0
    match_fields: list[str] = Field(default_factory=list)


class AssistantAskResponse(BaseModel):
    answer: str
    citations: list[CitationOut] = Field(default_factory=list)
    source: Literal["ai", "local"] = "local"
    model: str | None = None
    latency_ms: int | None = None
    execution_trace: list[dict[str, Any]] = Field(default_factory=list)
