"""Conversation endpoints: history, detail, delete, close, capture."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, status
from fastapi.responses import StreamingResponse

from app.chat_modes.catalog import COMPANION, TUTOR, WORKBENCH
from app.core.deps import CurrentUser, PaginationDep, SessionDep
from app.core.exceptions import AppError, ValidationError
from app.core.logging import get_logger
from app.database.models.enums import ConversationStatus, ExtractionStatus
from app.memory.facts import LANE_PERSONA
from app.schemas.common import Page
from app.schemas.conversation import (
    ConversationCaptureResult,
    ConversationCloseResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdate,
    NoteExtractResult,
    SettleProposal,
    SettleRunRequest,
)
from app.services.conversation_service import ConversationService, mode_fields

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post(
    "",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create an empty conversation",
)
async def create_conversation(
    payload: ConversationCreate,
    session: SessionDep,
    user: CurrentUser,
) -> ConversationSummary:
    service = ConversationService(session)
    conversation = await service.create(
        user_id=user.id, title=payload.title, mode_id=payload.mode_id
    )
    return ConversationSummary.from_orm(
        conversation, message_count=0, **mode_fields(conversation)
    )


@router.get("", response_model=Page[ConversationSummary], summary="List conversations")
async def list_conversations(
    session: SessionDep,
    user: CurrentUser,
    pagination: PaginationDep,
    conversation_status: Annotated[ConversationStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=128)] = None,
) -> Page[ConversationSummary]:
    service = ConversationService(session)
    return await service.list_page(
        user_id=user.id,
        limit=pagination.limit,
        offset=pagination.offset,
        status=conversation_status,
        search=search,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
    summary="Full conversation context",
)
async def get_conversation(
    conversation_id: str,
    session: SessionDep,
    user: CurrentUser,
) -> ConversationDetail:
    service = ConversationService(session)
    return await service.get_detail(conversation_id, user_id=user.id)


@router.patch(
    "/{conversation_id}",
    response_model=ConversationSummary,
    summary="Rename or change conversation status",
)
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> ConversationSummary:
    service = ConversationService(session)
    conversation = await service.update(
        conversation_id, user_id=user.id, title=payload.title, status=payload.status
    )
    count = await service.repo.count_messages(conversation_id)
    return ConversationSummary.from_orm(
        conversation, message_count=count, **mode_fields(conversation)
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a conversation and its messages",
)
async def delete_conversation(
    conversation_id: str,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    service = ConversationService(session)
    await service.delete(conversation_id, user_id=user.id)


@router.post(
    "/{conversation_id}/close",
    response_model=ConversationCloseResponse,
    summary="Close a conversation and trigger the mode's settle action",
)
async def close_conversation(
    conversation_id: str,
    session: SessionDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> ConversationCloseResponse:
    """Workbench extracts a Skill. Tutor queues notes + knowledge. Companion updates persona."""
    from app.core.config import settings
    from app.database.session import session_scope
    from app.services.memory_service import run_memory_refresh_task, writes_persona
    from app.services.skill_service import SkillService

    conv_service = ConversationService(session)
    conversation = await conv_service.mark_closed(conversation_id, user_id=user.id)

    triggered = False
    pending = conversation.extraction_status == ExtractionStatus.PENDING.value
    if settings.extraction_enabled and pending:

        async def _bg_extract(cid: str, uid: str) -> None:
            async with session_scope() as bg_session:
                svc = SkillService(bg_session)
                await svc.generate_from_conversation(cid, user_id=uid)

        background_tasks.add_task(_bg_extract, conversation.id, user.id)
        triggered = True

    notes_triggered = False
    memory_triggered = False
    mode = getattr(conversation, "mode", None)
    if mode is not None and writes_persona(mode):

        async def _bg_memory(cid: str, uid: str, mid: str) -> None:
            await run_memory_refresh_task(uid, cid, mid, True)

        background_tasks.add_task(_bg_memory, conversation.id, user.id, mode.id)
        memory_triggered = True
    if mode is not None and mode.key == TUTOR:

        async def _bg_notes(cid: str, uid: str) -> None:
            from app.services.note_extract_service import extract_tutor_notes

            async with session_scope() as bg_session:
                await extract_tutor_notes(bg_session, cid, user_id=uid)

        background_tasks.add_task(_bg_notes, conversation.id, user.id)
        notes_triggered = True

    if triggered:
        detail = "Skill extraction scheduled."
    elif notes_triggered:
        detail = "Study notes and knowledge background queued."
    elif memory_triggered:
        detail = "Companion profile update queued."
    else:
        detail = "Closed without updating profiles."

    return ConversationCloseResponse(
        conversation_id=conversation.id,
        status=ConversationStatus(conversation.status),
        extraction_status=ExtractionStatus(conversation.extraction_status),
        extraction_triggered=triggered,
        notes_triggered=notes_triggered,
        memory_triggered=memory_triggered,
        detail=detail,
    )


@router.post(
    "/{conversation_id}/extract-notes",
    response_model=NoteExtractResult,
    summary="Extract tutor notes into the NexusMind pending-import inbox",
)
async def extract_notes(
    conversation_id: str,
    session: SessionDep,
    user: CurrentUser,
    force: bool = Query(default=False),
) -> NoteExtractResult:
    from app.services.note_extract_service import extract_tutor_notes

    return await extract_tutor_notes(
        session, conversation_id, user_id=user.id, force=force
    )


@router.post(
    "/{conversation_id}/capture",
    response_model=ConversationCaptureResult,
    summary="Settle this chat: Skill, knowledge notes, or companion preferences",
)
async def capture_conversation(
    conversation_id: str,
    session: SessionDep,
    user: CurrentUser,
    force: bool = Query(default=False),
) -> ConversationCaptureResult:
    from app.services.memory_service import UserMemoryService
    from app.services.note_extract_service import extract_tutor_notes
    from app.services.skill_service import SkillService

    conv_service = ConversationService(session)
    conversation = await conv_service.get_or_404(conversation_id, user_id=user.id)
    mode = getattr(conversation, "mode", None)
    key = mode.key if mode is not None else WORKBENCH

    if key == WORKBENCH:
        result = await SkillService(session).generate_from_conversation(
            conversation_id, user_id=user.id, force=True
        )
        return ConversationCaptureResult(
            kind="skill",
            conversation_id=conversation_id,
            skill_id=result.skill_id,
            merged_into=result.merged_into,
            skipped=result.skipped,
            reason=result.reason,
            detail=result.reason,
        )

    if key == TUTOR:
        notes = await extract_tutor_notes(
            session, conversation_id, user_id=user.id, force=force
        )
        return ConversationCaptureResult(
            kind="knowledge",
            conversation_id=conversation_id,
            skipped=notes.skipped and not notes.memory_updated,
            reason=notes.reason,
            notes=notes.notes,
            notes_skipped=notes.skipped,
            memory_updated=notes.memory_updated,
        )

    if key == COMPANION:
        updated = await UserMemoryService(session).update_from_conversation(
            user_id=user.id,
            conversation_id=conversation_id,
            lane=LANE_PERSONA,
        )
        return ConversationCaptureResult(
            kind="persona",
            conversation_id=conversation_id,
            skipped=not updated,
            memory_updated=updated,
            reason=None if updated else "nothing_to_save",
        )

    raise ValidationError("该模式不沉淀 Skill 或档案。")


@router.post(
    "/{conversation_id}/settle/propose",
    response_model=SettleProposal,
    summary="Recommend what this chat is worth settling as",
)
async def propose_conversation_settle(
    conversation_id: str,
    session: SessionDep,
    user: CurrentUser,
) -> SettleProposal:
    from app.services.settle_service import propose_settle

    return await propose_settle(session, conversation_id, user_id=user.id)


@router.post(
    "/{conversation_id}/settle/run",
    summary="Write the settle kinds the user confirmed",
)
async def run_conversation_settle(
    conversation_id: str,
    payload: SettleRunRequest,
    session: SessionDep,
    user: CurrentUser,
) -> StreamingResponse:
    from app.services.settle_service import run_settle_events

    async def events() -> AsyncIterator[str]:
        try:
            async for item in run_settle_events(
                session,
                conversation_id,
                user_id=user.id,
                kinds=payload.kinds,
                grant_permissions=payload.grant_permissions,
            ):
                yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"
        except AppError as exc:
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("settle_run_failed", error=str(exc))
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "code": "internal_error",
                        "message": "Unexpected server error.",
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
