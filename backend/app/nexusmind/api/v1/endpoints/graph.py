"""知识图谱 API。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.nexusmind.api.deps import DBSession
from app.nexusmind.config.features import FEATURES
from app.nexusmind.schemas.graph import GraphEdge, GraphNode, GraphResponse, GraphStats
from app.nexusmind.services import graph_service
from app.nexusmind.utils.errors import ValidationError

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=GraphResponse, summary="获取知识图谱")
def get_graph(
    db: DBSession,
    max_keywords: int = Query(default=48, ge=5, le=120),
    max_knowledge: int = Query(default=60, ge=5, le=150),
    min_keyword_usage: int = Query(default=1, ge=0, le=50),
) -> GraphResponse:
    if not FEATURES.get("knowledge_graph"):
        raise ValidationError("知识图谱尚未启用")

    data = graph_service.build_knowledge_graph(
        db,
        max_keywords=max_keywords,
        max_knowledge=max_knowledge,
        min_keyword_usage=min_keyword_usage,
    )
    return GraphResponse(
        nodes=[GraphNode.model_validate(n) for n in data["nodes"]],
        edges=[GraphEdge.model_validate(e) for e in data["edges"]],
        stats=GraphStats.model_validate(data["stats"]),
    )
