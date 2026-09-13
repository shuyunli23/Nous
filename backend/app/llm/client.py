"""LLM client with pluggable providers.

The active provider comes from the runtime store (configured in the UI) and
falls back to ``.env``; see ``app.llm.provider_store.resolve_llm``. Callers use
the same three entry points regardless of which vendor or protocol is active:

- :func:`chat_complete` -- blocking completion
- :func:`chat_stream` -- async generator of text chunks
- :func:`structured_complete` -- JSON mode + Pydantic validation

Protocol handling splits by ``ResolvedLLM.kind``: OpenAI-compatible HTTP lives
here, AWS Bedrock in :mod:`app.llm.bedrock`.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.exceptions import LLMError
from app.core.logging import get_logger
from app.llm.provider_store import resolve_llm
from app.llm.providers import ResolvedLLM
from app.llm.token_limits import clamp_request_max_tokens

logger = get_logger(__name__)


def _config_for_call(config: ResolvedLLM | None) -> ResolvedLLM:
    if config is not None:
        return config
    from app.llm.usage import current_usage_meta

    meta = current_usage_meta()
    return resolve_llm(purpose=meta.purpose, provider_id=meta.provider_id)

# ---- types ---------------------------------------------------------------

Message = dict[str, Any]  # {"role": str, "content": str, "tool_calls"?: ...}


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class CompletionResult(BaseModel):
    content: str
    tool_calls: list[dict[str, Any]] = []
    usage: Usage = Usage()
    finish_reason: str = "stop"


# ---- helpers -------------------------------------------------------------


def _build_headers(cfg: ResolvedLLM) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
        return headers

    # Self-hosted servers (Ollama, vLLM) accept unauthenticated calls, but an
    # empty .env key is almost always an unfinished setup rather than a choice.
    if cfg.source == "env":
        raise LLMError(
            "LLM API key not configured. Add a provider on the settings page, "
            "or set LLM_API_KEY in your .env file.",
            details={
                "hint": "打开「模型设置」页面添加供应商，"
                "或复制 .env.example 为 .env 并填写 LLM_API_KEY。",
            },
        )
    return headers


def _chat_url(cfg: ResolvedLLM) -> str:
    if not cfg.base_url:
        raise LLMError(
            f"Provider '{cfg.label}' has no base_url configured.",
            details={"provider_id": cfg.provider_id},
        )
    return f"{cfg.base_url.rstrip('/')}/chat/completions"


# ---- client --------------------------------------------------------------


async def chat_complete(
    messages: list[Message],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] = "auto",
    response_format: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    config: ResolvedLLM | None = None,
    on_text: Callable[[str], None] | None = None,
) -> CompletionResult:
    """Completion call, optionally streaming text deltas via ``on_text``.

    ``config`` overrides the active provider, which lets the settings API test
    a draft provider without saving or activating it.

    When ``on_text`` is set (and JSON mode is not requested), tokens are
    forwarded as they arrive so the chat UI can paint the reply live. Tool-call
    fragments are still assembled into a normal ``CompletionResult``.
    """
    cfg = _config_for_call(config)
    stream = on_text is not None and response_format is None

    if cfg.kind == "bedrock":
        from app.llm.bedrock import bedrock_chat_complete, bedrock_chat_complete_stream

        if stream:
            result = await bedrock_chat_complete_stream(
                cfg,
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                on_text=on_text,
            )
        else:
            result = await bedrock_chat_complete(
                cfg,
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                response_format=response_format,
            )
    elif stream:
        result = await _openai_chat_complete_stream(
            cfg,
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            extra=extra,
            on_text=on_text,
        )
    else:
        result = await _openai_chat_complete(
            cfg,
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            extra=extra,
        )
    await _record_usage(cfg, result.usage, model=model)
    return result


async def _openai_chat_complete(
    cfg: ResolvedLLM,
    messages: list[Message],
    *,
    model: str | None,
    temperature: float | None,
    max_tokens: int | None,
    tools: list[dict[str, Any]] | None,
    tool_choice: str | dict[str, Any],
    response_format: dict[str, Any] | None,
    extra: dict[str, Any] | None,
) -> CompletionResult:
    payload = _build_payload(
        cfg,
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        tool_choice=tool_choice,
        response_format=response_format,
        stream=False,
        extra=extra,
    )

    async with httpx.AsyncClient(
        timeout=cfg.timeout_seconds,
        headers=_build_headers(cfg),
    ) as client:
        for attempt in range(1, cfg.max_retries + 2):
            try:
                resp = await client.post(_chat_url(cfg), json=payload)
                resp.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                body = exc.response.text[:500]
                if exc.response.status_code in {429, 500, 502, 503, 504}:
                    if attempt <= cfg.max_retries:
                        logger.warning(
                            "llm_retry",
                            status=exc.response.status_code,
                            attempt=attempt,
                            provider=cfg.label,
                        )
                        await asyncio.sleep(2**attempt)
                        continue
                raise LLMError(
                    f"LLM request failed: {exc.response.status_code}",
                    details={
                        "body": body,
                        "provider": cfg.label,
                        "model": model or cfg.model,
                    },
                ) from exc
            except httpx.TimeoutException as exc:
                raise LLMError(
                    "LLM request timed out.",
                    details={"provider": cfg.label, "timeout": cfg.timeout_seconds},
                ) from exc
            except httpx.HTTPError as exc:
                raise LLMError(
                    f"Could not reach the LLM endpoint: {exc}",
                    details={"provider": cfg.label, "base_url": cfg.base_url},
                ) from exc

    return _parse_response(resp.json())


async def _openai_chat_complete_stream(
    cfg: ResolvedLLM,
    messages: list[Message],
    *,
    model: str | None,
    temperature: float | None,
    max_tokens: int | None,
    tools: list[dict[str, Any]] | None,
    tool_choice: str | dict[str, Any],
    extra: dict[str, Any] | None,
    on_text: Callable[[str], None],
) -> CompletionResult:
    payload = _build_payload(
        cfg,
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        tool_choice=tool_choice,
        stream=True,
        extra=extra,
    )

    content_parts: list[str] = []
    tool_acc: dict[int, dict[str, Any]] = {}
    finish_reason = "stop"
    usage = Usage()

    async with httpx.AsyncClient(
        timeout=cfg.timeout_seconds,
        headers=_build_headers(cfg),
    ) as client:
        try:
            async with client.stream("POST", _chat_url(cfg), json=payload) as resp:
                try:
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    body = (await exc.response.aread())[:500].decode(
                        "utf-8", errors="replace"
                    )
                    raise LLMError(
                        f"LLM stream failed: {exc.response.status_code}",
                        details={
                            "body": body,
                            "provider": cfg.label,
                            "model": model or cfg.model,
                        },
                    ) from exc
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
                    parsed = _ingest_openai_chunk(
                        chunk,
                        content_parts=content_parts,
                        tool_acc=tool_acc,
                        on_text=on_text,
                    )
                    if parsed.finish_reason:
                        finish_reason = parsed.finish_reason
                    if parsed.usage is not None:
                        usage = parsed.usage
        except LLMError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMError(
                "LLM request timed out.",
                details={"provider": cfg.label, "timeout": cfg.timeout_seconds},
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(
                f"Could not reach the LLM endpoint: {exc}",
                details={"provider": cfg.label, "base_url": cfg.base_url},
            ) from exc

    tool_calls = [tool_acc[idx] for idx in sorted(tool_acc)]
    return CompletionResult(
        content="".join(content_parts),
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        usage=usage,
    )


class _ChunkParse:
    finish_reason: str | None = None
    usage: Usage | None = None


def _ingest_openai_chunk(
    chunk: dict[str, Any],
    *,
    content_parts: list[str],
    tool_acc: dict[int, dict[str, Any]],
    on_text: Callable[[str], None] | None,
) -> _ChunkParse:
    """Fold one OpenAI SSE JSON object into the running completion."""
    out = _ChunkParse()
    usage_raw = chunk.get("usage")
    if isinstance(usage_raw, dict):
        out.usage = Usage(
            prompt_tokens=usage_raw.get("prompt_tokens", 0) or 0,
            completion_tokens=usage_raw.get("completion_tokens", 0) or 0,
            total_tokens=usage_raw.get("total_tokens", 0) or 0,
        )

    choices = chunk.get("choices") or []
    if not choices:
        return out

    choice = choices[0] or {}
    if choice.get("finish_reason"):
        out.finish_reason = str(choice["finish_reason"])

    delta = choice.get("delta") or choice.get("message") or {}
    text = delta.get("content")
    if isinstance(text, str) and text:
        content_parts.append(text)
        if on_text is not None:
            on_text(text)

    for tc in delta.get("tool_calls") or []:
        if not isinstance(tc, dict):
            continue
        idx = int(tc.get("index") or 0)
        slot = tool_acc.setdefault(
            idx,
            {
                "id": "",
                "type": "function",
                "function": {"name": "", "arguments": ""},
            },
        )
        if tc.get("id"):
            slot["id"] = tc["id"]
        if tc.get("type"):
            slot["type"] = tc["type"]
        fn = tc.get("function") or {}
        if fn.get("name"):
            slot["function"]["name"] += fn["name"]
        if fn.get("arguments"):
            slot["function"]["arguments"] += fn["arguments"]

    return out


async def _record_usage(cfg: ResolvedLLM, usage: Usage, *, model: str | None) -> None:
    from app.llm.usage import record_completion

    await record_completion(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        model=model or cfg.model,
        provider_id=cfg.provider_id,
        provider_label=cfg.label,
    )


async def chat_stream(
    messages: list[Message],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    config: ResolvedLLM | None = None,
) -> AsyncIterator[str]:
    """Yield text deltas from a streaming completion."""
    cfg = _config_for_call(config)

    if cfg.kind == "bedrock":
        from app.llm.bedrock import bedrock_chat_stream

        async for chunk in bedrock_chat_stream(
            cfg,
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        ):
            yield chunk
        return

    payload = _build_payload(
        cfg,
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        stream=True,
    )

    async with httpx.AsyncClient(
        timeout=cfg.timeout_seconds,
        headers=_build_headers(cfg),
    ) as client:
        async with client.stream("POST", _chat_url(cfg), json=payload) as resp:
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise LLMError(
                    f"LLM stream failed: {exc.response.status_code}",
                    details={"provider": cfg.label},
                ) from exc
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if raw == "[DONE]":
                    break
                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                delta = chunk["choices"][0].get("delta", {})
                text = delta.get("content") or ""
                if text:
                    yield text


async def structured_complete(
    messages: list[Message],
    schema: type[BaseModel],
    *,
    model: str | None = None,
    config: ResolvedLLM | None = None,
) -> BaseModel:
    """Ask the model to reply in JSON and parse into ``schema``."""
    result = await chat_complete(
        messages,
        model=model,
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=4096,
        config=config,
    )
    try:
        data = _loads_json_object(result.content)
        return schema.model_validate(data)
    except Exception as exc:
        raise LLMError(
            "LLM returned invalid JSON for structured output.",
            details={
                "raw": (result.content or "")[:300],
                "error": str(exc),
                "finish_reason": result.finish_reason,
            },
        ) from exc


# ---- private -------------------------------------------------------------


def _strip_json_fence(text: str) -> str:
    """Unwrap ```json fences, which providers without JSON mode often add."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    body = stripped[3:]
    if body[:4].lower().startswith("json"):
        body = body[4:]
    fence_end = body.rfind("```")
    if fence_end != -1:
        body = body[:fence_end]
    return body.strip()


