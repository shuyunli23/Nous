"""知识图谱 Schema。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    type: Literal["knowledge", "keyword", "category"]
    label: str
    weight: float = 1
    meta: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: Literal["has_keyword", "in_category", "co_occur"]
    weight: float = 1


class GraphStats(BaseModel):
    knowledge: int = 0
    keyword: int = 0
    category: int = 0
    edges: int = 0
    knowledge_in_db: int = 0


class GraphResponse(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    stats: GraphStats = Field(default_factory=GraphStats)
