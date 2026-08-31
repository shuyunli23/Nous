"""LLM provider definitions shared by the runtime store, client and API.

Protocol families:

``openai_compatible``
    Anything speaking ``POST {base_url}/chat/completions`` with a bearer token:
    OpenAI, DeepSeek, Alibaba DashScope compatible-mode, Moonshot, vLLM,
    Ollama, one-api gateways, ...  Also usable for OpenAI-style
    ``/images/generations`` when assigned to the image route.

``bedrock``
    AWS Bedrock via the native Converse API, which uses SigV4 request signing
    instead of a bearer token and therefore needs its own adapter. Image route
    uses Nova Canvas / Titan on the same credentials.

``huggingface_image``
    Hugging Face Inference Providers (fal-ai, replicate, …) for text-to-image.
    Chat cannot use this kind; pick it under Settings → models by purpose →
    image generation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ProviderKind = Literal["openai_compatible", "bedrock", "huggingface_image"]

# Image-only records must never become the chat default or a chat-purpose route.
IMAGE_ONLY_KINDS = frozenset({"huggingface_image"})
CHAT_KINDS = frozenset({"openai_compatible", "bedrock"})
IMAGE_CAPABLE_KINDS = CHAT_KINDS | IMAGE_ONLY_KINDS

# Fields that must never be returned to a client in cleartext.
SECRET_FIELDS = frozenset(
    {"api_key", "aws_secret_access_key", "aws_session_token", "aws_access_key_id"}
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def mask_secret(value: str | None) -> str | None:
    """Render a credential as ``****abcd`` so the UI can confirm which key is set.

    Returns ``None`` for unset values and a fixed mask for very short ones so
    the output never leaks a full short key.
    """
    if not value:
        return None
    if len(value) <= 8:
        return "****"
    return f"****{value[-4:]}"


class ProviderInput(BaseModel):
    """User-supplied provider settings (create/update payload body)."""

    label: str = Field(min_length=1, max_length=80)
    kind: ProviderKind = "openai_compatible"
    model: str = Field(min_length=1, max_length=200)

    # --- openai_compatible ---
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)

    # --- huggingface_image ---
    hf_provider: str | None = Field(default=None, max_length=64)

    # --- bedrock ---
    aws_region: str | None = Field(default=None, max_length=64)
    aws_profile_name: str | None = Field(default=None, max_length=128)
    aws_access_key_id: str | None = Field(default=None, max_length=128)
    aws_secret_access_key: str | None = Field(default=None, max_length=256)
    aws_session_token: str | None = Field(default=None, max_length=4096)

    # --- generation overrides (fall back to .env when unset) ---
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
        """Treat whitespace-only input from form fields as "not set"."""
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("label", "model", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("base_url")
    @classmethod
    def _check_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return value.rstrip("/")

    @model_validator(mode="after")
    def _check_kind_requirements(self) -> ProviderInput:
        if self.kind == "openai_compatible":
            if not self.base_url:
                raise ValueError("base_url is required for openai_compatible providers")
        elif self.kind == "bedrock":
            if not self.aws_region:
                raise ValueError("aws_region is required for bedrock providers")
            # A lone access key id without its secret cannot sign a request.
            has_id = bool(self.aws_access_key_id)
            has_secret = bool(self.aws_secret_access_key)
            if has_id != has_secret:
                raise ValueError(
                    "aws_access_key_id and aws_secret_access_key must be set together"
                )
        elif self.kind == "huggingface_image":
            if not self.hf_provider:
                self.hf_provider = "fal-ai"
        return self


class ProviderRecord(ProviderInput):
    """A stored provider: user input plus identity and timestamps."""

    id: str
    created_at: datetime
    updated_at: datetime

    def public_dict(self) -> dict[str, Any]:
        """Serialise with every credential masked, safe to send to the browser."""
        data = self.model_dump(mode="json")
        for field in SECRET_FIELDS:
            data[field] = mask_secret(getattr(self, field))
        return data

    def touch(self) -> None:
        self.updated_at = _now()


class ResolvedLLM(BaseModel):
    """The concrete configuration a single LLM call should use.

    Produced either from the active runtime provider or from ``.env`` defaults,
    so call sites never need to know which source won.
    """

    source: Literal["runtime", "env"]
    kind: ProviderKind
    model: str
    label: str
    provider_id: str | None = None

    base_url: str | None = None
    api_key: str | None = None
    hf_provider: str | None = None

    aws_region: str | None = None
    aws_profile_name: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None

    temperature: float
    max_tokens: int
    timeout_seconds: float
    max_retries: int

    @property
    def configured(self) -> bool:
        """Whether this config has enough credentials to attempt a call.

        Bedrock is optimistic: boto3 can also pick credentials up from the
        environment, an instance role or SSO, none of which we can see here.
        """
        if self.kind == "bedrock":
            return bool(self.aws_region)
        if self.kind == "huggingface_image":
            return bool(self.api_key)
        return bool(self.api_key)


class ProviderPreset(BaseModel):
    """UI prefill for a known vendor. Never contains credentials."""

    id: str
    label: str
    kind: ProviderKind
    base_url: str | None = None
    hf_provider: str | None = None
    model: str
    docs_url: str | None = None
    hint: str | None = None
    credential_env: list[str] = []


PRESETS: list[ProviderPreset] = [
    ProviderPreset(
        id="deepseek",
        label="DeepSeek",
        kind="openai_compatible",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        docs_url="https://platform.deepseek.com/api_keys",
        hint="API key 以 sk- 开头。",
        credential_env=["LLM_API_KEY"],
    ),
    ProviderPreset(
        id="openai",
        label="OpenAI",
        kind="openai_compatible",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        docs_url="https://platform.openai.com/api-keys",
        credential_env=["LLM_API_KEY"],
    ),
    ProviderPreset(
        id="aliyun",
        label="阿里云百炼 / DashScope",
        kind="openai_compatible",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
        docs_url="https://bailian.console.aliyun.com/",
        hint="使用 compatible-mode 地址；API key 以 sk- 开头。",
        credential_env=["ALI_API_KEY", "ALI_BASE_URL", "ALI_MODEL_NAME"],
    ),
    ProviderPreset(
        id="moonshot",
        label="Moonshot / Kimi",
        kind="openai_compatible",
        base_url="https://api.moonshot.cn/v1",
        model="moonshot-v1-8k",
        docs_url="https://platform.moonshot.cn/console/api-keys",
    ),
    ProviderPreset(
        id="zhipu",
        label="智谱 GLM",
        kind="openai_compatible",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-4-plus",
        docs_url="https://open.bigmodel.cn/usercenter/apikeys",
    ),
    ProviderPreset(
        id="siliconflow",
        label="SiliconFlow 硅基流动",
        kind="openai_compatible",
        base_url="https://api.siliconflow.cn/v1",
        model="Qwen/Qwen2.5-7B-Instruct",
        docs_url="https://cloud.siliconflow.cn/account/ak",
    ),
    ProviderPreset(
        id="ollama",
        label="Ollama（本地）",
        kind="openai_compatible",
        base_url="http://localhost:11434/v1",
        model="qwen2.5:7b",
        hint="本地服务通常不校验 API key，可留空。",
    ),
    ProviderPreset(
        id="flux-dev",
        label="FLUX.1-dev（Hugging Face / fal-ai）",
        kind="huggingface_image",
        model="black-forest-labs/FLUX.1-dev",
        hf_provider="fal-ai",
        docs_url="https://huggingface.co/docs/inference-providers",
        hint="填 HF Token（hf_…）。在「按用途选用模型 → 文生图」里选用，不会改对话模型。",
        credential_env=["HF_TOKEN"],
    ),
    ProviderPreset(
        id="flux-schnell",
        label="FLUX.1-schnell（更快）",
        kind="huggingface_image",
        model="black-forest-labs/FLUX.1-schnell",
        hf_provider="fal-ai",
        docs_url="https://huggingface.co/docs/inference-providers",
        hint="同样走 Hugging Face Inference Providers；比 dev 更快、细节略少。",
        credential_env=["HF_TOKEN"],
    ),
    ProviderPreset(
        id="bedrock",
        label="AWS Bedrock",
        kind="bedrock",
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        docs_url="https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html",
        hint=(
            "填 Access Key/Secret，或只填 Profile 名走本机 ~/.aws/credentials；"
            "两者都留空则使用默认凭证链（环境变量 / IAM 角色）。"
        ),
        credential_env=[
            "AWS_REGION",
            "AWS_PROFILE_NAME",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
        ],
    ),
]
