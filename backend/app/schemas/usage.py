"""Token usage API schemas. Counts only, no money."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UsageTotals(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0


class UsagePurposeRow(UsageTotals):
    purpose: str
    label: str = ""


class UsageModelRow(UsageTotals):
    model: str
    provider_label: str = ""


class UsagePeriod(UsageTotals):
    since: datetime | None = None
    by_purpose: list[UsagePurposeRow] = Field(default_factory=list)
    by_model: list[UsageModelRow] = Field(default_factory=list)


class UsageSummary(BaseModel):
    today: UsagePeriod
    month: UsagePeriod
    all: UsagePeriod
