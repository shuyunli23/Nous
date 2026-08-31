"""GET /api/v1/usage — token totals (no money)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.schemas.usage import UsageSummary
from app.services.usage_service import UsageService

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("", response_model=UsageSummary, summary="Token usage today, this month, and all time")
async def get_usage(session: SessionDep, user: CurrentUser) -> UsageSummary:
    return await UsageService(session).summary(user.id)
