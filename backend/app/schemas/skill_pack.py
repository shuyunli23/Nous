"""API schemas for nous-pack/2 install lifecycle."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.skill import SkillSummary


class PackSkillPreview(BaseModel):
    key: str
    name: str
    description: str = ""
    tools_local: list[str] = Field(default_factory=list)
    tools_local_exposed: list[str] = Field(default_factory=list)
    tools_builtin: list[str] = Field(default_factory=list)


class PackArchivePreview(BaseModel):
    format: str
    pack_id: str
    version: str
    name: str
    description: str = ""
    permissions_requested: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    skills: list[PackSkillPreview] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class PackToolSummary(ORMModel):
    id: str
    name: str
    exposed_name: str
    description: str
    enabled: bool
    skill_key: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class InstalledPackSummary(ORMModel):
    id: str
    pack_id: str
    version: str
    name: str
    description: str
    status: str
    permissions: list[str] = Field(default_factory=list)
    permissions_requested: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    content_hash: str
    created_at: datetime
    updated_at: datetime
    tool_count: int = 0
    skill_count: int = 0


class InstalledPackDetail(InstalledPackSummary):
    author: str | None = None
    license: str | None = None
    install_path: str
    tools: list[PackToolSummary] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)


class PackArchiveImportResult(BaseModel):
    pack: InstalledPackDetail
    created_skills: list[SkillSummary] = Field(default_factory=list)
    replaced_pack_id: str | None = None
    warnings: list[str] = Field(default_factory=list)


class PackStatusPatch(BaseModel):
    status: str = Field(pattern="^(active|disabled)$")
