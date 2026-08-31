"""Conversation and message API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.database.models.enums import ConversationStatus, ExtractionStatus
from app.schemas.common import ORMModel


class MessageRead(ORMModel):
    id: str
    seq: int = 0
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    token_usage: dict[str, Any] | None = None
    used_skill_ids: list[str] | None = None
    execution_trace: list[dict[str, Any]] | None = None
    created_at: datetime


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    mode_id: str | None = None


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    status: ConversationStatus | None = None


class ConversationSummary(ORMModel):
    """List-view projection: no messages, plus a cheap message count."""

    id: str
    user_id: str
    title: str
    status: str
    summary: str | None = None
    extraction_status: str
    message_count: int = 0
    mode_id: str | None = None
    mode_key: str | None = None
    mode_name: str | None = None
    token_total: int = 0
    created_time: datetime
    updated_time: datetime


class ConversationDetail(ConversationSummary):
    """Full context of a single conversation."""

    messages: list[MessageRead] = Field(default_factory=list)
    extraction_error: str | None = None


class ConversationCloseResponse(BaseModel):
    conversation_id: str
    status: ConversationStatus
    extraction_status: ExtractionStatus
    extraction_triggered: bool
    notes_triggered: bool = False
    memory_triggered: bool = False
    detail: str | None = None


class NoteRef(BaseModel):
    id: str
    title: str


class NoteExtractResult(BaseModel):
    conversation_id: str
    skipped: bool = False
    reason: str | None = None
    notes: list[NoteRef] = Field(default_factory=list)
    memory_updated: bool = False


class ConversationCaptureResult(BaseModel):
    kind: Literal["skill", "knowledge", "persona"]
    conversation_id: str
    skill_id: str | None = None
    merged_into: str | None = None
    skipped: bool = False
    reason: str | None = None
    notes: list[NoteRef] = Field(default_factory=list)
    notes_skipped: bool = False
    memory_updated: bool = False
    detail: str | None = None
