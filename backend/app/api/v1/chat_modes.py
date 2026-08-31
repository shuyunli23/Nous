"""POST /api/v1/chat-modes — built-in + custom conversation modes."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.chat_mode import ChatModeCreate, ChatModeRead, ChatModeUpdate
from app.schemas.common import OkResponse
from app.services.chat_mode_service import ChatModeService

router = APIRouter(prefix="/chat-modes", tags=["chat-modes"])


@router.get("", response_model=list[ChatModeRead], summary="List chat modes")
async def list_chat_modes(
    session: SessionDep,
    user: CurrentUser,
) -> list[ChatModeRead]:
    svc = ChatModeService(session)
    modes = await svc.list_for_user(user.id)
    return [ChatModeRead.model_validate(m) for m in modes]


@router.post(
    "",
    response_model=ChatModeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom chat mode",
)
async def create_chat_mode(
    payload: ChatModeCreate,
    session: SessionDep,
    user: CurrentUser,
) -> ChatModeRead:
    svc = ChatModeService(session)
    mode = await svc.create_custom(
        user_id=user.id,
        name=payload.name,
        system_prompt=payload.system_prompt,
        use_long_term_memory=payload.use_long_term_memory,
        use_knowledge_memory=payload.use_knowledge_memory,
        description=payload.description,
    )
    return ChatModeRead.model_validate(mode)


@router.patch(
    "/{mode_id}",
    response_model=ChatModeRead,
    summary="Update a custom chat mode (or the knowledge-memory toggle on tutor/companion)",
)
async def update_chat_mode(
    mode_id: str,
    payload: ChatModeUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> ChatModeRead:
    svc = ChatModeService(session)
    mode = await svc.update_custom(
        mode_id,
        user_id=user.id,
        name=payload.name,
        system_prompt=payload.system_prompt,
        use_long_term_memory=payload.use_long_term_memory,
        use_knowledge_memory=payload.use_knowledge_memory,
        description=payload.description,
    )
    return ChatModeRead.model_validate(mode)


@router.delete(
    "/{mode_id}",
    response_model=OkResponse,
    summary="Delete a custom chat mode",
)
async def delete_chat_mode(
    mode_id: str,
    session: SessionDep,
    user: CurrentUser,
) -> OkResponse:
    svc = ChatModeService(session)
    await svc.delete_custom(mode_id, user_id=user.id)
    return OkResponse(ok=True)
