"""Unit tests for conversation topic titles (no LLM)."""

from __future__ import annotations

from app.services.conversation_service import derive_title
from app.services.conversation_title import (
    clip_title,
    expand_clipped_title,
    is_filler_text,
    is_weak_title,
    should_llm_refresh,
    title_from_messages,
    title_from_user_texts,
)


def test_greeting_is_not_used_as_title() -> None:
    assert derive_title("hi") == "新会话"
    assert derive_title("你好") == "新会话"
    assert derive_title("你好呀") == "新会话"
    assert is_filler_text("hello")
    assert is_filler_text("你好呀")


def test_strips_leading_greeting_from_real_request() -> None:
    assert title_from_user_texts(["你好，帮我写周报"]) == "帮我写周报"


def test_image_request_becomes_topic() -> None:
    assert title_from_user_texts(["生成一张美女的图像"]) == "美女图像"


def test_identity_question_is_named() -> None:
    assert title_from_user_texts(["你是？能做什么"]) == "了解助手能力"


def test_skips_greeting_then_uses_later_turn() -> None:
    title = title_from_user_texts(["hi", "帮我练习英语口语"])
    assert title == "帮我练习英语口语"
    assert title != "hi"


def test_mode_fallback_when_only_greetings() -> None:
    assert (
        title_from_user_texts(["你好"], mode_key="companion", mode_name="陪伴")
        == "日常陪伴"
    )
    assert (
        title_from_user_texts(["hi"], mode_key="tutor", mode_name="英语陪练")
        == "学习交流"
    )


def test_first_line_title_is_weak() -> None:
    user = ["生成一张美女的图像"]
    opener = title_from_user_texts(user)
    assert is_weak_title(opener, user)
    assert is_weak_title("hi", user)
    assert is_weak_title("新会话", user)


def test_old_first_line_title_still_weak() -> None:
    user = ["帮我把这篇论文做成 demo 网页给领导汇报一下"]
    stored = "帮我把这篇论文做成 demo 网页给领导汇报一下"
    assert is_weak_title(stored, user)


def test_should_refresh_greeting_only_after_more_turns() -> None:
    assert should_llm_refresh("新会话", ["hi"]) is False
    assert should_llm_refresh("日常陪伴", ["你好", "最近有点累", "想聊聊工作"]) is True
    assert should_llm_refresh("美女图像", ["生成一张美女的图像"]) is True


def test_named_title_not_weak() -> None:
    texts = ["生成一张美女的图像", "换成桔梗的风格"]
    assert is_weak_title("犬夜叉插画实验", texts) is False
    assert should_llm_refresh("犬夜叉插画实验", texts) is True  # 2nd user turn


def test_clip_title_strips_label() -> None:
    assert clip_title("标题：美女人像生成。") == "美女人像生成"
    long_title = "这是一段非常非常非常非常长的中文标题需要被截断处理而且还会更长一些"
    assert "…" not in clip_title(long_title)
    assert len(clip_title(long_title)) <= 240


def test_expand_clipped_title_restores_user_line() -> None:
    user = ["AI代理框架DeepSeek Harness的功能介绍以及怎么在本地跑起来"]
    stored = "AI代理框架DeepSeek Harness的功…"
    expanded = expand_clipped_title(stored, user)
    assert "…" not in expanded
    assert expanded.startswith("AI代理框架DeepSeek Harness")
    assert "功能介绍" in expanded
    assert expand_clipped_title("犬夜叉插画实验", user) == "犬夜叉插画实验"


def test_title_from_messages_uses_user_role() -> None:
    title = title_from_messages(
        [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "Hello! How can I help?"},
            {"role": "user", "content": "帮我把这篇论文做成 demo 网页"},
        ]
    )
    assert "demo" in title or "论文" in title


if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print(_name, "ok")
    print("all ok")
