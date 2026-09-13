"""Assemble OpenAI SSE deltas into a completion, including tool calls."""

from __future__ import annotations

import asyncio

from app.llm.client import _ingest_openai_chunk


def test_ingest_openai_text_deltas() -> None:
    parts: list[str] = []
    tools: dict[int, dict] = {}
    seen: list[str] = []

    first = _ingest_openai_chunk(
        {"choices": [{"delta": {"content": "你好"}}]},
        content_parts=parts,
        tool_acc=tools,
        on_text=seen.append,
    )
    second = _ingest_openai_chunk(
        {"choices": [{"delta": {"content": "世界"}, "finish_reason": "stop"}]},
        content_parts=parts,
        tool_acc=tools,
        on_text=seen.append,
    )

    assert "".join(parts) == "你好世界"
    assert seen == ["你好", "世界"]
    assert second.finish_reason == "stop"
    assert first.finish_reason is None
    assert tools == {}


def test_ingest_openai_tool_call_fragments() -> None:
    parts: list[str] = []
    tools: dict[int, dict] = {}

    _ingest_openai_chunk(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "search", "arguments": ""},
                            }
                        ]
                    }
                }
            ]
        },
        content_parts=parts,
        tool_acc=tools,
        on_text=None,
    )
    _ingest_openai_chunk(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "function": {"arguments": '{"q":'}}
                        ]
                    }
                }
            ]
        },
        content_parts=parts,
        tool_acc=tools,
        on_text=None,
    )
    parsed = _ingest_openai_chunk(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "function": {"arguments": '"hi"}'}}
                        ]
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
        content_parts=parts,
        tool_acc=tools,
        on_text=None,
    )

    assert parts == []
    assert parsed.finish_reason == "tool_calls"
    assert tools[0]["id"] == "call_1"
    assert tools[0]["function"]["name"] == "search"
    assert tools[0]["function"]["arguments"] == '{"q":"hi"}'


# --- Bedrock stream interruption -------------------------------------------
#
# A converse_stream response can die mid-iteration (urllib3 ProtocolError:
# "Response ended prematurely"), which used to kill the whole agent turn.


class _FakeStream:
    """Yields the given events, then raises -- or ends cleanly if exc is None."""

    def __init__(self, events: list[dict], exc: Exception | None) -> None:
        self._events = events
        self._exc = exc

    def __iter__(self):
        yield from self._events
        if self._exc is not None:
            raise self._exc


class _FakeClient:
    """Serves one scripted stream per converse_stream call."""

    def __init__(self, attempts: list[_FakeStream]) -> None:
        self._attempts = attempts
        self.calls = 0

    def converse_stream(self, **_kwargs):
        stream = self._attempts[min(self.calls, len(self._attempts) - 1)]
        self.calls += 1
        return {"stream": stream}


def _text_event(text: str) -> dict:
    return {"contentBlockDelta": {"delta": {"text": text}}}


def _bedrock_cfg(max_retries: int = 2):
    from app.llm.providers import ResolvedLLM

    return ResolvedLLM(
        source="env",
        kind="bedrock",
        model="anthropic.claude-test",
        label="test",
        aws_region="us-east-1",
        aws_access_key_id="AK",
        aws_secret_access_key="SK",
        temperature=0.2,
        max_tokens=1024,
        timeout_seconds=120.0,
        max_retries=max_retries,
    )


def _protocol_error() -> Exception:
    from urllib3.exceptions import ProtocolError

    return ProtocolError("Response ended prematurely")


def _patch_client(monkeypatch, client: _FakeClient) -> None:
    import app.llm.bedrock as bedrock

    async def fake_get_client(_cfg):
        return client

    monkeypatch.setattr(bedrock, "_get_client", fake_get_client)


def test_is_transient_matches_dropped_connections() -> None:
    from app.llm.bedrock import _is_transient

    assert _is_transient(_protocol_error())
    assert _is_transient(Exception("ThrottlingException: slow down"))
    # The class name carries the signal even when the message does not.
    assert _is_transient(type("ReadTimeoutError", (Exception,), {})("boom"))
    assert not _is_transient(ValueError("bad model id"))


