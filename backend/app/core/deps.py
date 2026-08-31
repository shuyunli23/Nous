"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.models import User
from app.database.session import get_session
from app.repositories.user_repo import UserRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> User:
    """Resolve the acting user.

    Authentication is intentionally out of scope: the optional ``X-User-Id``
    header selects (or creates) a user, otherwise the configured local dev user
    is used. Swapping this single dependency for real auth is enough to secure
    every endpoint, since all queries are already scoped by ``user_id``.
    """
    external_id = x_user_id or settings.default_user_external_id
    repo = UserRepository(session)
    user = await repo.get_or_create(external_id)
    await session.commit()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


class Pagination:
    """Reusable ``limit``/``offset`` query params."""

    def __init__(
        self,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends(Pagination)]
