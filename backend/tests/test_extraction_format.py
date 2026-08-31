"""Skill extraction prompt compaction (no LLM)."""

from __future__ import annotations

from app.llm.client import _loads_json_object, _strip_json_fence
from app.llm.prompts.extraction import compact_extraction_text, format_conversation


def test_compact_replaces_svg_and_caps_length() -> None:
    svg = "<svg xmlns='http://www.w3.org/2000/svg'><rect width='10' height='10'/></svg>"
    body = "先画架构图：\n" + svg + "\n再调配色。"
    out = compact_extraction_text(body, limit=200)
    assert "<svg" not in out.lower()
    assert "SVG 图已省略" in out
    assert "再调配色" in out


def test_format_conversation_strips_svg_from_assistant() -> None:
    huge = "<svg viewBox='0 0 800 600'>" + ("<g></g>" * 2000) + "</svg>"
    text = format_conversation(
        [
            {"role": "user", "content": "画一张 Docker 网络图"},
            {"role": "assistant", "content": huge},
        ]
    )
    assert "<svg" not in text.lower()
    assert "Docker" in text
    assert len(text) < 8_000


def test_json_object_from_fence_and_chatter() -> None:
    assert _strip_json_fence('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert _loads_json_object('Sure.\n{"reusable": true, "confidence": 0.9, "reason": "x"}')[
        "reusable"
    ] is True


if __name__ == "__main__":
    test_compact_replaces_svg_and_caps_length()
    test_format_conversation_strips_svg_from_assistant()
    test_json_object_from_fence_and_chatter()
    print("ok")
