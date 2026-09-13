"""Per-model output token caps.

``max_tokens`` is the completion budget (tool JSON + prose). A rich webpage or
deck needs several thousand tokens; the old product default of 2048 truncated
those calls and the model then shrank the artifact until it fit.

Two callers with deliberately different rules about that old 2048:

* ``effective_max_tokens`` -- resolving a stored config. 2048 means "nobody
  chose this", so it yields the model cap.
* ``clamp_request_max_tokens`` -- a per-call override. 2048 there was typed on
  purpose for this one call, so it is honoured.

This leaves a known asymmetry: an install still carrying ``LLM_MAX_TOKENS=2048``
migrates up to the model cap (64k on Claude 4), while a fresh install sits at
the 8192 default from ``Settings``. That is intended -- 8192 is a deliberate
conservative floor, and per-provider settings are where you opt into more.
"""

from __future__ import annotations

# Historic .env / UI default. Treat as unset so existing installs pick up the
# model cap without a manual edit. Mirrored in frontend/src/lib/tokenLimits.ts.
_LEGACY_DEFAULT = 2048


def output_token_cap(kind: str, model: str) -> int:
    """Largest completion the provider is known to accept for this model."""
    name = (model or "").lower()
    family = (kind or "").lower()

    if family == "huggingface_image":
        return 1024

    if "claude" in name or "anthropic" in name or family == "bedrock":
        if any(key in name for key in ("opus-4", "sonnet-4", "haiku-4", "3-7", "3.7")):
            return 64_000
        if "opus" in name and "3-5" not in name and "3.5" not in name:
            return 4096
        return 8192

    if any(key in name for key in ("o1", "o3", "o4", "gpt-5")):
        return 100_000
    if "gpt-4.1" in name:
        return 32_768
    if "gpt-4o" in name:
        return 16_384
    if "gemini" in name or family == "gemini":
        return 65_536
    if "deepseek" in name:
        return 8192
    if "qwen" in name:
        return 8192
    return 8192


def effective_max_tokens(
    kind: str,
    model: str,
    requested: int | None,
) -> int:
    """Clamp a user/env value to the model cap; empty or legacy 2048 → cap."""
    cap = output_token_cap(kind, model)
    if requested is None:
        return cap
    try:
        value = int(requested)
    except (TypeError, ValueError):
        return cap
    if value <= 0 or value == _LEGACY_DEFAULT:
        return cap
    return max(64, min(value, cap))


def clamp_request_max_tokens(
    kind: str,
    model: str,
    requested: int | None,
    fallback: int,
) -> int:
    """Clamp a per-call override without treating 2048 as unset."""
    cap = output_token_cap(kind, model)
    value = fallback if requested is None else requested
    try:
        n = int(value)
    except (TypeError, ValueError):
        return cap
    if n <= 0:
        return cap
    return max(1, min(n, cap))
