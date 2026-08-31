"""Assemble OpenAI SSE deltas into a completion, including tool calls."""

from __future__ import annotations

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
