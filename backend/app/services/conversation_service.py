"""Conversation use cases. Owns transaction boundaries."""

from __future__ import annotations

from app.chat_modes.catalog import WORKBENCH
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.database.models import Conversation
from app.database.models.enums import ConversationStatus, ExtractionStatus
from app.database.session import session_scope
from app.repositories.conversation_repo import ConversationRepository
from app.schemas.common import Page
from app.schemas.conversation import (
    ConversationDetail,
    ConversationSummary,
    MessageRead,
)
from app.services.conversation_title import (
    expand_clipped_title,
    is_clipped_title,
    is_weak_title,
    schedule_title_job,
    should_llm_refresh,
    title_from_messages,
    title_from_user_texts,
    user_texts_from_messages,
    llm_topic_title_timed,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


def derive_title(text: str) -> str:
    """Build a readable title from a user message (no LLM)."""
    return title_from_user_texts([text]) or "新会话"


def mode_fields(conversation: Conversation) -> dict:
    mode = getattr(conversation, "mode", None)
    return {
        "mode_id": conversation.mode_id,
        "mode_key": mode.key if mode is not None else None,
        "mode_name": mode.name if mode is not None else None,
    }


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ConversationRepository(session)

    async def create(
        self, *, user_id: str, title: str | None = None, mode_id: str | None = None
    ) -> Conversation:
        custom = (title or "").strip()
        conversation = await self.repo.create(
            user_id=user_id, title=custom or "新会话", mode_id=mode_id
        )
        if custom:
            conversation.title_auto = False
        await self.session.commit()
        await self.session.refresh(conversation, attribute_names=["mode"])
        logger.info(
            "conversation_created",
            conversation_id=conversation.id,
            user_id=user_id,
            mode_id=mode_id,
        )
        return conversation

    async def get_or_404(
        self, conversation_id: str, *, user_id: str | None = None
    ) -> Conversation:
        conversation = await self.repo.get(conversation_id)
        if conversation is None or (
            user_id is not None and conversation.user_id != user_id
        ):
            raise NotFoundError(
                f"Conversation {conversation_id} not found.",
                details={"conversation_id": conversation_id},
            )
        return conversation

    async def list_page(
        self,
        *,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        status: ConversationStatus | None = None,
        search: str | None = None,
    ) -> Page[ConversationSummary]:
        rows, total = await self.repo.list_for_user(
            user_id, limit=limit, offset=offset, status=status, search=search
        )
        ids = [conversation.id for conversation, _count in rows]
        ledger = await self._token_totals(ids)
        legacy = await self._legacy_message_tokens(ids)
        pending, needs_commit = await self._backfill_list_titles(rows)
        items = [
            ConversationSummary.from_orm(
                conversation,
                message_count=count,
                token_total=ledger.get(conversation.id) or legacy.get(conversation.id) or 0,
                **mode_fields(conversation),
            )
            for conversation, count in rows
        ]
        if needs_commit:
            await self.session.commit()
        for conversation_id in pending[:6]:
            schedule_title_job(conversation_id, _refine_title_job)
        return Page[ConversationSummary](
            items=items, total=total, limit=limit, offset=offset
        )

    async def get_detail(
        self, conversation_id: str, *, user_id: str | None = None
    ) -> ConversationDetail:
        conversation = await self.get_or_404(conversation_id, user_id=user_id)
        messages = await self.repo.list_messages(conversation_id)
        if getattr(conversation, "title_auto", True):
            user_texts = user_texts_from_messages(messages)
            expanded = expand_clipped_title(conversation.title, user_texts)
            if expanded != (conversation.title or "").strip():
                conversation.title = expanded
                await self.session.commit()
        msg_schemas = [MessageRead.model_validate(m) for m in messages]

        # Build a plain dict to avoid Pydantic touching the lazy-loaded
        # `messages` relationship on the ORM object (MissingGreenlet).
        data = {
            "id": conversation.id,
            "user_id": conversation.user_id,
            "title": conversation.title,
            "status": conversation.status,
            "summary": conversation.summary,
            "extraction_status": conversation.extraction_status,
            "extraction_error": conversation.extraction_error,
            "message_count": len(messages),
            "token_total": (await self._token_totals([conversation.id])).get(
                conversation.id, 0
            )
            or _legacy_sum(messages),
            **mode_fields(conversation),
            "created_time": conversation.created_time,
            "updated_time": conversation.updated_time,
            "messages": msg_schemas,
        }
        return ConversationDetail.model_validate(data)

    async def update(
        self,
        conversation_id: str,
        *,
        user_id: str | None = None,
        title: str | None = None,
        status: ConversationStatus | None = None,
    ) -> Conversation:
        conversation = await self.get_or_404(conversation_id, user_id=user_id)
        if title is not None:
            conversation.title = title
            conversation.title_auto = False
        if status is not None:
            conversation.status = status.value
        await self.session.commit()
        await self.session.refresh(conversation, attribute_names=["mode"])
        return conversation

    async def delete(self, conversation_id: str, *, user_id: str | None = None) -> None:
        conversation = await self.get_or_404(conversation_id, user_id=user_id)
        await self.repo.delete(conversation)
        await self.session.commit()
        logger.info("conversation_deleted", conversation_id=conversation_id)

    async def mark_closed(
        self, conversation_id: str, *, user_id: str | None = None
    ) -> Conversation:
        """Close a conversation and queue it for skill extraction."""
        conversation = await self.get_or_404(conversation_id, user_id=user_id)
        conversation.status = ConversationStatus.CLOSED.value
        mode = getattr(conversation, "mode", None)
        skip_skills = mode is not None and mode.key != WORKBENCH
        if skip_skills:
            conversation.extraction_status = ExtractionStatus.SKIPPED.value
        elif conversation.extraction_status in {
            ExtractionStatus.DONE.value,
            ExtractionStatus.RUNNING.value,
        }:
            pass  # already handled or in flight
        else:
            conversation.extraction_status = ExtractionStatus.PENDING.value
            conversation.extraction_error = None
        await self.session.commit()
        await self.session.refresh(conversation)
        logger.info("conversation_closed", conversation_id=conversation_id)
        return conversation

    async def ensure_title(self, conversation: Conversation, first_message: str) -> bool:
        """Keep a usable title as soon as the first user turn lands.

        Returns True when a background LLM polish should still run.
        """
        _title, needs_llm = await self.refresh_title(
            conversation, extra_user_text=first_message, use_llm=False
        )
        return needs_llm

    async def refresh_title(
        self,
        conversation: Conversation,
        *,
        extra_user_text: str | None = None,
        use_llm: bool = True,
    ) -> tuple[str, bool]:
        """Heuristic now; LLM polish when the opener is still a greeting or first line."""
        if not getattr(conversation, "title_auto", True):
            return conversation.title, False

        messages = await self.repo.list_messages(conversation.id, limit=24)
        user_texts = user_texts_from_messages(messages)
        if extra_user_text and extra_user_text not in user_texts:
            user_texts = [extra_user_text, *user_texts]

        mode = getattr(conversation, "mode", None)
        mode_key = mode.key if mode is not None else None
        mode_name = mode.name if mode is not None else None
        heuristic = title_from_user_texts(
            user_texts, mode_key=mode_key, mode_name=mode_name
        )
        current = (conversation.title or "").strip() or "新会话"
        if is_clipped_title(current):
            expanded = expand_clipped_title(current, user_texts)
            if expanded and expanded != current:
                conversation.title = expanded
                current = expanded
        if heuristic and is_weak_title(current, user_texts):
            conversation.title = heuristic
            current = heuristic

        needs_llm = should_llm_refresh(current, user_texts)
        if use_llm and needs_llm:
            payload = [
                {"role": getattr(row, "role", ""), "content": getattr(row, "content", "") or ""}
                for row in messages
            ]
            llm_title = await llm_topic_title_timed(payload, mode_name=mode_name)
            if llm_title:
                conversation.title = llm_title
            needs_llm = False

        await self.session.flush()
        return conversation.title, needs_llm

    async def _backfill_list_titles(
        self, rows: list[tuple[Conversation, int]]
    ) -> tuple[list[str], bool]:
        """Restore clipped titles and upgrade leftover first-line titles (flush only)."""
        pending: list[str] = []
        for conversation, count in rows:
            if not getattr(conversation, "title_auto", True):
                continue
            clipped = is_clipped_title(conversation.title)
            if not clipped and count < 2:
                continue
            messages = await self.repo.list_messages(conversation.id, limit=24)
            user_texts = user_texts_from_messages(messages)
            if clipped:
                expanded = expand_clipped_title(conversation.title, user_texts)
                if expanded and expanded != conversation.title:
                    conversation.title = expanded
                    continue
            if count < 2:
                continue
            if not is_weak_title(conversation.title, user_texts):
                continue
            mode = getattr(conversation, "mode", None)
            heuristic = title_from_messages(
                messages,
                mode_key=mode.key if mode is not None else None,
                mode_name=mode.name if mode is not None else None,
            )
            if heuristic and heuristic != conversation.title:
                conversation.title = heuristic
            if should_llm_refresh(conversation.title, user_texts):
                pending.append(conversation.id)
        needs_commit = bool(self.session.dirty)
        if needs_commit:
            await self.session.flush()
        return pending, needs_commit

    async def _token_totals(self, conversation_ids: list[str]) -> dict[str, int]:
        from app.services.usage_service import UsageService

        return await UsageService(self.session).totals_for_conversations(conversation_ids)

    async def _legacy_message_tokens(self, conversation_ids: list[str]) -> dict[str, int]:
        if not conversation_ids:
            return {}
        from collections import defaultdict

        from sqlalchemy import select

        from app.database.models.message import Message

        stmt = select(Message.conversation_id, Message.token_usage).where(
            Message.conversation_id.in_(conversation_ids),
            Message.token_usage.isnot(None),
        )
        rows = (await self.session.execute(stmt)).all()
        totals: dict[str, int] = defaultdict(int)
        for conversation_id, usage in rows:
            totals[str(conversation_id)] += _usage_total(usage)
        return dict(totals)


def _usage_total(usage: object) -> int:
    if not isinstance(usage, dict):
        return 0
    return int(usage.get("total_tokens") or 0)


def _legacy_sum(messages: list) -> int:
    return sum(_usage_total(getattr(item, "token_usage", None)) for item in messages)


async def _refine_title_job(conversation_id: str) -> None:
    """Background LLM pass so the history list can catch up after a reload."""
    async with session_scope() as session:
        svc = ConversationService(session)
        conversation = await svc.repo.get(conversation_id)
        if conversation is None or not getattr(conversation, "title_auto", True):
            return
        await svc.refresh_title(conversation, use_llm=True)
        await session.commit()
        logger.info(
            "conversation_title_refined",
            conversation_id=conversation_id,
            title=conversation.title,
        )
