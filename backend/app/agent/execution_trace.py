"""Compact execution steps shown in the chat UI (not fed back to the LLM)."""

from __future__ import annotations

import json
from typing import Any


def _truncate(value: str, limit: int = 160) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {"_raw": _truncate(raw, 120)}
    return {}


def _arg_preview(name: str, args: dict[str, Any]) -> str:
    preferred = (
        "query",
        "url",
        "city",
        "expression",
        "prompt",
        "title",
        "topic",
        "q",
    )
    for key in preferred:
        if key in args and args[key] not in (None, ""):
            return f"{key}={_truncate(str(args[key]), 80)}"
    if not args:
        return ""
    first_key = next(iter(args))
    return f"{first_key}={_truncate(str(args[first_key]), 80)}"


def _result_summary(name: str, result: dict[str, Any]) -> tuple[str, str]:
    """Return (status, detail). status is ok | error | info."""
    if result.get("ok") is False or result.get("error"):
        err = result.get("error") or result.get("message") or "failed"
        return "error", _truncate(str(err), 180)

    if name == "web_search":
        count = result.get("count")
        if count is None:
            count = len(result.get("results") or [])
        provider = result.get("provider") or ""
        titles = [
            str(item.get("title") or "")
            for item in (result.get("results") or [])[:2]
            if item.get("title")
        ]
        detail = f"{count} 条结果"
        if provider:
            detail += f" · {provider}"
        if titles:
            detail += " · " + " / ".join(_truncate(t, 40) for t in titles)
        return "ok", detail

    if name == "fetch_url":
        title = result.get("title") or result.get("url") or ""
        chars = result.get("chars") or len(str(result.get("text") or result.get("content") or ""))
        return "ok", _truncate(f"{title} · {chars} 字符", 160)

    if name in {
        "generate_image",
        "crop_image",
        "create_presentation",
        "create_pdf",
        "create_webpage",
    } or name.startswith("pack__"):
        url = result.get("download_url") or result.get("url") or ""
        inspect = result.get("inspect") if isinstance(result.get("inspect"), dict) else {}
        extra = ""
        if inspect:
            n = inspect.get("image_count")
            pages = inspect.get("section_count") or inspect.get("slide_count") or inspect.get("page_count")
            bits = []
            if pages is not None:
                bits.append(f"{pages}页")
            if n is not None:
                bits.append(f"{n}图")
            extra = " · ".join(bits)
        if url:
            detail = f"产出 {url}"
            if extra:
                detail += f" · {extra}"
            return "ok", detail
        return "ok", _truncate(str(result.get("message") or extra or "完成"), 120)

    if name == "get_weather":
        city = result.get("city") or result.get("location") or ""
        summary = result.get("summary") or result.get("description") or ""
        return "ok", _truncate(f"{city} {summary}".strip(), 140)

    if name == "calculator":
        return "ok", _truncate(str(result.get("result") or result.get("value") or "完成"), 80)

    if name == "current_datetime":
        return "ok", _truncate(str(result.get("iso") or result.get("datetime") or "完成"), 80)

    # Generic: prefer short human fields
    for key in ("summary", "message", "answer", "result"):
        if result.get(key):
            return "ok", _truncate(str(result[key]), 160)
    return "ok", "完成"


def skill_retrieve_step(skills: list[dict[str, Any]]) -> dict[str, Any]:
    if not skills:
        return {
            "kind": "skill_retrieve",
            "title": "检索 Skill",
            "detail": "未命中相关 Skill",
            "status": "info",
        }
    names = [str(s.get("name") or "未命名") for s in skills[:4]]
    more = len(skills) - len(names)
    detail = "、".join(names)
    if more > 0:
        detail += f" 等 {len(skills)} 个"
    return {
        "kind": "skill_retrieve",
        "title": "检索 Skill",
        "detail": detail,
        "status": "ok",
        "count": len(skills),
    }


def tool_step(
    *,
    name: str,
    call_id: str,
    raw_args: Any,
    result: dict[str, Any],
) -> dict[str, Any]:
    args = _parse_args(raw_args)
    status, detail = _result_summary(name, result if isinstance(result, dict) else {})
    preview = _arg_preview(name, args)
    return {
        "kind": "tool",
        "title": name,
        "detail": " · ".join(p for p in (preview, detail) if p),
        "status": status,
        "tool": name,
        "call_id": call_id or None,
        "args": {k: _truncate(str(v), 120) for k, v in list(args.items())[:6]},
    }


def plan_step(plan: str, required_tools: list[str]) -> dict[str, Any]:
    return {
        "kind": "plan",
        "title": "计划",
        "detail": _truncate(plan, 180),
        "status": "info",
        "required_tools": required_tools,
    }


def verify_step(*, ok: bool, detail: str) -> dict[str, Any]:
    return {
        "kind": "verify",
        "title": "核对" if ok else "核对未通过",
        "detail": _truncate(detail, 180),
        "status": "ok" if ok else "error",
    }


def think_step(*, elapsed_ms: int, detail: str | None = None) -> dict[str, Any]:
    step: dict[str, Any] = {
        "kind": "think",
        "title": "模型推理",
        "status": "ok",
        "elapsed_ms": elapsed_ms,
    }
    if detail:
        # Keep enough text to reread the chain of thought; still cap the JSON blob.
        step["detail"] = _truncate(detail.strip(), 12000)
    return step


def answer_step() -> dict[str, Any]:
    return {
        "kind": "answer",
        "title": "生成回答",
        "detail": "基于工具结果整理回复",
        "status": "ok",
    }
