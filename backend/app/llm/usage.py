"""Token ledger: context for a call, plus a fire-and-forget write."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Iterator

from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

PURPOSE_CHAT = "chat"
PURPOSE_SKILL = "skill"
PURPOSE_MEMORY = "memory"
PURPOSE_NOTES = "notes"
PURPOSE_KNOWLEDGE = "knowledge"
PURPOSE_PROBE = "probe"
PURPOSE_OTHER = "other"

KNOWN_PURPOSES = (
    PURPOSE_CHAT,
    PURPOSE_SKILL,
    PURPOSE_MEMORY,
    PURPOSE_NOTES,
    PURPOSE_KNOWLEDGE,
    PURPOSE_PROBE,
    PURPOSE_OTHER,
)


@dataclass(frozen=True)
class UsageMeta:
    purpose: str = PURPOSE_OTHER
    user_id: str | None = None
    conversation_id: str | None = None
    provider_id: str | None = None


_usage_meta: ContextVar[UsageMeta] = ContextVar(
    "llm_usage_meta", default=UsageMeta()
)
_usage_session: ContextVar["AsyncSession | None"] = ContextVar(
    "llm_usage_session", default=None
)


@contextmanager
def usage_scope(
    *,
    purpose: str,
    user_id: str | None = None,
    conversation_id: str | None = None,
    provider_id: str | None = None,
    session: "AsyncSession | None" = None,
) -> Iterator[None]:
    """Tag nested LLM calls (chat_complete / structured_complete) with a purpose."""
    meta_token = _usage_meta.set(
        UsageMeta(
            purpose=purpose or PURPOSE_OTHER,
            user_id=user_id,
            conversation_id=conversation_id,
            provider_id=provider_id,
        )
    )
    session_token = _usage_session.set(session)
    try:
        yield
    finally:
        _usage_session.reset(session_token)
        _usage_meta.reset(meta_token)


def current_usage_meta() -> UsageMeta:
    return _usage_meta.get()


def period_starts(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Local midnight today and the first of this month (tz-aware)."""
    local = (now or datetime.now().astimezone()).astimezone()
    start_today = local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_month = start_today.replace(day=1)
    return start_today, start_month


async def record_completion(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    model: str,
    provider_id: str | None,
    provider_label: str,
) -> None:
    """Persist one successful completion. Never raises into the caller."""
    prompt = max(int(prompt_tokens or 0), 0)
    completion = max(int(completion_tokens or 0), 0)
    total = max(int(total_tokens or 0), 0) or (prompt + completion)
    meta = current_usage_meta()
    try:
        from app.database.models.llm_usage import LlmUsageEvent
        from app.database.session import session_scope

        event = LlmUsageEvent(
            user_id=meta.user_id,
            conversation_id=meta.conversation_id,
            purpose=meta.purpose or PURPOSE_OTHER,
            provider_id=provider_id,
            provider_label=(provider_label or "")[:80],
            model=(model or "")[:200],
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
        )
        bound = _usage_session.get()
        if bound is not None:
            bound.add(event)
            return
        async with session_scope() as session:
            session.add(event)
            await session.commit()
    except Exception:
        logger.warning("llm_usage_record_failed", exc_info=True)
