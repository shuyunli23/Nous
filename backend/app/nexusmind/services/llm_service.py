"""多服务商 LLM 适配层。

协议族：
- openai_compatible: OpenAI / Azure / DeepSeek / Qwen / 智谱 / 火山 / Ollama / Custom
- anthropic: Claude Messages API
- gemini: Google Generative Language API
- bedrock: Amazon Bedrock Converse API（boto3）
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.nexusmind.config import settings
from app.nexusmind.models.model_config import LLMProvider, ModelConfig
from app.nexusmind.utils.errors import ExternalServiceError, ValidationError

logger = logging.getLogger(__name__)

OPENAI_COMPATIBLE = {
    LLMProvider.OPENAI,
    LLMProvider.AZURE_OPENAI,
    LLMProvider.DEEPSEEK,
    LLMProvider.QWEN,
    LLMProvider.ZHIPU,
    LLMProvider.VOLCENGINE,
    LLMProvider.OLLAMA,
    LLMProvider.CUSTOM,
}

# 不依赖 HTTP base_url 的服务商
NO_BASE_URL_REQUIRED = {
    LLMProvider.OLLAMA,
    LLMProvider.AWS,
}


@dataclass
class ChatResult:
    content: str
    latency_ms: int
    raw: dict[str, Any] | None = None


@dataclass
class ModelEndpoint:
    provider: str
    api_key: str
    base_url: str
    model_name: str
    temperature: float = 0.2
    max_tokens: int = 2048
    extra_config: dict[str, Any] | None = None

    @classmethod
    def from_config(cls, cfg: ModelConfig) -> "ModelEndpoint":
        return cls(
            provider=cfg.provider,
            api_key=cfg.api_key or "",
            base_url=cfg.resolved_base_url,
            model_name=cfg.model_name,
            temperature=float(cfg.temperature),
            max_tokens=int(cfg.max_tokens),
            extra_config=cfg.extra_config or {},
        )


ANALYSIS_SYSTEM_PROMPT = """你是个人知识管理系统的分析助手。请阅读用户提供的知识文档，提取结构化元数据。
只输出合法 JSON，不要 Markdown 代码块，不要额外解释。
JSON 字段：
{
  "keywords": ["5到10个核心关键词"],
  "category": "技术领域，如 Frontend/Backend/DevOps/AI/Database/Mobile/General",
  "summary": "一句话中文摘要",
  "search_keywords": ["适合搜索的关键词，可与 keywords 重叠"]
}"""


def build_analysis_user_prompt(title: str, content: str) -> str:
    clipped = content[: settings.AI_MAX_INPUT_CHARS]
    return (
        "请分析下面的知识文档：\n"
        "1. 提取5-10个核心关键词\n"
        "2. 提取技术领域\n"
        "3. 提取知识主题（体现在 summary）\n"
        "4. 提取一句话摘要\n"
        "5. 提取适合搜索的关键词\n\n"
        f"标题：{title or '（无标题）'}\n\n"
        f"正文：\n{clipped}"
    )


async def chat_completion(
    endpoint: ModelEndpoint,
    *,
    system: str,
    user: str,
    timeout: int | None = None,
    on_text: Callable[[str], None] | None = None,
) -> ChatResult:
    """统一聊天补全入口。"""
    if not endpoint.model_name.strip():
        raise ValidationError("模型名称不能为空")
    if not endpoint.base_url.strip() and endpoint.provider not in NO_BASE_URL_REQUIRED:
        raise ValidationError("Base URL 不能为空，请填写或选择带默认地址的服务商")

    provider = endpoint.provider
    started = time.perf_counter()

    if provider in OPENAI_COMPATIBLE:
        content, raw = await _chat_openai_compatible(
            endpoint, system=system, user=user, timeout=timeout, on_text=on_text
        )
    elif provider == LLMProvider.ANTHROPIC:
        content, raw = await _chat_anthropic(endpoint, system=system, user=user, timeout=timeout)
    elif provider == LLMProvider.GEMINI:
        content, raw = await _chat_gemini(endpoint, system=system, user=user, timeout=timeout)
    elif provider == LLMProvider.AWS:
        content, raw = await _chat_aws_bedrock(endpoint, system=system, user=user, timeout=timeout)
    else:
        raise ValidationError(f"暂不支持的服务商协议: {provider}")

    if on_text is not None and provider not in OPENAI_COMPATIBLE and content:
        on_text(content)

    latency = int((time.perf_counter() - started) * 1000)
    return ChatResult(content=content.strip(), latency_ms=latency, raw=raw)


async def test_connection(endpoint: ModelEndpoint) -> ChatResult:
    return await chat_completion(
        endpoint,
        system="You are a connectivity probe. Reply with exactly: ok",
        user="ping",
        timeout=min(30, settings.AI_REQUEST_TIMEOUT),
    )


async def analyze_document(endpoint: ModelEndpoint, *, title: str, content: str) -> dict[str, Any]:
    result = await chat_completion(
        endpoint,
        system=ANALYSIS_SYSTEM_PROMPT,
        user=build_analysis_user_prompt(title, content),
        timeout=settings.AI_REQUEST_TIMEOUT,
    )
    parsed = parse_json_object(result.content)
    keywords = _as_str_list(parsed.get("keywords"))
    search_keywords = _as_str_list(parsed.get("search_keywords")) or keywords
    # 合并去重，keywords 优先
    merged: list[str] = []
    seen: set[str] = set()
    for item in keywords + search_keywords:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item.strip())
    return {
        "keywords": merged[:12],
        "keyword_weights": [(k, 1.0 - i * 0.03) for i, k in enumerate(merged[:12])],
        "category": str(parsed.get("category") or "General").strip()[:64] or "General",
        "summary": str(parsed.get("summary") or "").strip()[:500],
        "search_keywords": search_keywords,
        "model_reply": result.content,
        "latency_ms": result.latency_ms,
    }


def parse_json_object(text: str) -> dict[str, Any]:
    """从模型输出中尽量提取 JSON 对象。"""
    raw = (text or "").strip()
    if not raw:
        raise ExternalServiceError("模型返回为空")

    # 去掉 ```json 包裹
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as exc:
            raise ExternalServiceError(f"无法解析模型 JSON：{exc}") from exc

    raise ExternalServiceError("模型未返回合法 JSON 对象")


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if item is None:
            continue
        s = str(item).strip()
        if s:
            out.append(s[:64])
    return out


async def _chat_openai_compatible(
    endpoint: ModelEndpoint,
    *,
    system: str,
    user: str,
    timeout: int | None,
    on_text: Callable[[str], None] | None = None,
) -> tuple[str, dict[str, Any]]:
    base = endpoint.base_url.rstrip("/")
    extra = endpoint.extra_config or {}

    if endpoint.provider == LLMProvider.AZURE_OPENAI:
        # 支持完整 deployment URL 或资源根 URL
        if "/chat/completions" in base:
            url = base
        elif "/deployments/" in base:
            url = f"{base}/chat/completions"
        else:
            # https://xxx.openai.azure.com + deployment name = model_name
            url = f"{base}/openai/deployments/{endpoint.model_name}/chat/completions"
        api_version = str(extra.get("api_version") or "2024-02-15-preview")
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}api-version={api_version}"
        headers = {
            "api-key": endpoint.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": endpoint.temperature,
            "max_tokens": endpoint.max_tokens,
        }
    else:
        url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if endpoint.api_key:
            headers["Authorization"] = f"Bearer {endpoint.api_key}"
        payload = {
            "model": endpoint.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": endpoint.temperature,
            "max_tokens": endpoint.max_tokens,
        }

    if on_text is not None:
        return await _chat_openai_compatible_stream(
            url, headers=headers, payload=payload, timeout=timeout, on_text=on_text
        )

    data = await _post_json(url, headers=headers, payload=payload, timeout=timeout)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ExternalServiceError(f"OpenAI 兼容响应格式异常: {data}") from exc
    return str(content or ""), data


async def _chat_openai_compatible_stream(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int | None,
    on_text: Callable[[str], None],
) -> tuple[str, dict[str, Any]]:
    to = timeout or settings.AI_REQUEST_TIMEOUT
    body = {**payload, "stream": True}
    parts: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=to) as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                if resp.status_code >= 400:
                    detail = (await resp.aread())[:500].decode("utf-8", errors="replace")
                    raise ExternalServiceError(f"HTTP {resp.status_code}: {detail}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0] or {}).get("delta") or {}
                    text = delta.get("content")
                    if isinstance(text, str) and text:
                        parts.append(text)
                        on_text(text)
    except ExternalServiceError:
        raise
    except httpx.TimeoutException as exc:
        raise ExternalServiceError(f"请求超时（{to}s）") from exc
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"网络错误: {exc}") from exc
    return "".join(parts), {}


async def _chat_anthropic(
    endpoint: ModelEndpoint,
    *,
    system: str,
    user: str,
    timeout: int | None,
) -> tuple[str, dict[str, Any]]:
    if not endpoint.api_key:
        raise ValidationError("Anthropic 需要 API Key")
    base = endpoint.base_url.rstrip("/")
    url = base if base.endswith("/messages") else f"{base}/messages"
    headers = {
        "x-api-key": endpoint.api_key,
        "anthropic-version": str((endpoint.extra_config or {}).get("anthropic_version") or "2023-06-01"),
        "Content-Type": "application/json",
    }
    payload = {
        "model": endpoint.model_name,
        "max_tokens": endpoint.max_tokens,
        "temperature": endpoint.temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    data = await _post_json(url, headers=headers, payload=payload, timeout=timeout)
    try:
        blocks = data.get("content") or []
        texts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
        content = "\n".join(t for t in texts if t)
    except Exception as exc:  # noqa: BLE001
        raise ExternalServiceError(f"Anthropic 响应格式异常: {data}") from exc
    return content, data


async def _chat_gemini(
    endpoint: ModelEndpoint,
    *,
    system: str,
    user: str,
    timeout: int | None,
) -> tuple[str, dict[str, Any]]:
    if not endpoint.api_key:
        raise ValidationError("Gemini 需要 API Key")
    base = endpoint.base_url.rstrip("/")
    # https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
    if ":generateContent" in base:
        url = base
    else:
        url = f"{base}/models/{endpoint.model_name}:generateContent"
    url = f"{url}?key={endpoint.api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": endpoint.temperature,
            "maxOutputTokens": endpoint.max_tokens,
        },
    }
    data = await _post_json(url, headers=headers, payload=payload, timeout=timeout)
    try:
        parts = data["candidates"][0]["content"]["parts"]
        content = "".join(str(p.get("text", "")) for p in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise ExternalServiceError(f"Gemini 响应格式异常: {data}") from exc
    return content, data


async def _chat_aws_bedrock(
    endpoint: ModelEndpoint,
    *,
    system: str,
    user: str,
    timeout: int | None,
) -> tuple[str, dict[str, Any]]:
    """Amazon Bedrock Runtime Converse API。

    凭证约定：
    - api_key → AWS Access Key ID（可留空，走环境变量 / IAM 角色）
    - extra_config.aws_secret_access_key → Secret Access Key
    - extra_config.region → 区域，默认 us-east-1
    - extra_config.aws_session_token → 可选临时凭证
    - model_name → Bedrock modelId / inference profile
    """
    extra = endpoint.extra_config or {}
    region = str(extra.get("region") or "us-east-1").strip() or "us-east-1"
    secret = str(extra.get("aws_secret_access_key") or "").strip()
    session_token = str(extra.get("aws_session_token") or "").strip() or None
    access_key = (endpoint.api_key or "").strip()

    if access_key and not secret:
        raise ValidationError("AWS 已填写 Access Key 时，还需提供 Secret Access Key")
    if secret and not access_key:
        raise ValidationError("AWS 已填写 Secret 时，还需提供 Access Key ID")

    to = timeout or settings.AI_REQUEST_TIMEOUT

    def _invoke() -> dict[str, Any]:
        try:
            import boto3
            from botocore.config import Config as BotoConfig
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError as exc:  # pragma: no cover
            raise ExternalServiceError("未安装 boto3，请执行 pip install boto3") from exc

        client_kwargs: dict[str, Any] = {
            "service_name": "bedrock-runtime",
            "region_name": region,
            "config": BotoConfig(
                connect_timeout=min(30, to),
                read_timeout=to,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        }
        if access_key and secret:
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret
            if session_token:
                client_kwargs["aws_session_token"] = session_token

        # 可选自定义 endpoint（例如 VPC endpoint）
        if endpoint.base_url.strip():
            client_kwargs["endpoint_url"] = endpoint.base_url.rstrip("/")

        client = boto3.client(**client_kwargs)
        try:
            return client.converse(
                modelId=endpoint.model_name,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={
                    "temperature": float(endpoint.temperature),
                    "maxTokens": int(endpoint.max_tokens),
                },
            )
        except ClientError as exc:
            err = exc.response.get("Error", {}) if hasattr(exc, "response") else {}
            code = err.get("Code", "ClientError")
            msg = err.get("Message") or str(exc)
            raise ExternalServiceError(f"AWS Bedrock {code}: {msg}") from exc
        except BotoCoreError as exc:
            raise ExternalServiceError(f"AWS Bedrock 网络/凭证错误: {exc}") from exc

    try:
        data = await asyncio.wait_for(asyncio.to_thread(_invoke), timeout=to + 5)
    except TimeoutError as exc:
        raise ExternalServiceError(f"请求超时（{to}s）") from exc

    try:
        blocks = data["output"]["message"]["content"]
        texts = [
            str(b.get("text", ""))
            for b in blocks
            if isinstance(b, dict) and b.get("text")
        ]
        content = "\n".join(t for t in texts if t)
    except (KeyError, IndexError, TypeError) as exc:
        raise ExternalServiceError(f"AWS Bedrock 响应格式异常: {data}") from exc
    return content, data


async def _post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int | None,
) -> dict[str, Any]:
    to = timeout or settings.AI_REQUEST_TIMEOUT
    try:
        async with httpx.AsyncClient(timeout=to) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise ExternalServiceError(f"请求超时（{to}s）") from exc
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"网络错误: {exc}") from exc

    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise ExternalServiceError(f"HTTP {resp.status_code}: {detail}")

    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        raise ExternalServiceError("响应不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise ExternalServiceError("响应 JSON 必须是对象")
    return data
