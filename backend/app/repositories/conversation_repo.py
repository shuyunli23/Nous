"""Data access for conversations and messages.

Repositories own queries only: they never commit. Transaction boundaries belong
to the service layer so one request can span several repository calls.
"""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.base import utcnow
from app.database.models import Conversation, Message
from app.database.models.enums import ConversationStatus, ExtractionStatus


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- conversations -----------------------------------------------------

    async def create(
        self, *, user_id: str, title: str, mode_id: str | None = None
    ) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title, mode_id=mode_id)
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get(
        self, conversation_id: str, *, with_messages: bool = False
    ) -> Conversation | None:
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        stmt = stmt.options(selectinload(Conversation.mode))
        if with_messages:
            stmt = stmt.options(selectinload(Conversation.messages))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        status: ConversationStatus | None = None,
        search: str | None = None,
    ) -> tuple[Sequence[tuple[Conversation, int]], int]:
        """Return ``[(conversation, message_count)]`` plus the total row count."""
        count_subq = (
            select(func.count(Message.id))
            .where(Message.conversation_id == Conversation.id)
            .correlate(Conversation)
            .scalar_subquery()
        )

        stmt = select(Conversation, count_subq).where(Conversation.user_id == user_id)
        stmt = stmt.options(selectinload(Conversation.mode))
        count_stmt = select(func.count(Conversation.id)).where(
            Conversation.user_id == user_id
        )

        if status is not None:
            stmt = stmt.where(Conversation.status == status.value)
            count_stmt = count_stmt.where(Conversation.status == status.value)
        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(func.lower(Conversation.title).like(pattern))
            count_stmt = count_stmt.where(func.lower(Conversation.title).like(pattern))

        stmt = stmt.order_by(Conversation.updated_time.desc()).limit(limit).offset(offset)

        rows = (await self.session.execute(stmt)).all()
        total = (await self.session.execute(count_stmt)).scalar_one()
        return [(row[0], row[1] or 0) for row in rows], int(total)

    async def count_messages(self, conversation_id: str) -> int:
        stmt = select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def delete(self, conversation: Conversation) -> None:
        await self.session.delete(conversation)

    async def touch(self, conversation: Conversation) -> None:
        """Bump ``updated_time`` so list ordering reflects latest activity."""
        conversation.updated_time = utcnow()
        await self.session.flush()

    async def set_status(
        self, conversation: Conversation, status: ConversationStatus
    ) -> None:
        conversation.status = status.value
        await self.session.flush()

    async def set_extraction_status(
        self,
        conversation: Conversation,
        status: ExtractionStatus,
        *,
        error: str | None = None,
    ) -> None:
        conversation.extraction_status = status.value
        conversation.extraction_error = error
        await self.session.flush()

    async def list_pending_extraction(self, limit: int = 20) -> Sequence[Conversation]:
        stmt = (
            select(Conversation)
            .where(
                Conversation.status == ConversationStatus.CLOSED.value,
                Conversation.extraction_status == ExtractionStatus.PENDING.value,
            )
            .order_by(Conversation.updated_time.asc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    # --- messages ----------------------------------------------------------

    async def next_seq(self, conversation_id: str) -> int:
        """Next ordinal for a conversation (1-based)."""
        stmt = select(func.max(Message.seq)).where(
            Message.conversation_id == conversation_id
        )
        current = (await self.session.execute(stmt)).scalar_one_or_none()
        return int(current or 0) + 1

    async def add_message(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        token_usage: dict[str, Any] | None = None,
        used_skill_ids: list[str] | None = None,
        execution_trace: list[dict[str, Any]] | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            seq=await self.next_seq(conversation_id),
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            token_usage=token_usage,
            used_skill_ids=used_skill_ids,
            execution_trace=execution_trace,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_messages(
        self, conversation_id: str, *, limit: int | None = None
    ) -> Sequence[Message]:
        """Messages in chronological order; ``limit`` keeps the newest ones."""
        if limit is None:
            stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.seq.asc(), Message.created_at.asc())
            )
            return (await self.session.execute(stmt)).scalars().all()

        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.seq.desc(), Message.created_at.desc())
            .limit(limit)
        )
        newest_first = (await self.session.execute(stmt)).scalars().all()
        return list(reversed(newest_first))

    async def delete_messages(self, conversation_id: str) -> None:
        await self.session.execute(
            delete(Message).where(Message.conversation_id == conversation_id)
        )
