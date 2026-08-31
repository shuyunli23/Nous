"""Data access for users."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: str) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, external_id: str) -> User:
        user = await self.get_by_external_id(external_id)
        if user is not None:
            return user
        user = User(external_id=external_id, display_name=external_id)
        self.session.add(user)
        await self.session.flush()
        return user
