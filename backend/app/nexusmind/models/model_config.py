"""AI 模型配置模型 —— 支撑「模型管理中心」。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.nexusmind.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LLMProvider(StrEnum):
    """支持的模型服务商。

    绝大多数厂商都提供 OpenAI 兼容端点，因此适配层只需区分四种协议族：
    openai 兼容 / anthropic / gemini / aws bedrock。这里仍然分开枚举，
    是为了能给出各自的默认 base_url 与更精准的错误提示。
    """

    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    AWS = "aws"              # Amazon Bedrock
    DEEPSEEK = "deepseek"
    QWEN = "qwen"            # 通义千问 / 阿里云百炼
    ZHIPU = "zhipu"          # 智谱 GLM
    VOLCENGINE = "volcengine"  # 火山方舟
    OLLAMA = "ollama"
    CUSTOM = "custom"        # 任意 OpenAI 兼容端点


# 各服务商默认的 API 入口，用户不填 base_url 时使用
PROVIDER_DEFAULT_BASE_URL: dict[str, str] = {
    LLMProvider.OPENAI: "https://api.openai.com/v1",
    LLMProvider.AZURE_OPENAI: "",  # Azure 必须由用户提供资源专属地址
    LLMProvider.ANTHROPIC: "https://api.anthropic.com/v1",
    LLMProvider.GEMINI: "https://generativelanguage.googleapis.com/v1beta",
    LLMProvider.AWS: "",  # Bedrock 按 region 走 boto3，无需 HTTP base_url
    LLMProvider.DEEPSEEK: "https://api.deepseek.com/v1",
    LLMProvider.QWEN: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    LLMProvider.ZHIPU: "https://open.bigmodel.cn/api/paas/v4",
    LLMProvider.VOLCENGINE: "https://ark.cn-beijing.volces.com/api/v3",
    LLMProvider.OLLAMA: "http://localhost:11434/v1",
    LLMProvider.CUSTOM: "",
}


class ModelConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """一条模型配置（Provider + Key + BaseURL + ModelName）。

    允许保存多条，其中 `is_default=True` 的那条会被 AI 分析流程默认选用。
    """

    __tablename__ = "model_config"

    # 用户自定义别名，例如 "工作用 GPT-5"
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # 明文存储在本地 SQLite。本项目定位为单机个人工具，
    # 若要部署到多用户环境，应在此处接入 KMS / 对称加密。
    api_key: Mapped[str] = mapped_column(Text, default="", nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # 采样参数
    temperature: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 连通性测试结果
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, default=None)
    last_test_message: Mapped[str | None] = mapped_column(Text, default=None)

    # 预留：Azure api-version、自定义 headers、代理等
    extra_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    @property
    def resolved_base_url(self) -> str:
        """用户未填写时回落到服务商默认地址。"""
        return (self.base_url or PROVIDER_DEFAULT_BASE_URL.get(self.provider, "")).rstrip("/")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ModelConfig {self.name} ({self.provider}/{self.model_name})>"
