"""AWS Bedrock adapter using the Converse API.

Bedrock needs SigV4 signed requests and a different payload shape than the
OpenAI chat-completions schema the rest of the app speaks, so this module
translates in both directions and exposes the same ``CompletionResult``.

boto3 is an optional dependency (``requirements-aws.txt``) and is imported
lazily so installs that never touch Bedrock stay slim. Its client is
synchronous, so calls run in a worker thread to keep the event loop free.
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any

from app.core.exceptions import LLMError
from app.core.logging import get_logger
from app.llm.token_limits import clamp_request_max_tokens

if TYPE_CHECKING:
    from app.llm.client import CompletionResult, Message
    from app.llm.providers import ResolvedLLM

logger = get_logger(__name__)

# Bedrock stop reasons -> OpenAI finish_reason vocabulary.
_STOP_REASON_MAP = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "tool_use": "tool_calls",
    "max_tokens": "length",
    "content_filtered": "content_filter",
    "guardrail_intervened": "content_filter",
}

# boto3 clients are expensive to build (~100ms), so reuse them per credential set.
_client_cache: dict[tuple[str | None, ...], Any] = {}
_cache_lock = asyncio.Lock()


def _import_boto3() -> Any:
    try:
        import boto3  # noqa: PLC0415  (deliberately lazy)
    except ImportError as exc:
        raise LLMError(
            "AWS Bedrock support requires boto3, which is not installed.",
            details={"hint": "pip install -r requirements-aws.txt"},
        ) from exc
    return boto3


def _cache_key(cfg: ResolvedLLM) -> tuple[str | None, ...]:
    return (
        cfg.aws_region,
        cfg.aws_profile_name,
        cfg.aws_access_key_id,
        cfg.aws_secret_access_key,
        cfg.aws_session_token,
    )


def _build_client(cfg: ResolvedLLM) -> Any:
    """Create a ``bedrock-runtime`` client for this provider's credentials.

    Explicit keys win; otherwise a named profile is used; otherwise boto3's
    default credential chain (env vars, SSO, instance role) applies.
    """
    boto3 = _import_boto3()
    session_kwargs: dict[str, Any] = {"region_name": cfg.aws_region}
    if cfg.aws_access_key_id and cfg.aws_secret_access_key:
        session_kwargs["aws_access_key_id"] = cfg.aws_access_key_id
        session_kwargs["aws_secret_access_key"] = cfg.aws_secret_access_key
        if cfg.aws_session_token:
            session_kwargs["aws_session_token"] = cfg.aws_session_token
    elif cfg.aws_profile_name:
        session_kwargs["profile_name"] = cfg.aws_profile_name

    try:
        from botocore.config import Config  # noqa: PLC0415  (lazy, like boto3)

        session = boto3.Session(**session_kwargs)
        return session.client(
            "bedrock-runtime",
            # botocore defaults to a 60s read timeout, which a thinking model can
            # exceed between two stream events -- and no TCP keepalive, so an idle
            # connection is fair game for any middlebox. Both showed up as
            # ``ProtocolError: Response ended prematurely`` mid-stream. The knobs
            # reuse the provider's own timeout/retry settings rather than adding
            # new ones. Note these retries cannot cover a break that happens
            # *during* streaming -- bedrock_chat_complete_stream handles that.
            config=Config(
                read_timeout=cfg.timeout_seconds,
                connect_timeout=cfg.timeout_seconds,
                tcp_keepalive=True,
                retries={"max_attempts": cfg.max_retries + 1, "mode": "standard"},
            ),
        )
    except Exception as exc:  # botocore raises many distinct credential errors
        raise LLMError(
            f"Could not initialise AWS Bedrock client: {exc}",
            details={"region": cfg.aws_region, "profile": cfg.aws_profile_name},
        ) from exc


async def _get_client(cfg: ResolvedLLM) -> Any:
    key = _cache_key(cfg)
    cached = _client_cache.get(key)
    if cached is not None:
        return cached
    async with _cache_lock:
        cached = _client_cache.get(key)
        if cached is None:
            cached = await asyncio.to_thread(_build_client, cfg)
            _client_cache[key] = cached
    return cached


def clear_client_cache() -> None:
    """Forget cached clients, e.g. after credentials change."""
    _client_cache.clear()


# ---- payload translation -------------------------------------------------


def _text_blocks(content: Any) -> list[dict[str, Any]]:
    """Normalise OpenAI message content into Converse text / image blocks."""
    if content is None:
        return []
    if isinstance(content, str):
        return [{"text": content}] if content.strip() else []
    if isinstance(content, list):
        blocks: list[dict[str, Any]] = []
        for part in content:
            if isinstance(part, str) and part.strip():
                blocks.append({"text": part})
                continue
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type == "text":
                text = str(part.get("text") or "")
                if text.strip():
                    blocks.append({"text": text})
            elif part_type == "image_url":
                image = _data_url_to_bedrock_image(part.get("image_url"))
                if image:
                    blocks.append(image)
            elif part_type == "image" and isinstance(part.get("image"), dict):
                blocks.append({"image": part["image"]})
        return blocks
    return [{"text": str(content)}]


_BEDROCK_IMAGE_FORMATS = {
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


def _data_url_to_bedrock_image(image_url: Any) -> dict[str, Any] | None:
    """Convert an OpenAI ``image_url`` data URL into a Converse image block."""
    url = ""
    if isinstance(image_url, dict):
        url = str(image_url.get("url") or "")
    elif isinstance(image_url, str):
        url = image_url
    if not url.startswith("data:"):
        return None
    header, _, b64 = url.partition(",")
    mime = header[5:].split(";")[0].strip().lower()
    fmt = _BEDROCK_IMAGE_FORMATS.get(mime)
    if not fmt or not b64:
        return None
    try:
        raw = base64.b64decode(b64)
    except Exception:
        return None
    if not raw:
        return None
    return {"image": {"format": fmt, "source": {"bytes": raw}}}


def _tool_use_blocks(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for call in tool_calls:
        fn = call.get("function") or {}
        raw_args = fn.get("arguments")
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args) if raw_args.strip() else {}
            except json.JSONDecodeError:
                args = {"_raw": raw_args}
        else:
            args = raw_args or {}
        blocks.append(
            {
                "toolUse": {
                    "toolUseId": str(call.get("id") or fn.get("name") or "tool"),
                    "name": str(fn.get("name") or "tool"),
                    "input": args,
                }
            }
        )
    return blocks


def to_converse_messages(
    messages: list[Message],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split OpenAI-style messages into Converse ``(system, messages)``.

    Converse requires alternating user/assistant turns starting with the user,
    so consecutive same-role messages are merged.
    """
    system: list[dict[str, Any]] = []
    converted: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role")
        if role == "system":
            system.extend(_text_blocks(msg.get("content")))
            continue

        if role == "tool":
            # Tool results are carried on a user turn in the Converse schema.
            block = {
                "toolResult": {
                    "toolUseId": str(msg.get("tool_call_id") or "tool"),
                    "content": _text_blocks(msg.get("content")) or [{"text": ""}],
                }
            }
            converted.append({"role": "user", "content": [block]})
            continue

        if role == "assistant":
            content = _text_blocks(msg.get("content"))
            if msg.get("tool_calls"):
                content += _tool_use_blocks(msg["tool_calls"])
            if not content:
                continue
            converted.append({"role": "assistant", "content": content})
            continue

        # Default: treat anything else as a user turn.
        content = _text_blocks(msg.get("content"))
        if content:
            converted.append({"role": "user", "content": content})

    merged: list[dict[str, Any]] = []
    for msg in converted:
        if merged and merged[-1]["role"] == msg["role"]:
            merged[-1]["content"] = merged[-1]["content"] + msg["content"]
        else:
            merged.append(dict(msg))

    # Bedrock rejects a conversation that opens with an assistant turn.
    if merged and merged[0]["role"] == "assistant":
        merged.insert(0, {"role": "user", "content": [{"text": "(continue)"}]})

    if not merged:
        merged = [{"role": "user", "content": [{"text": "(empty)"}]}]

    return system, merged