def test_stream_break_keeps_partial_answer(monkeypatch) -> None:
    """Text already streamed is salvaged, not thrown away."""
    from app.llm.bedrock import bedrock_chat_complete_stream

    client = _FakeClient(
        [_FakeStream([_text_event("你好"), _text_event("世界")], _protocol_error())]
    )
    _patch_client(monkeypatch, client)
    seen: list[str] = []

    result = asyncio.run(
        bedrock_chat_complete_stream(
            _bedrock_cfg(), [{"role": "user", "content": "hi"}], on_text=seen.append
        )
    )

    assert result.content == "你好世界"
    assert result.finish_reason == "interrupted"
    # Salvage, not restart: the model is not asked to regenerate.
    assert client.calls == 1
    assert seen == ["你好", "世界"]


def test_stream_break_before_output_retries_cleanly(monkeypatch) -> None:
    """With nothing emitted yet a restart is safe and cannot duplicate text."""
    from app.llm.bedrock import bedrock_chat_complete_stream

    client = _FakeClient(
        [
            _FakeStream([], _protocol_error()),
            _FakeStream(
                [
                    _text_event("完整"),
                    {"messageStop": {"stopReason": "end_turn"}},
                ],
                None,
            ),
        ]
    )
    _patch_client(monkeypatch, client)
    seen: list[str] = []

    result = asyncio.run(
        bedrock_chat_complete_stream(
            _bedrock_cfg(), [{"role": "user", "content": "hi"}], on_text=seen.append
        )
    )

    assert client.calls == 2
    assert result.content == "完整"
    assert result.finish_reason == "stop"
    assert seen == ["完整"]


def test_stream_break_with_no_output_ends_as_llm_error(monkeypatch) -> None:
    """Retries exhausted with nothing to show -> a readable error, not urllib3."""
    from app.core.exceptions import LLMError
    from app.llm.bedrock import bedrock_chat_complete_stream

    client = _FakeClient([_FakeStream([], _protocol_error())])
    _patch_client(monkeypatch, client)

    raised: Exception | None = None
    try:
        asyncio.run(
            bedrock_chat_complete_stream(
                _bedrock_cfg(max_retries=0), [{"role": "user", "content": "hi"}]
            )
        )
    except Exception as exc:
        raised = exc

    assert isinstance(raised, LLMError)
    assert "Response ended prematurely" in str(raised)
    assert "代理" in (raised.details or {}).get("hint", "")


def test_dangling_tool_use_is_dropped_before_bedrock() -> None:
    # A salvaged/interrupted turn persists an assistant toolUse that never ran,
    # then compaction can drop a result while keeping its caller. Either way
    # Bedrock rejects the whole conversation unless we pair them up first.
    from app.llm.bedrock import drop_unpaired_tool_calls, to_converse_messages

    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "on it",
            "tool_calls": [
                {"id": "keep1", "function": {"name": "create_webpage", "arguments": "{}"}},
                {"id": "orphan", "function": {"name": "search", "arguments": "{}"}},
            ],
        },
        {"role": "tool", "tool_call_id": "keep1", "content": "ok"},
        # No result for "orphan" -> the stream broke before it executed.
        {"role": "user", "content": "continue"},
        # An orphan result whose caller was trimmed away entirely.
        {"role": "tool", "tool_call_id": "vanished", "content": "stale"},
    ]

    cleaned = drop_unpaired_tool_calls(messages)
    kept_calls = [
        c["id"]
        for m in cleaned
        if m.get("role") == "assistant"
        for c in (m.get("tool_calls") or [])
    ]
    assert kept_calls == ["keep1"]
    assert not any(
        m.get("role") == "tool" and m.get("tool_call_id") == "vanished" for m in cleaned
    )

    # And the converted Bedrock payload has exactly one toolUse and one toolResult.
    _system, converse = to_converse_messages(messages)
    use_ids = [
        b["toolUse"]["toolUseId"]
        for m in converse
        for b in m["content"]
        if "toolUse" in b
    ]
    result_ids = [
        b["toolResult"]["toolUseId"]
        for m in converse
        for b in m["content"]
        if "toolResult" in b
    ]
    assert use_ids == ["keep1"]
    assert result_ids == ["keep1"]
