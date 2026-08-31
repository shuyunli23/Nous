"""Turn a tutor conversation into NexusMind pending-import drafts."""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat_modes.catalog import TUTOR
from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.llm.client import structured_complete
from app.llm.prompts.extraction import format_conversation
from app.llm.prompts.note_extraction import NOTE_EXTRACT_SYSTEM, NOTE_EXTRACT_USER
from app.repositories.conversation_repo import ConversationRepository
from app.schemas.conversation import NoteExtractResult, NoteRef
from app.services.conversation_service import ConversationService

logger = get_logger(__name__)


class NoteDraft(BaseModel):
    title: str = ""
    summary: str = ""
    markdown: str = ""
    category: str | None = "学习"


class NotesLLMResult(BaseModel):
    worth_saving: bool = False
    reason: str = ""
    notes: list[NoteDraft] = Field(default_factory=list)


def _persist_drafts(
    *,
    conversation_id: str,
    conversation_title: str,
    drafts: list[NoteDraft],
) -> list[NoteRef]:
    from app.nexusmind.db.session import session_scope
    from app.nexusmind.services import knowledge_service

    created: list[NoteRef] = []
    with session_scope() as db:
        for draft in drafts:
            title = (draft.title or "").strip() or "学习笔记"
            body = (draft.markdown or "").strip()
            if not body:
                continue
            item = knowledge_service.create_chat_draft(
                db,
                title=title,
                markdown_content=body,
                summary=(draft.summary or "").strip() or None,
                category=(draft.category or "学习").strip() or "学习",
                conversation_id=conversation_id,
                conversation_title=conversation_title,
            )
            created.append(NoteRef(id=item.id, title=item.title))
    return created


def _existing_for_conversation(conversation_id: str) -> list[NoteRef]:
    from app.nexusmind.db.session import session_scope
    from app.nexusmind.services import knowledge_service

    with session_scope() as db:
        items = knowledge_service.list_for_conversation(db, conversation_id)
        return [NoteRef(id=item.id, title=item.title) for item in items]


async def _update_knowledge_memory(
    session: AsyncSession,
    *,
    user_id: str,
    conversation_id: str,
) -> bool:
    from app.memory.facts import LANE_KNOWLEDGE
    from app.services.memory_service import UserMemoryService

    svc = UserMemoryService(session)
    return await svc.update_from_conversation(
        user_id=user_id, conversation_id=conversation_id, lane=LANE_KNOWLEDGE
    )


async def extract_tutor_notes(
    session: AsyncSession,
    conversation_id: str,
    *,
    user_id: str,
    force: bool = False,
) -> NoteExtractResult:
    conv_svc = ConversationService(session)
    conversation = await conv_svc.get_or_404(conversation_id, user_id=user_id)
    mode = getattr(conversation, "mode", None)
    if mode is None or mode.key != TUTOR:
        raise ValidationError("只有学习模式的会话可以沉淀笔记。")

    existing = _existing_for_conversation(conversation_id)
    if existing and not force:
        memory_updated = await _update_knowledge_memory(
            session, user_id=user_id, conversation_id=conversation_id
        )
        return NoteExtractResult(
            conversation_id=conversation_id,
            skipped=True,
            reason="already_extracted",
            notes=existing,
            memory_updated=memory_updated,
        )

    repo = ConversationRepository(session)
    messages = await repo.list_messages(conversation_id)
    turns = [
        {"role": m.role, "content": m.content}
        for m in messages
        if m.role in {"user", "assistant"} and (m.content or "").strip()
    ]
    if len(turns) < 2:
        return NoteExtractResult(
            conversation_id=conversation_id,
            skipped=True,
            reason="too_few_messages",
        )

    text = format_conversation(turns)
    from app.llm.usage import PURPOSE_NOTES, usage_scope

    with usage_scope(
        purpose=PURPOSE_NOTES,
        user_id=user_id,
        conversation_id=conversation_id,
        session=session,
    ):
        parsed = await structured_complete(
            [
                {"role": "system", "content": NOTE_EXTRACT_SYSTEM},
                {
                    "role": "user",
                    "content": NOTE_EXTRACT_USER.format(
                        title=conversation.title or "学习会话",
                        conversation_text=text,
                    ),
                },
            ],
            NotesLLMResult,
        )
    assert isinstance(parsed, NotesLLMResult)

    if not parsed.worth_saving or not parsed.notes:
        memory_updated = await _update_knowledge_memory(
            session, user_id=user_id, conversation_id=conversation_id
        )
        return NoteExtractResult(
            conversation_id=conversation_id,
            skipped=True,
            reason=parsed.reason or "nothing_to_save",
            memory_updated=memory_updated,
        )

    created = _persist_drafts(
        conversation_id=conversation_id,
        conversation_title=conversation.title or "",
        drafts=parsed.notes[:4],
    )
    memory_updated = await _update_knowledge_memory(
        session, user_id=user_id, conversation_id=conversation_id
    )
    logger.info(
        "tutor_notes_extracted",
        conversation_id=conversation_id,
        count=len(created),
        memory_updated=memory_updated,
    )
    return NoteExtractResult(
        conversation_id=conversation_id,
        skipped=False,
        reason=parsed.reason or None,
        notes=created,
        memory_updated=memory_updated,
    )
