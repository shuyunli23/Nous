"""模型配置 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.nexusmind.models.model_config import LLMProvider, PROVIDER_DEFAULT_BASE_URL


class ProviderInfo(BaseModel):
    """前端下拉用的服务商元数据。"""

    id: str
    label: str
    default_base_url: str
    protocol: str  # openai_compatible | anthropic | gemini | bedrock
    hint: str = ""


PROVIDER_CATALOG: list[ProviderInfo] = [
    ProviderInfo(
        id=LLMProvider.OPENAI,
        label="OpenAI",
        default_base_url=PROVIDER_DEFAULT_BASE_URL[LLMProvider.OPENAI],
        protocol="openai_compatible",
        hint="官方 Chat Completions API",
    ),
    ProviderInfo(
        id=LLMProvider.AZURE_OPENAI,
        label="Azure OpenAI",
        default_base_url="",
        protocol="openai_compatible",
        hint="需填写资源 endpoint；api-version 写在高级配置",
    ),
    ProviderInfo(
        id=LLMProvider.ANTHROPIC,
        label="Anthropic Claude",
        default_base_url=PROVIDER_DEFAULT_BASE_URL[LLMProvider.ANTHROPIC],
        protocol="anthropic",
    ),
    ProviderInfo(
        id=LLMProvider.GEMINI,
        label="Google Gemini",
        default_base_url=PROVIDER_DEFAULT_BASE_URL[LLMProvider.GEMINI],
        protocol="gemini",
    ),
    ProviderInfo(
        id=LLMProvider.AWS,
        label="Amazon Bedrock (AWS)",
        default_base_url="",
        protocol="bedrock",
        hint="填写 Access Key / Secret / Region；Model Name 用 Bedrock 模型 ID，如 amazon.nova-lite-v1:0",
    ),
    ProviderInfo(
        id=LLMProvider.DEEPSEEK,
        label="DeepSeek",
        default_base_url=PROVIDER_DEFAULT_BASE_URL[LLMProvider.DEEPSEEK],
        protocol="openai_compatible",
    ),
    ProviderInfo(
        id=LLMProvider.QWEN,
        label="通义千问",
        default_base_url=PROVIDER_DEFAULT_BASE_URL[LLMProvider.QWEN],
        protocol="openai_compatible",
        hint="阿里云百炼 compatible-mode",
    ),
    ProviderInfo(
        id=LLMProvider.ZHIPU,
        label="智谱 GLM",
        default_base_url=PROVIDER_DEFAULT_BASE_URL[LLMProvider.ZHIPU],
        protocol="openai_compatible",
    ),
    ProviderInfo(
        id=LLMProvider.VOLCENGINE,
        label="火山方舟",
        default_base_url=PROVIDER_DEFAULT_BASE_URL[LLMProvider.VOLCENGINE],
        protocol="openai_compatible",
    ),
    ProviderInfo(
        id=LLMProvider.OLLAMA,
        label="Ollama",
        default_base_url=PROVIDER_DEFAULT_BASE_URL[LLMProvider.OLLAMA],
        protocol="openai_compatible",
        hint="本地部署，API Key 可留空",
    ),
    ProviderInfo(
        id=LLMProvider.CUSTOM,
        label="自定义 OpenAI 兼容",
        default_base_url="",
        protocol="openai_compatible",
        hint="任意兼容 /chat/completions 的网关",
    ),
]


class ModelConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    provider: str
    api_key: str = ""
    base_url: str = ""
    model_name: str = Field(..., min_length=1, max_length=128)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=64, le=128000)
    is_default: bool = False
    is_active: bool = True
    extra_config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "model_name")
    @classmethod
    def _strip_required(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("provider")
    @classmethod
    def _check_provider(cls, v: str) -> str:
        allowed = {p.value for p in LLMProvider}
        if v not in allowed:
            raise ValueError(f"不支持的服务商: {v}")
        return v


class ModelConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    provider: str | None = None
    # None = 不改；空字符串也可表示清空（Ollama）；前端用特殊约定：不传则保留
    api_key: str | None = None
    base_url: str | None = None
    model_name: str | None = Field(default=None, min_length=1, max_length=128)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=64, le=128000)
    is_default: bool | None = None
    is_active: bool | None = None
    extra_config: dict[str, Any] | None = None

    @field_validator("provider")
    @classmethod
    def _check_provider(cls, v: str | None) -> str | None:
        if v is None:
            return None
        allowed = {p.value for p in LLMProvider}
        if v not in allowed:
            raise ValueError(f"不支持的服务商: {v}")
        return v


class ModelConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    provider: str
    # 仅返回掩码，不回传明文
    api_key_masked: str = ""
    has_api_key: bool = False
    base_url: str
    resolved_base_url: str = ""
    model_name: str
    temperature: float
    max_tokens: int
    is_default: bool
    is_active: bool
    last_tested_at: datetime | None = None
    last_test_ok: bool | None = None
    last_test_message: str | None = None
    extra_config: dict[str, Any] = Field(default_factory=dict)
    created_time: datetime
    updated_time: datetime


class ModelTestRequest(BaseModel):
    """可对已保存配置测试，也可对未保存的草稿测试。"""

    # 已保存配置 id；与草稿字段二选一
    id: str | None = None
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model_name: str | None = None
    temperature: float | None = 0.2
    max_tokens: int | None = 64
    extra_config: dict[str, Any] | None = None


class ModelTestResult(BaseModel):
    ok: bool
    message: str
    latency_ms: int = 0
    reply_preview: str | None = None


class AnalysisResultOut(BaseModel):
    """分析完成后的摘要响应。"""

    knowledge_id: str
    analysis_status: str
    summary: str | None = None
    category: str | None = None
    keywords: list[str] = Field(default_factory=list)
    analyzed_by_model: str | None = None
    analysis_error: str | None = None
    source: str  # ai | local
