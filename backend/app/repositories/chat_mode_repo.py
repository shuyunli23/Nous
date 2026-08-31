"""Data access for chat modes."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.chat_mode import ChatMode


class ChatModeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, mode_id: str) -> ChatMode | None:
        result = await self.session.execute(
            select(ChatMode).where(ChatMode.id == mode_id)
        )
        return result.scalar_one_or_none()

    async def get_by_key(self, key: str) -> ChatMode | None:
        result = await self.session.execute(select(ChatMode).where(ChatMode.key == key))
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str) -> list[ChatMode]:
        stmt = (
            select(ChatMode)
            .where(or_(ChatMode.is_builtin.is_(True), ChatMode.user_id == user_id))
            .order_by(ChatMode.sort_order.asc(), ChatMode.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, mode: ChatMode) -> ChatMode:
        self.session.add(mode)
        await self.session.flush()
        return mode

    async def delete(self, mode: ChatMode) -> None:
        await self.session.delete(mode)
        await self.session.flush()
