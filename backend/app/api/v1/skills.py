"""Skill management endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.config import settings
from app.core.deps import CurrentUser, PaginationDep, SessionDep
from app.database.models.enums import SkillStatus
from app.llm.embeddings import active_provider
from app.memory.vector_store import get_vector_store
from app.schemas.common import OkResponse, Page
from app.schemas.skill import (
    FeedbackRequest,
    GenerateSkillRequest,
    GenerateSkillResponse,
    SearchRequest,
    SkillCreate,
    SkillDetail,
    SkillImportResult,
    SkillPackImport,
    SkillStatusPatch,
    SkillSummary,
    SkillUpdate,
)
from app.services.skill_service import SkillService
from app.skill.packs import get_builtin_pack, list_builtin_packs

router = APIRouter(prefix="/skills", tags=["skills"])


@router.post(
    "",
    response_model=SkillDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Manually create a skill",
)
async def create_skill(
    payload: SkillCreate,
    session: SessionDep,
    user: CurrentUser,
) -> SkillDetail:
    svc = SkillService(session)
    return await svc.create(user_id=user.id, payload=payload)


@router.get("", response_model=Page[SkillSummary], summary="List skills")
async def list_skills(
    session: SessionDep,
    user: CurrentUser,
    pagination: PaginationDep,
    skill_status: Annotated[SkillStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=128)] = None,
) -> Page[SkillSummary]:
    svc = SkillService(session)
    return await svc.list_page(
        user_id=user.id,
        limit=pagination.limit,
        offset=pagination.offset,
        status=skill_status,
        search=search,
    )


@router.get(
    "/packs",
    summary="List built-in skill packs (Claude/WorkBuddy-style)",
)
async def list_packs() -> dict:
    return {"items": list_builtin_packs(), "total": len(list_builtin_packs())}


@router.get(
    "/packs/{pack_id}",
    summary="Preview a built-in skill pack",
)
async def get_pack(pack_id: str) -> dict:
    pack = get_builtin_pack(pack_id)
    if pack is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError(f"Pack '{pack_id}' not found.")
    return pack


@router.post(
    "/import",
    response_model=SkillImportResult,
    summary="Import a skill pack (built-in id or inline JSON skills)",
)
async def import_skills(
    payload: SkillPackImport,
    session: SessionDep,
    user: CurrentUser,
) -> SkillImportResult:
    svc = SkillService(session)
    return await svc.import_pack(user_id=user.id, payload=payload)


@router.post(
    "/search",
    summary="Inspect hybrid retrieval results for a query",
)
async def search_skills(
    payload: SearchRequest,
    session: SessionDep,
    user: CurrentUser,
) -> dict:
    """Returns the score breakdown (vector vs keyword) for tuning thresholds."""
    svc = SkillService(session)
    results = await svc.search(
        user_id=user.id,
        query=payload.query,
        limit=payload.limit,
        status=payload.status,
    )
    return {
        "query": payload.query,
        "count": len(results),
        "embedding_provider": active_provider(),
        "results": results,
    }


@router.post(
    "/reindex",
    summary="Rebuild the vector index from the database",
)
async def reindex_skills(
    session: SessionDep,
    user: CurrentUser,
    force: Annotated[bool, Query()] = False,
) -> dict:
    svc = SkillService(session)
    stats = await svc.reindex(user_id=user.id, force=force)
    return {
        "ok": True,
        "vector_backend": settings.vector_backend,
        "embedding_provider": active_provider(),
        "indexed_total": get_vector_store().count(),
        **stats,
    }


@router.get("/{skill_id}", response_model=SkillDetail, summary="Get skill detail")
async def get_skill(
    skill_id: str,
    session: SessionDep,
    user: CurrentUser,
) -> SkillDetail:
    svc = SkillService(session)
    return await svc.get_or_404(skill_id, user_id=user.id)


@router.put("/{skill_id}", response_model=SkillDetail, summary="Update a skill")
async def update_skill(
    skill_id: str,
    payload: SkillUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> SkillDetail:
    svc = SkillService(session)
    return await svc.update(skill_id, payload, user_id=user.id)


@router.patch(
    "/{skill_id}/status",
    response_model=SkillDetail,
    summary="Change skill status (enable/disable/deprecate)",
)
async def patch_skill_status(
    skill_id: str,
    payload: SkillStatusPatch,
    session: SessionDep,
    user: CurrentUser,
) -> SkillDetail:
    svc = SkillService(session)
    return await svc.set_status(skill_id, payload.status, user_id=user.id)


@router.delete(
    "/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a skill",
)
async def delete_skill(
    skill_id: str,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    svc = SkillService(session)
    await svc.delete(skill_id, user_id=user.id)


@router.post(
    "/generate",
    response_model=GenerateSkillResponse,
    summary="Trigger skill extraction from a conversation",
)
async def generate_skill(
    payload: GenerateSkillRequest,
    session: SessionDep,
    user: CurrentUser,
) -> GenerateSkillResponse:
    """Phase 3: extraction runs in-band. Phase 5+ could move to background."""
    svc = SkillService(session)
    result = await svc.generate_from_conversation(
        payload.conversation_id,
        user_id=user.id,
        force=payload.force,
    )
    return GenerateSkillResponse(
        conversation_id=result.conversation_id,
        extraction_status=result.extraction_status,
        skill_id=result.skill_id,
        merged_into=result.merged_into,
        skipped=result.skipped,
        reason=result.reason,
    )


@router.post(
    "/{skill_id}/feedback",
    response_model=OkResponse,
    summary="Record usage feedback (positive/negative)",
)
async def skill_feedback(
    skill_id: str,
    payload: FeedbackRequest,
    session: SessionDep,
    user: CurrentUser,
) -> OkResponse:
    svc = SkillService(session)
    positive = payload.feedback == "positive"
    await svc.record_feedback(
        skill_id,
        user_id=user.id,
        positive=positive,
        message_id=payload.message_id,
    )
    return OkResponse(message=f"Feedback '{payload.feedback}' recorded.")
