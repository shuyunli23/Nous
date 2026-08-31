"""Token ledger helpers (no DB, no LLM)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from app.llm.usage import (
    PURPOSE_CHAT,
    PURPOSE_MEMORY,
    current_usage_meta,
    period_starts,
    usage_scope,
)


def test_period_starts_local_midnight() -> None:
    now = datetime(2026, 8, 16, 11, 35, tzinfo=timezone(timedelta(hours=8)))
    today, month = period_starts(now)
    assert today.hour == 0
    assert today.day == 16
    assert month.day == 1
    assert month.month == 8


def test_usage_scope_nests_and_restores() -> None:
    with usage_scope(purpose=PURPOSE_CHAT, user_id="u1", conversation_id="c1"):
        assert current_usage_meta().purpose == PURPOSE_CHAT
        assert current_usage_meta().user_id == "u1"
        with usage_scope(purpose=PURPOSE_MEMORY, user_id="u1", conversation_id="c1"):
            assert current_usage_meta().purpose == PURPOSE_MEMORY
        assert current_usage_meta().purpose == PURPOSE_CHAT
    assert current_usage_meta().conversation_id is None