def to_tool_config(tools: list[dict[str, Any]]) -> dict[str, Any]:
    """Translate OpenAI function tools into a Converse ``toolConfig``."""
    specs: list[dict[str, Any]] = []
    for tool in tools:
        fn = tool.get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        specs.append(
            {
                "toolSpec": {
                    "name": name,
                    "description": fn.get("description") or name,
                    "inputSchema": {
                        "json": fn.get("parameters")
                        or {"type": "object", "properties": {}}
                    },
                }
            }
        )
    return {"tools": specs}


def _parse_converse_response(data: dict[str, Any]) -> CompletionResult:
    from app.llm.client import CompletionResult, Usage

    try:
        content_blocks = data["output"]["message"].get("content") or []
    except (KeyError, TypeError) as exc:
        raise LLMError(
            "Unexpected Bedrock response shape.", details={"raw": str(data)[:300]}
        ) from exc

    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in content_blocks:
        if "text" in block:
            text_parts.append(block["text"])
        elif "toolUse" in block:
            use = block["toolUse"]
            tool_calls.append(
                {
                    "id": use.get("toolUseId"),
                    "type": "function",
                    "function": {
                        "name": use.get("name"),
                        "arguments": json.dumps(
                            use.get("input") or {}, ensure_ascii=False
                        ),
                    },
                }
            )

    usage_raw = data.get("usage") or {}
    stop_reason = str(data.get("stopReason") or "end_turn")
    return CompletionResult(
        content="".join(text_parts),
        tool_calls=tool_calls,
        finish_reason=_STOP_REASON_MAP.get(stop_reason, stop_reason),
        usage=Usage(
            prompt_tokens=usage_raw.get("inputTokens", 0),
            completion_tokens=usage_raw.get("outputTokens", 0),
            total_tokens=usage_raw.get("totalTokens", 0),
        ),
    )