def _loads_json_object(text: str) -> Any:
    """Parse a JSON object, tolerating markdown fences and leading chatter."""
    stripped = _strip_json_fence(text)
    if not stripped:
        raise json.JSONDecodeError("Expecting value", stripped, 0)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def _build_payload(
    cfg: ResolvedLLM,
    messages: list[Message],
    *,
    model: str | None,
    temperature: float | None,
    max_tokens: int | None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] = "auto",
    response_format: dict[str, Any] | None = None,
    stream: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model or cfg.model,
        "messages": messages,
        "temperature": temperature if temperature is not None else cfg.temperature,
        "max_tokens": clamp_request_max_tokens(
            cfg.kind, model or cfg.model, max_tokens, cfg.max_tokens
        ),
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice
    if response_format:
        payload["response_format"] = response_format
    if extra:
        payload.update(extra)
    return payload


def _parse_response(data: dict[str, Any]) -> CompletionResult:
    try:
        choice = data["choices"][0]
        msg = choice.get("message", {})
        usage_raw = data.get("usage") or {}
        return CompletionResult(
            content=msg.get("content") or "",
            tool_calls=msg.get("tool_calls") or [],
            finish_reason=choice.get("finish_reason", "stop"),
            usage=Usage(
                prompt_tokens=usage_raw.get("prompt_tokens", 0),
                completion_tokens=usage_raw.get("completion_tokens", 0),
                total_tokens=usage_raw.get("total_tokens", 0),
            ),
        )
    except (KeyError, IndexError) as exc:
        raise LLMError(
            "Unexpected LLM response shape.", details={"raw": str(data)[:300]}
        ) from exc
