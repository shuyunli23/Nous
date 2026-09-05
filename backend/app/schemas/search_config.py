"""Schemas for the runtime web-search settings API.

Secrets travel inbound in cleartext but never travel back out unmasked.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent.search_config import PROVIDERS

SearchProvider = Literal[
    "auto",
    "brave",
    "tavily",
    "serper",
    "deepseek",
    "ddgs",
    "ddg_html",
]
KeySource = Literal["runtime", "env", "llm", "unset"]
ProviderSource = Literal["runtime", "env"]


class SearchKeyView(BaseModel):
    configured: bool
    source: KeySource
    masked: str | None = None


class SearchConfigUpdate(BaseModel):
    """Partial update. Omitted fields keep their stored overlay value."""

    provider: str | None = Field(default=None, max_length=32)
    brave_search_api_key: str | None = Field(default=None, max_length=500)
    tavily_api_key: str | None = Field(default=None, max_length=500)
    serper_api_key: str | None = Field(default=None, max_length=500)
    deepseek_api_key: str | None = Field(default=None, max_length=500)
    deepseek_base_url: str | None = Field(default=None, max_length=500)
    deepseek_model: str | None = Field(default=None, max_length=200)
    deepseek_max_uses: int | None = Field(default=None, ge=1, le=5)

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class SearchConfigResponse(BaseModel):
    provider: SearchProvider
    provider_source: ProviderSource
    env_provider: str
    keys: dict[str, SearchKeyView]
    deepseek_base_url: str
    deepseek_model: str
    deepseek_max_uses: int
    planned_backends: list[str]
    store_path: str
    providers: list[str] = Field(default_factory=lambda: list(PROVIDERS))


class SearchTestRequest(BaseModel):
    query: str = Field(default="OpenAI", min_length=1, max_length=200)
    max_results: int = Field(default=3, ge=1, le=5)


class SearchTestResponse(BaseModel):
    ok: bool
    query: str
    provider: str | None = None
    count: int = 0
    results: list[dict[str, str]] = Field(default_factory=list)
    tried: list[str] = Field(default_factory=list)
    latency_ms: int | None = None
    error: str | None = None
