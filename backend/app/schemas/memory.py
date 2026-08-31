"""Long-term memory API schemas (persona vs knowledge lanes)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MemoryItemRead(BaseModel):
    id: str = ""
    field_key: str = ""
    category: str
    item_key: str
    title: str = ""
    value: str = ""
    pinned: bool = False


class MemoryFieldRead(BaseModel):
    field_key: str
    name: str = ""
    description: str = ""
    items: list[MemoryItemRead] = Field(default_factory=list)


class MemoryLaneRead(BaseModel):
    empty: bool = True
    rendered: str = ""
    summary: str = ""
    fields: list[MemoryFieldRead] = Field(default_factory=list)
    items: list[MemoryItemRead] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class UserMemoryRead(BaseModel):
    persona: MemoryLaneRead
    knowledge: MemoryLaneRead


class MemoryClearRequest(BaseModel):
    lane: Literal["persona", "knowledge", "all"] = "all"
