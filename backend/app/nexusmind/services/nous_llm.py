"""Bridge knowledge analysis / RAG assistant onto Nous's active LLM provider."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from app.llm.client import chat_complete
from app.llm.provider_store import resolve_llm
from app.nexusmind.services.llm_service import (
    ANALYSIS_SYSTEM_PROMPT,
    build_analysis_user_prompt,
    parse_json_object,
)


def nous_llm_ready() -> bool:
    try:
        return resolve_llm().configured
    except Exception:  # noqa: BLE001
        return False


async def nous_chat(
    system: str,
    user: str,
    *,
    on_text: Callable[[str], None] | None = None,
) -> tuple[str, str, int]:
    """Return (content, model_label, latency_ms) using the active Nous provider."""
    llm = resolve_llm()
    started = time.perf_counter()
    from app.llm.usage import PURPOSE_KNOWLEDGE, usage_scope

    with usage_scope(purpose=PURPOSE_KNOWLEDGE):
        result = await chat_complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            on_text=on_text,
        )
    latency = int((time.perf_counter() - started) * 1000)
    return result.content.strip(), f"{llm.label}/{llm.model}", latency


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            out.append(text[:64])
    return out


async def nous_analyze_document(*, title: str, content: str) -> tuple[dict[str, Any], str]:
    text, label, latency = await nous_chat(
        ANALYSIS_SYSTEM_PROMPT,
        build_analysis_user_prompt(title, content),
    )
    parsed = parse_json_object(text)
    keywords = _as_str_list(parsed.get("keywords"))
    search_keywords = _as_str_list(parsed.get("search_keywords")) or keywords
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
        "model_reply": text,
        "latency_ms": latency,
    }, label
