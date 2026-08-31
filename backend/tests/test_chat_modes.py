"""Chat mode prompts and tool-policy routing (no LLM)."""

from __future__ import annotations

from app.agent.nodes.llm_call import should_call_tools
from app.chat_modes.catalog import (
    COMPANION,
    KNOWLEDGE_PLACEHOLDER,
    PERSONA_PLACEHOLDER,
    TUTOR,
    WORKBENCH,
    resolve_system_prompt,
)


def test_workbench_prompt_stays_on_chat_system() -> None:
    prompt = resolve_system_prompt(key=WORKBENCH)
    assert "个人智能 Agent（工作台）" in prompt
    assert "create_webpage" in prompt
    assert PERSONA_PLACEHOLDER not in prompt
    assert KNOWLEDGE_PLACEHOLDER not in prompt


def test_tutor_prompt_is_separate() -> None:
    prompt = resolve_system_prompt(key=TUTOR)
    assert "学习向导" in prompt
    assert "不要主动去做网页 Demo" in prompt
    assert "create_webpage" not in prompt
    assert KNOWLEDGE_PLACEHOLDER not in prompt


def test_companion_prompt_injects_persona_placeholder() -> None:
    prompt = resolve_system_prompt(key=COMPANION, use_long_term_memory=True)
    assert "愿意陪着说话" in prompt
    assert PERSONA_PLACEHOLDER in prompt
    assert KNOWLEDGE_PLACEHOLDER not in prompt
    assert "不要去做网页 Demo" in prompt
    assert "get_weather" in prompt


def test_custom_prompt_without_memory() -> None:
    prompt = resolve_system_prompt(
        key="c_abc123",
        custom_prompt="你是一只说话简洁的猫。",
        use_long_term_memory=False,
    )
    assert prompt.startswith("你是一只说话简洁的猫。")
    assert PERSONA_PLACEHOLDER not in prompt
    assert KNOWLEDGE_PLACEHOLDER not in prompt


def test_custom_prompt_with_persona_appends_placeholder() -> None:
    prompt = resolve_system_prompt(
        key="c_abc123",
        custom_prompt="你是一只说话简洁的猫。",
        use_long_term_memory=True,
    )
    assert "你是一只说话简洁的猫。" in prompt
    assert PERSONA_PLACEHOLDER in prompt
    assert KNOWLEDGE_PLACEHOLDER not in prompt


def test_none_policy_skips_tools() -> None:
    assert should_call_tools({"tool_policy": "none", "tool_calls": [{"name": "x"}]}) == "verify"
    assert should_call_tools({"tool_policy": "full", "tool_calls": [{"name": "x"}]}) == "tools"
    assert should_call_tools({"tool_policy": "light", "tool_calls": [{"name": "x"}]}) == "tools"


def test_light_tools_include_weather_and_search() -> None:
    from app.chat_modes.catalog import LIGHT_TOOLS, builtin_specs

    assert "get_weather" in LIGHT_TOOLS
    assert "web_search" in LIGHT_TOOLS
    policies = {spec["key"]: spec["tool_policy"] for spec in builtin_specs()}
    assert policies["tutor"] == "light"
    assert policies["companion"] == "light"
    assert policies["workbench"] == "full"
