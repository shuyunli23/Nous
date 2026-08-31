"""知识检索 API。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.nexusmind.api.deps import DBSession, Pagination
from app.nexusmind.config.features import FEATURES
from app.nexusmind.schemas.common import MessageResponse
from app.nexusmind.schemas.knowledge import KeywordOut
from app.nexusmind.schemas.search import KeywordStatOut, SearchHit, SearchResponse
from app.nexusmind.services import embedding_service, search_service
from app.nexusmind.utils.errors import ValidationError

router = APIRouter(prefix="/search", tags=["search"])


def _to_hit(scored) -> SearchHit:  # noqa: ANN001
    item = scored.knowledge
    return SearchHit(
        id=item.id,
        title=item.title,
        summary=item.summary,
        category=item.category,
        is_favorite=item.is_favorite,
        is_important=item.is_important,
        word_count=item.word_count,
        reading_minutes=item.reading_minutes,
        analysis_status=item.analysis_status,
        attachment_count=len(item.attachments or []),
        keywords=[KeywordOut.model_validate(k) for k in (item.keywords or [])],
        created_time=item.created_time,
        updated_time=item.updated_time,
        score=round(scored.score, 2),
        match_fields=sorted(scored.match_fields),
        snippet=scored.snippet,
        matched_keywords=scored.matched_keywords,
    )


@router.get("", response_model=SearchResponse, summary="搜索知识")
def search(
    db: DBSession,
    pagination: Pagination,
    q: str = Query(..., min_length=1, description="搜索词，如 Vue"),
    mode: str = Query(
        default="hybrid",
        description="keyword | fulltext | hybrid | vector",
    ),
    category: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
) -> SearchResponse:
    items, total, note = search_service.search_knowledge(
        db,
        q=q,
        mode=mode,
        page=pagination.page,
        page_size=pagination.page_size,
        category=category,
        include_archived=include_archived,
    )
    return SearchResponse(
        query=q.strip(),
        mode=mode,  # type: ignore[arg-type]
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        items=[_to_hit(i) for i in items],
        note=note,
    )


@router.post(
    "/embeddings/rebuild",
    response_model=MessageResponse,
    summary="重建语义向量索引",
)
def rebuild_embeddings(db: DBSession) -> MessageResponse:
    if not FEATURES.get("vector_search"):
        raise ValidationError("语义检索尚未启用（vector_search）")
    stats = embedding_service.rebuild_all(db)
    return MessageResponse(
        message=(
            f"已重建向量索引：indexed={stats['indexed']}, "
            f"removed={stats['removed']}, total={stats['total_knowledge']}"
        )
    )


@router.get("/keywords/hot", response_model=list[KeywordStatOut], summary="热门关键词")
def hot_keywords(
    db: DBSession,
    limit: int = Query(default=24, ge=1, le=100),
) -> list[KeywordStatOut]:
    rows = search_service.list_hot_keywords(db, limit=limit)
    return [
        KeywordStatOut(
            id=kw.id,
            name=kw.name,
            slug=kw.slug,
            usage_count=kw.usage_count,
            sample_title=title,
        )
        for kw, title in rows
    ]


@router.get("/keywords/suggest", response_model=list[KeywordStatOut], summary="关键词联想")
def suggest_keywords(
    db: DBSession,
    q: str = Query(default="", description="前缀/片段，空则返回热门"),
    limit: int = Query(default=12, ge=1, le=50),
) -> list[KeywordStatOut]:
    items = search_service.suggest_keywords(db, q=q, limit=limit)
    return [
        KeywordStatOut(
            id=kw.id,
            name=kw.name,
            slug=kw.slug,
            usage_count=kw.usage_count,
            sample_title=None,
        )
        for kw in items
    ]
