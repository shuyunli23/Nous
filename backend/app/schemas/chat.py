"""Chat API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32000)
    conversation_id: str | None = None   # None → create new conversation
    mode_id: str | None = None           # only used when creating a conversation
    provider_id: str | None = None       # saved provider for this turn; else Settings route


class SkillUsedInfo(BaseModel):
    id: str
    name: str
    similarity: float | None = None


class ChatModeRef(BaseModel):
    id: str
    key: str
    name: str
    tool_policy: str
    use_long_term_memory: bool = False
    use_knowledge_memory: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str          # assistant message id
    answer: str
    used_skills: list[SkillUsedInfo] = Field(default_factory=list)
    token_usage: dict[str, Any] | None = None
    title: str | None = None   # current conversation title (updated on first turn)
    execution_trace: list[dict[str, Any]] | None = None
    mode: ChatModeRef | None = None
