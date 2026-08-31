"""Skill API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.database.models.enums import SkillSource, SkillStatus
from app.schemas.common import ORMModel


# ── Skill read schemas ────────────────────────────────────────────────────

class WorkflowStep(BaseModel):
    step: int
    action: str
    command: str | None = None
    expect: str | None = None


class SkillSummary(ORMModel):
    """List-view projection."""
    id: str
    user_id: str
    name: str
    description: str
    status: str
    source: str
    confidence: float
    version: int
    usage_count: int
    success_rate: float | None = None
    trigger_keywords: list[str] = Field(default_factory=list)
    trigger_intent: str | None = None
    created_at: datetime
    updated_at: datetime
    created_from_conversation_id: str | None = None


class SkillDetail(SkillSummary):
    """Full skill with all fields."""
    instruction: str
    workflow: list[dict[str, Any]] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    last_used_at: datetime | None = None
    embedding_hash: str | None = None


# ── Write schemas ────────────────────────────────────────────────────────

class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    instruction: str = ""
    trigger_keywords: list[str] = Field(default_factory=list)
    trigger_intent: str | None = None
    workflow: list[dict[str, Any]] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    instruction: str | None = None
    trigger_keywords: list[str] | None = None
    trigger_intent: str | None = None
    workflow: list[dict[str, Any]] | None = None
    examples: list[dict[str, Any]] | None = None
    tools: list[str] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class SkillStatusPatch(BaseModel):
    status: SkillStatus


# ── Extraction ───────────────────────────────────────────────────────────

class GenerateSkillRequest(BaseModel):
    conversation_id: str
    force: bool = False   # re-extract even if status=done


class GenerateSkillResponse(BaseModel):
    conversation_id: str
    extraction_status: str
    skill_id: str | None = None      # set when a skill was created
    merged_into: str | None = None   # set when deduped into existing skill
    skipped: bool = False
    reason: str | None = None


# ── Feedback ─────────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    feedback: str = Field(pattern="^(positive|negative)$")
    message_id: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)
    status: SkillStatus | None = None


# ── Import / packs ────────────────────────────────────────────────────────


class SkillImportItem(BaseModel):
    """One skill inside an import pack (Claude/WorkBuddy-style playbook)."""

    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    instruction: str = ""
    trigger_keywords: list[str] = Field(default_factory=list)
    trigger_intent: str | None = None
    workflow: list[dict[str, Any]] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class SkillPackImport(BaseModel):
    """Import a named pack of skills (JSON body or built-in pack id)."""

    pack_id: str | None = Field(
        default=None,
        description="Built-in pack id, e.g. nous-research. Mutually exclusive with skills.",
    )
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    skills: list[SkillImportItem] = Field(default_factory=list)
    activate: bool = Field(
        default=True,
        description="If true, imported skills are active; otherwise draft.",
    )
    skip_duplicates: bool = Field(
        default=True,
        description="Skip skills whose name already exists for this user.",
    )


class SkillImportResult(BaseModel):
    pack_id: str | None = None
    pack_name: str | None = None
    created: list[SkillSummary] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    total_created: int = 0
    total_skipped: int = 0