def _build_kwargs(
    cfg: ResolvedLLM,
    messages: list[Message],
    *,
    model: str | None,
    temperature: float | None,
    max_tokens: int | None,
    tools: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    system, converse_messages = to_converse_messages(messages)
    kwargs: dict[str, Any] = {
        "modelId": model or cfg.model,
        "messages": converse_messages,
        "inferenceConfig": {
            "temperature": temperature if temperature is not None else cfg.temperature,
            "maxTokens": clamp_request_max_tokens(
                cfg.kind, model or cfg.model, max_tokens, cfg.max_tokens
            ),
        },
    }
    if system:
        kwargs["system"] = system
    if tools:
        tool_config = to_tool_config(tools)
        if tool_config["tools"]:
            kwargs["toolConfig"] = tool_config
    return kwargs


# Failures worth retrying rather than surfacing. The second group is connection
# breakage: ``ProtocolError`` / ``ReadTimeoutError`` carry the useful word in the
# class name, not in ``str(exc)``, which is why _is_transient matches both.
_TRANSIENT_TOKENS = (
    "Throttling",
    "TooManyRequests",
    "ServiceUnavailable",
    "500",
    "Response ended prematurely",
    "IncompleteRead",
    "ProtocolError",
    "ReadTimeout",
    "ConnectionReset",
    "Connection aborted",
)


def _is_transient(exc: Exception) -> bool:
    """True for upstream hiccups: throttling, 5xx, or a dropped connection."""
    text = f"{type(exc).__name__}: {exc}"
    return any(token in text for token in _TRANSIENT_TOKENS)


def _raise_bedrock_error(exc: Exception, cfg: ResolvedLLM) -> None:
    """Map botocore failures onto ``LLMError`` with an actionable message."""
    name = type(exc).__name__
    message = str(exc)
    hint: str | None = None
    if "AccessDenied" in name or "AccessDenied" in message:
        hint = "检查 IAM 权限是否包含 bedrock:InvokeModel，以及该模型是否已在控制台申请开通。"
    elif "ValidationException" in message and "model" in message.lower():
        hint = "modelId 可能不适用于该区域，或需要使用 inference profile ID。"
    elif "UnrecognizedClientException" in message or "InvalidSignature" in message:
        hint = "Access Key / Secret 不正确。"
    elif "ExpiredToken" in message:
        hint = "临时凭证已过期，请更新 Session Token。"
    elif "NoCredentials" in name or "credential" in message.lower():
        hint = "未找到 AWS 凭证：填写 Access Key/Secret 或 Profile 名。"
    elif "ThrottlingException" in message or "TooManyRequests" in message:
        hint = "请求被限流，稍后重试。"
    elif "Response ended prematurely" in message or "ProtocolError" in name:
        hint = (
            "网络或代理把 Bedrock 的流式连接掐断了（VPN、公司代理常见）。"
            "已自动重试仍失败，稍后再试即可。"
        )

    details: dict[str, Any] = {
        "error_type": name,
        "region": cfg.aws_region,
        "model": cfg.model,
    }
    if hint:
        details["hint"] = hint
    raise LLMError(f"Bedrock request failed: {message[:400]}", details=details) from exc


# ---- public API ----------------------------------------------------------


async def bedrock_chat_complete(
    cfg: ResolvedLLM,
    messages: list[Message],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    response_format: dict[str, Any] | None = None,
) -> CompletionResult:
    """Non-streaming Bedrock completion."""
    client = await _get_client(cfg)
    kwargs = _build_kwargs(
        cfg,
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
    )

    # Converse has no JSON mode; nudge the model with an extra system block so
    # structured_complete still gets parseable output.
    if response_format and response_format.get("type") == "json_object":
        kwargs.setdefault("system", [])
        kwargs["system"] = list(kwargs["system"]) + [
            {"text": "Respond with a single valid JSON object and nothing else."}
        ]

    for attempt in range(1, cfg.max_retries + 2):
        try:
            data = await asyncio.to_thread(lambda: client.converse(**kwargs))
            return _parse_converse_response(data)
        except LLMError:
            raise
        except Exception as exc:
            if _is_transient(exc) and attempt <= cfg.max_retries:
                logger.warning("bedrock_retry", attempt=attempt, error=str(exc)[:200])
                await asyncio.sleep(2**attempt)
                continue
            _raise_bedrock_error(exc, cfg)

    raise LLMError("Bedrock request failed after retries.")


class _StreamAccumulator:
    """Completion assembled from ``converse_stream`` events, one event at a time.

    Split out of the read loop so the retry path can ask ``produced`` -- did this
    attempt get anything out before the connection died? -- which is what decides
    between restarting the call and salvaging a partial answer.
    """

    def __init__(self) -> None:
        self.text_parts: list[str] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.current: dict[str, str] | None = None
        self.stop_reason = "end_turn"
        self.usage_raw: dict[str, Any] = {}

    @property
    def produced(self) -> bool:
        """Whether anything already reached the caller (and so the UI)."""
        return bool(self.text_parts or self.tool_calls or self.current)

    @property
    def char_count(self) -> int:
        return sum(len(part) for part in self.text_parts)

    def apply(
        self, event: dict[str, Any], on_text: Callable[[str], None] | None
    ) -> None:
        start = (event.get("contentBlockStart") or {}).get("start") or {}
        tool_start = start.get("toolUse")
        if tool_start:
            self.current = {
                "id": str(tool_start.get("toolUseId") or ""),
                "name": str(tool_start.get("name") or ""),
                "input": "",
            }

        delta = (event.get("contentBlockDelta") or {}).get("delta") or {}
        text = delta.get("text")
        if text:
            self.text_parts.append(text)
            if on_text is not None:
                on_text(text)
        tool_delta = delta.get("toolUse") or {}
        fragment = tool_delta.get("input")
        if self.current is not None and fragment:
            if isinstance(fragment, dict):
                self.current["input"] = json.dumps(fragment, ensure_ascii=False)
            else:
                self.current["input"] += str(fragment)

        if "contentBlockStop" in event and self.current is not None:
            raw_input = self.current["input"] or "{}"
            try:
                parsed = json.loads(raw_input)
            except json.JSONDecodeError:
                parsed = {}
            self.tool_calls.append(
                {
                    "id": self.current["id"],
                    "type": "function",
                    "function": {
                        "name": self.current["name"],
                        "arguments": json.dumps(parsed, ensure_ascii=False)
                        if not isinstance(parsed, str)
                        else parsed,
                    },
                }
            )
            self.current = None

        message_stop = event.get("messageStop") or {}
        if message_stop.get("stopReason"):
            self.stop_reason = str(message_stop["stopReason"])

        meta_usage = (event.get("metadata") or {}).get("usage")
        if isinstance(meta_usage, dict):
            self.usage_raw = meta_usage

    def result(self, *, finish_reason: str | None = None) -> CompletionResult:
        from app.llm.client import CompletionResult, Usage  # noqa: PLC0415

        return CompletionResult(
            content="".join(self.text_parts),
            tool_calls=self.tool_calls,
            finish_reason=finish_reason
            or _STOP_REASON_MAP.get(self.stop_reason, self.stop_reason),
            usage=Usage(
                prompt_tokens=self.usage_raw.get("inputTokens", 0) or 0,
                completion_tokens=self.usage_raw.get("outputTokens", 0) or 0,
                total_tokens=self.usage_raw.get("totalTokens", 0) or 0,
            ),
        )


async def bedrock_chat_complete_stream(
    cfg: ResolvedLLM,
    messages: list[Message],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    on_text: Callable[[str], None] | None = None,
) -> CompletionResult:
    """Streaming Bedrock completion that still returns a full ``CompletionResult``.

    A ``converse_stream`` response can die halfway through -- the connection is
    open for as long as the model talks, so a proxy or an idle-connection reaper
    surfaces as ``ProtocolError: Response ended prematurely`` mid-iteration.
    Two different recoveries, because they are not the same situation:

    * Nothing decoded yet -> restart the call. No text has reached ``on_text``,
      so a restart cannot duplicate anything on screen and needs no token_clear.
    * Something decoded already -> return it with ``finish_reason="interrupted"``.
      It is on the user's screen and already paid for; verify sees the marker and
      asks the model to continue from the break instead of scrapping the turn.
    """
    client = await _get_client(cfg)
    kwargs = _build_kwargs(
        cfg,
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
    )

    for attempt in range(1, cfg.max_retries + 2):
        acc = _StreamAccumulator()
        try:
            response = await asyncio.to_thread(
                lambda: client.converse_stream(**kwargs)
            )
            sentinel = object()
            iterator = iter(response["stream"])
            while True:
                event = await asyncio.to_thread(next, iterator, sentinel)
                if event is sentinel:
                    break
                if isinstance(event, dict):
                    acc.apply(event, on_text)
        except LLMError:
            raise
        except Exception as exc:
            if acc.produced:
                logger.warning(
                    "bedrock_stream_salvaged",
                    attempt=attempt,
                    chars=acc.char_count,
                    tool_calls=len(acc.tool_calls),
                    error=str(exc)[:200],
                )
                return acc.result(finish_reason="interrupted")
            if _is_transient(exc) and attempt <= cfg.max_retries:
                logger.warning(
                    "bedrock_stream_retry", attempt=attempt, error=str(exc)[:200]
                )
                await asyncio.sleep(2**attempt)
                continue
            _raise_bedrock_error(exc, cfg)
        else:
            return acc.result()

    raise LLMError("Bedrock stream failed after retries.")


async def bedrock_chat_stream(
    cfg: ResolvedLLM,
    messages: list[Message],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> AsyncIterator[str]:
    """Yield text deltas from ``converse_stream``.

    The botocore event stream is a blocking iterator, so each item is pulled in
    a worker thread.

    No retry or salvage here, unlike ``bedrock_chat_complete_stream``: deltas are
    yielded as they arrive, so anything already handed to the caller cannot be
    taken back. A mid-stream break is only translated into ``LLMError`` so the
    caller gets a readable reason instead of a raw urllib3 exception.
    """
    client = await _get_client(cfg)
    kwargs = _build_kwargs(
        cfg,
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
    )

    try:
        response = await asyncio.to_thread(lambda: client.converse_stream(**kwargs))
    except Exception as exc:
        _raise_bedrock_error(exc, cfg)
        return

    sentinel = object()
    iterator = iter(response["stream"])

    while True:
        try:
            event = await asyncio.to_thread(next, iterator, sentinel)
        except LLMError:
            raise
        except Exception as exc:
            _raise_bedrock_error(exc, cfg)
            return
        if event is sentinel:
            break
        delta = (event or {}).get("contentBlockDelta", {}).get("delta", {})
        text = delta.get("text")
        if text:
            yield text
