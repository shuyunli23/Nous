"""Output token caps for artifact-sized tool calls."""

from __future__ import annotations

from app.llm.token_limits import (
    clamp_request_max_tokens,
    effective_max_tokens,
    output_token_cap,
)


def test_claude_35_sonnet_cap_is_8192() -> None:
    model = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"
    assert output_token_cap("bedrock", model) == 8192
    assert effective_max_tokens("bedrock", model, None) == 8192
    assert effective_max_tokens("bedrock", model, 2048) == 8192
    assert effective_max_tokens("bedrock", model, 4096) == 4096
    assert effective_max_tokens("bedrock", model, 99_000) == 8192


def test_per_call_clamp_keeps_small_overrides() -> None:
    model = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"
    assert clamp_request_max_tokens("bedrock", model, 48, 8192) == 48
    assert clamp_request_max_tokens("bedrock", model, 99_000, 8192) == 8192
    assert clamp_request_max_tokens("bedrock", model, None, 4096) == 4096


def test_claude_4_and_gpt4o_caps() -> None:
    assert output_token_cap("bedrock", "anthropic.claude-sonnet-4-20250514") == 64_000
    assert output_token_cap("openai_compatible", "gpt-4o") == 16_384
    assert output_token_cap("openai_compatible", "deepseek-chat") == 8192
