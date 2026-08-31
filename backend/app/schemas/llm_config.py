"""Schemas for the runtime LLM provider settings API.

Credentials travel inbound in cleartext (there is no way around that when the
user is typing a key) but never travel back out: every response model carries
masked values produced by ``ProviderRecord.public_dict``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.llm.providers import ProviderInput, ProviderKind


class ProviderCreate(ProviderInput):
    """Create payload: full provider settings plus an activation switch."""

    activate: bool = Field(
        default=True,
        description="Make this the active provider immediately after saving.",
    )

    def to_input(self) -> ProviderInput:
        data = self.model_dump(exclude={"activate"})
        return ProviderInput.model_validate(data)


class ProviderUpdate(BaseModel):
    """Partial update.

    Omitted fields keep their stored value; an empty string clears a field.
    Cross-field rules are re-checked against the merged record by the store.
    """

    label: str | None = Field(default=None, min_length=1, max_length=80)
    kind: ProviderKind | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)

    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    hf_provider: str | None = Field(default=None, max_length=64)

    aws_region: str | None = Field(default=None, max_length=64)
    aws_profile_name: str | None = Field(default=None, max_length=128)
    aws_access_key_id: str | None = Field(default=None, max_length=128)
    aws_secret_access_key: str | None = Field(default=None, max_length=256)
    aws_session_token: str | None = Field(default=None, max_length=4096)

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=200_000)

    @field_validator(
        "base_url",
        "api_key",
        "hf_provider",
        "aws_region",
        "aws_profile_name",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    def changes(self) -> dict[str, Any]:
        """Only the fields the caller actually sent."""
        return self.model_dump(exclude_unset=True)


class ProviderView(BaseModel):
    """A stored provider with masked credentials."""

    id: str
    label: str
    kind: ProviderKind
    model: str
    base_url: str | None = None
    api_key: str | None = Field(default=None, description="Masked, e.g. ****1234")
    hf_provider: str | None = None

    aws_region: str | None = None
    aws_profile_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None

    temperature: float | None = None
    max_tokens: int | None = None

    created_at: datetime
    updated_at: datetime

    is_active: bool = False
    has_credentials: bool = False


class ActiveLLMView(BaseModel):
    """What the next LLM call will actually use."""

    source: str
    kind: ProviderKind
    label: str
    model: str
    provider_id: str | None = None
    base_url: str | None = None
    aws_region: str | None = None
    configured: bool
    temperature: float
    max_tokens: int


class EnvDefaultsView(BaseModel):
    """Read-only view of the ``.env`` fallback, so the UI can explain it."""

    base_url: str
    model: str
    has_api_key: bool
    temperature: float
    max_tokens: int


class PresetView(BaseModel):
    id: str
    label: str
    kind: ProviderKind
    base_url: str | None = None
    hf_provider: str | None = None
    model: str
    docs_url: str | None = None
    hint: str | None = None
    credential_env: list[str] = []


class LLMConfigResponse(BaseModel):
    """Everything the settings page needs in one request."""

    enabled: bool
    active: ActiveLLMView
    env_defaults: EnvDefaultsView
    providers: list[ProviderView]
    presets: list[PresetView]
    routes: dict[str, str | None] = Field(default_factory=dict)
    store_path: str


class LLMRoutesUpdate(BaseModel):
    """Assign saved providers to call purposes. Omitted keys stay as they are.

    ``null`` or empty string means “follow the default / active provider”.
    """

    chat: str | None = None
    skill: str | None = None
    notes: str | None = None
    memory: str | None = None
    knowledge: str | None = None
    image: str | None = None

    @field_validator(
        "chat", "skill", "notes", "memory", "knowledge", "image", mode="before"
    )
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    def changes(self) -> dict[str, str | None]:
        return self.model_dump(exclude_unset=True)


class ProviderTestRequest(BaseModel):
    """Test a saved provider by id, or an unsaved draft inline.

    Exactly one of ``provider_id`` or ``draft`` should be supplied; ``draft``
    wins if both are, and omitting both tests the currently active config.
    """

    provider_id: str | None = None
    draft: ProviderInput | None = None
    prompt: str = Field(
        default="Reply with the single word: pong",
        max_length=500,
    )


class ProviderTestResponse(BaseModel):
    ok: bool
    label: str
    kind: ProviderKind
    model: str
    source: str
    latency_ms: int | None = None
    content: str | None = None
    total_tokens: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] | None = None
