"""Aggregate token ledger into today / month / all."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.llm_usage import LlmUsageEvent
from app.llm.usage import KNOWN_PURPOSES, period_starts
from app.schemas.usage import (
    UsageModelRow,
    UsagePeriod,
    UsagePurposeRow,
    UsageSummary,
    UsageTotals,
)

PURPOSE_LABELS = {
    "chat": "对话",
    "skill": "Skill 抽取",
    "memory": "档案记忆",
    "notes": "学习笔记",
    "knowledge": "知识库",
    "probe": "连接测试",
    "other": "其他",
}


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class UsageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def summary(self, user_id: str) -> UsageSummary:
        start_today, start_month = period_starts()
        rows = await self._load_rows(user_id)
        return UsageSummary(
            today=self._period(rows, since=start_today),
            month=self._period(rows, since=start_month),
            all=self._period(rows, since=None),
        )

    async def totals_for_conversations(self, conversation_ids: list[str]) -> dict[str, int]:
        if not conversation_ids:
            return {}
        stmt = (
            select(
                LlmUsageEvent.conversation_id,
                func.coalesce(func.sum(LlmUsageEvent.total_tokens), 0),
            )
            .where(LlmUsageEvent.conversation_id.in_(conversation_ids))
            .group_by(LlmUsageEvent.conversation_id)
        )
        result = await self.session.execute(stmt)
        return {str(cid): int(total or 0) for cid, total in result.all() if cid}

    async def _load_rows(self, user_id: str) -> list[LlmUsageEvent]:
        stmt = (
            select(LlmUsageEvent)
            .where(
                or_(
                    LlmUsageEvent.user_id == user_id,
                    LlmUsageEvent.user_id.is_(None),
                )
            )
            .order_by(LlmUsageEvent.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def _period(
        self, rows: list[LlmUsageEvent], *, since: datetime | None
    ) -> UsagePeriod:
        chosen = rows
        if since is not None:
            start = _aware(since)
            chosen = [row for row in rows if _aware(row.created_at) >= start]
        totals = UsageTotals()
        by_purpose: dict[str, UsageTotals] = {}
        by_model: dict[tuple[str, str], UsageTotals] = {}
        for row in chosen:
            self._add(totals, row)
            purpose = row.purpose if row.purpose in KNOWN_PURPOSES else "other"
            bucket = by_purpose.setdefault(purpose, UsageTotals())
            self._add(bucket, row)
            key = (row.model or "unknown", row.provider_label or "")
            model_bucket = by_model.setdefault(key, UsageTotals())
            self._add(model_bucket, row)
        purpose_rows = [
            UsagePurposeRow(
                purpose=purpose,
                label=PURPOSE_LABELS.get(purpose, purpose),
                **by_purpose[purpose].model_dump(),
            )
            for purpose in KNOWN_PURPOSES
            if purpose in by_purpose
        ]
        purpose_rows.sort(key=lambda item: item.total_tokens, reverse=True)
        model_rows = [
            UsageModelRow(
                model=model,
                provider_label=label,
                **totals.model_dump(),
            )
            for (model, label), totals in by_model.items()
        ]
        model_rows.sort(key=lambda item: item.total_tokens, reverse=True)
        return UsagePeriod(
            since=since,
            prompt_tokens=totals.prompt_tokens,
            completion_tokens=totals.completion_tokens,
            total_tokens=totals.total_tokens,
            calls=totals.calls,
            by_purpose=purpose_rows,
            by_model=model_rows[:12],
        )

    @staticmethod
    def _add(bucket: UsageTotals, row: LlmUsageEvent) -> None:
        bucket.prompt_tokens += int(row.prompt_tokens or 0)
        bucket.completion_tokens += int(row.completion_tokens or 0)
        bucket.total_tokens += int(row.total_tokens or 0)
        bucket.calls += 1
