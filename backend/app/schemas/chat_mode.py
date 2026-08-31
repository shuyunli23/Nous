"""Chat mode API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ChatModeRead(ORMModel):
    id: str
    key: str
    name: str
    description: str = ""
    system_prompt: str = ""
    tool_policy: str
    use_long_term_memory: bool = False
    use_knowledge_memory: bool = False
    is_builtin: bool = False
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChatModeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    system_prompt: str = Field(min_length=1, max_length=16000)
    description: str = Field(default="", max_length=400)
    use_long_term_memory: bool = False
    use_knowledge_memory: bool = False


class ChatModeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=16000)
    description: str | None = Field(default=None, max_length=400)
    use_long_term_memory: bool | None = None
    use_knowledge_memory: bool | None = None
