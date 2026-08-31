"""AI 知识助手：检索增强生成（RAG）。"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.nexusmind.config import settings
from app.nexusmind.services import embedding_service, model_config_service, search_service
from app.nexusmind.services.llm_service import ModelEndpoint, chat_completion

logger = logging.getLogger(__name__)

ASSISTANT_SYSTEM = """你是 Nous 个人知识库助手。
根据提供的「参考笔记」回答用户问题。
规则：
1. 优先依据参考笔记，不要编造库中不存在的事实。
2. 若参考不足，明确说明，并给出可继续检索的关键词建议。
3. 回答使用简洁中文，可分点。
4. 在相关处用 [1]、[2] 标注引用编号（对应参考笔记序号）。
5. 不要输出与问题无关的长篇套话。"""


@dataclass
class Citation:
    id: str
    title: str
    summary: str | None
    score: float
    match_fields: list[str] = field(default_factory=list)


@dataclass
class AssistantReply:
    answer: str
    citations: list[Citation]
    source: str  # ai | local
    model: str | None = None
    latency_ms: int | None = None
    execution_trace: list[dict[str, Any]] = field(default_factory=list)


def _merge_retrieval(db: Session, question: str, *, k: int = 6) -> list[Citation]:
    """向量 + hybrid 混合召回，按分数去重。"""
    by_id: dict[str, Citation] = {}

    # hybrid 关键词/全文
    try:
        hits, _, _ = search_service.search_knowledge(
            db, q=question, mode="hybrid", page=1, page_size=k
        )
        for h in hits:
            item = h.knowledge
            by_id[item.id] = Citation(
                id=item.id,
                title=item.title,
                summary=item.summary,
                score=float(h.score),
                match_fields=sorted(h.match_fields),
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("hybrid retrieval skipped: %s", exc)

    # vector
    try:
        vhits = embedding_service.top_k_for_assistant(db, question, k=k)
        for h in vhits:
            item = h.knowledge
            prev = by_id.get(item.id)
            score = float(h.score)
            if prev is None or score > prev.score:
                fields = set(prev.match_fields) if prev else set()
                fields.add("vector")
                by_id[item.id] = Citation(
                    id=item.id,
                    title=item.title,
                    summary=item.summary or h.snippet,
                    score=max(score, prev.score if prev else 0),
                    match_fields=sorted(fields),
                )
            elif prev is not None and "vector" not in prev.match_fields:
                prev.match_fields = sorted({*prev.match_fields, "vector"})
    except Exception as exc:  # noqa: BLE001
        logger.debug("vector retrieval skipped: %s", exc)

    ranked = sorted(by_id.values(), key=lambda c: -c.score)[:k]
    return ranked


def _build_context(citations: list[Citation], db: Session) -> str:
    from app.nexusmind.services import knowledge_service

    blocks: list[str] = []
    for i, c in enumerate(citations, start=1):
        try:
            item = knowledge_service.get_knowledge(db, c.id)
            body = (item.plain_text or item.markdown_content or "")[:1800]
        except Exception:  # noqa: BLE001
            body = c.summary or ""
        blocks.append(
            f"[{i}] 标题：{c.title}\n"
            f"摘要：{c.summary or '（无）'}\n"
            f"正文片段：\n{body}"
        )
    return "\n\n---\n\n".join(blocks)


def _local_answer(question: str, citations: list[Citation]) -> str:
    if not citations:
        return (
            f"知识库里暂时没有找到与「{question}」高度相关的笔记。\n\n"
            "建议：先对笔记执行 AI 分析以生成关键词，或换更短的核心词再试。"
        )
    lines = [
        f"根据知识库检索，找到 {len(citations)} 条可能相关的笔记（本地汇总，未调用大模型）：",
        "",
    ]
    for i, c in enumerate(citations, start=1):
        summary = c.summary or "（无摘要）"
        lines.append(f"[{i}] **{c.title}**")
        lines.append(f"    {summary}")
        if c.match_fields:
            lines.append(f"    命中：{', '.join(c.match_fields)} · 相关度 {c.score}")
        lines.append("")
    lines.append("可在「模型」页配置 LLM 后获得自然语言综合回答。")
    return "\n".join(lines)


def _format_history(history: list[dict[str, str]] | None) -> str:
    if not history:
        return ""
    parts: list[str] = []
    for msg in history[-6:]:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        label = "用户" if role == "user" else "助手"
        parts.append(f"{label}：{content}")
    if not parts:
        return ""
    return "最近对话：\n" + "\n".join(parts) + "\n\n"


EmitFn = Callable[[dict[str, Any]], None]


def _emit(emit: EmitFn | None, event: dict[str, Any]) -> None:
    if emit is not None:
        emit(event)


def _retrieve_step(citations: list[Citation], elapsed_ms: int) -> dict[str, Any]:
    if not citations:
        return {
            "kind": "retrieve",
            "title": "检索笔记",
            "detail": "未命中相关笔记",
            "status": "info",
            "count": 0,
            "elapsed_ms": elapsed_ms,
        }
    names = [c.title for c in citations[:4]]
    detail = "、".join(names)
    if len(citations) > 4:
        detail += f" 等 {len(citations)} 篇"
    return {
        "kind": "retrieve",
        "title": "检索笔记",
        "detail": detail,
        "status": "ok",
        "count": len(citations),
        "elapsed_ms": elapsed_ms,
    }


def _think_step(answer: str, elapsed_ms: int) -> dict[str, Any]:
    return {
        "kind": "think",
        "title": "模型推理",
        "detail": (answer or "").strip()[:12000],
        "status": "ok",
        "elapsed_ms": elapsed_ms,
    }


def _reply(
    *,
    answer: str,
    citations: list[Citation],
    source: str,
    model: str | None,
    latency_ms: int | None,
    retrieve_step: dict[str, Any],
    think_step: dict[str, Any] | None = None,
) -> AssistantReply:
    trace = [retrieve_step]
    if think_step is not None:
        trace.append(think_step)
    return AssistantReply(
        answer=answer,
        citations=citations,
        source=source,
        model=model,
        latency_ms=latency_ms,
        execution_trace=trace,
    )


async def ask(
    db: Session,
    *,
    message: str,
    history: list[dict[str, str]] | None = None,
    model_id: str | None = None,
    top_k: int | None = None,
    emit: EmitFn | None = None,
) -> AssistantReply:
    question = (message or "").strip()
    if not question:
        from app.nexusmind.utils.errors import ValidationError

        raise ValidationError("请输入问题")
    if len(question) > 2000:
        from app.nexusmind.utils.errors import ValidationError

        raise ValidationError("问题过长")

    k = top_k or settings.ASSISTANT_TOP_K
    _emit(
        emit,
        {
            "type": "step_start",
            "node": "retrieve",
            "kind": "retrieve",
            "title": "检索笔记",
            "status": "running",
        },
    )
    retrieve_started = time.perf_counter()
    citations = _merge_retrieval(db, question, k=k)
    retrieve_ms = int((time.perf_counter() - retrieve_started) * 1000)
    retrieve_step = _retrieve_step(citations, retrieve_ms)
    _emit(
        emit,
        {
            "type": "step_end",
            "node": "retrieve",
            "kind": "retrieve",
            "elapsed_ms": retrieve_ms,
            "status": retrieve_step["status"],
            "execution_trace": [retrieve_step],
        },
    )

    context = _build_context(citations, db) if citations else "（暂无参考笔记）"
    hist = _format_history(history)

    model = None
    if model_id:
        model = model_config_service.get_model(db, model_id)
    else:
        model = model_config_service.get_default_model(db)

    user_prompt = (
        f"{hist}"
        f"参考笔记：\n{context}\n\n"
        f"用户问题：{question}\n\n"
        "请基于参考笔记作答，并使用 [编号] 引用。"
    )

    on_text = None
    if emit is not None:

        def on_text(text: str) -> None:
            _emit(emit, {"type": "token", "text": text})

    if model is not None and model.is_active:
        _emit(
            emit,
            {
                "type": "step_start",
                "node": "llm_call",
                "kind": "think",
                "title": "模型推理",
                "status": "running",
            },
        )
        think_started = time.perf_counter()
        try:
            endpoint = ModelEndpoint.from_config(model)
            endpoint.temperature = min(0.5, max(0.1, float(endpoint.temperature)))
            result = await chat_completion(
                endpoint,
                system=ASSISTANT_SYSTEM,
                user=user_prompt,
                on_text=on_text,
            )
            answer = result.content.strip()
            answer = re.sub(r"^```(?:markdown)?\n|\n```$", "", answer).strip()
            think_ms = int((time.perf_counter() - think_started) * 1000)
            think = _think_step(answer, think_ms)
            _emit(
                emit,
                {
                    "type": "step_end",
                    "node": "llm_call",
                    "kind": "think",
                    "elapsed_ms": think_ms,
                    "status": "ok",
                    "execution_trace": [retrieve_step, think],
                },
            )
            return _reply(
                answer=answer,
                citations=citations,
                source="ai",
                model=f"{model.provider}/{model.model_name}",
                latency_ms=result.latency_ms,
                retrieve_step=retrieve_step,
                think_step=think,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("assistant LLM failed: %s", exc)
            think_ms = int((time.perf_counter() - think_started) * 1000)
            answer = _local_answer(question, citations) + f"\n\n（模型调用失败，已降级本地汇总：{exc}）"
            _emit(
                emit,
                {
                    "type": "step_end",
                    "node": "llm_call",
                    "kind": "think",
                    "elapsed_ms": think_ms,
                    "status": "error",
                    "execution_trace": [retrieve_step],
                },
            )
            return _reply(
                answer=answer,
                citations=citations,
                source="local",
                model=None,
                latency_ms=None,
                retrieve_step=retrieve_step,
            )

    from app.nexusmind.services.nous_llm import nous_chat, nous_llm_ready

    if nous_llm_ready():
        _emit(
            emit,
            {
                "type": "step_start",
                "node": "llm_call",
                "kind": "think",
                "title": "模型推理",
                "status": "running",
            },
        )
        think_started = time.perf_counter()
        try:
            content, label, latency = await nous_chat(
                ASSISTANT_SYSTEM, user_prompt, on_text=on_text
            )
            answer = re.sub(r"^```(?:markdown)?\n|\n```$", "", content).strip()
            think_ms = int((time.perf_counter() - think_started) * 1000)
            think = _think_step(answer, think_ms)
            _emit(
                emit,
                {
                    "type": "step_end",
                    "node": "llm_call",
                    "kind": "think",
                    "elapsed_ms": think_ms,
                    "status": "ok",
                    "execution_trace": [retrieve_step, think],
                },
            )
            return _reply(
                answer=answer,
                citations=citations,
                source="ai",
                model=label,
                latency_ms=latency,
                retrieve_step=retrieve_step,
                think_step=think,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("assistant Nous LLM failed: %s", exc)
            think_ms = int((time.perf_counter() - think_started) * 1000)
            answer = _local_answer(question, citations) + f"\n\n（模型调用失败，已降级本地汇总：{exc}）"
            _emit(
                emit,
                {
                    "type": "step_end",
                    "node": "llm_call",
                    "kind": "think",
                    "elapsed_ms": think_ms,
                    "status": "error",
                    "execution_trace": [retrieve_step],
                },
            )
            return _reply(
                answer=answer,
                citations=citations,
                source="local",
                model=None,
                latency_ms=None,
                retrieve_step=retrieve_step,
            )

    return _reply(
        answer=_local_answer(question, citations),
        citations=citations,
        source="local",
        model=None,
        latency_ms=None,
        retrieve_step=retrieve_step,
    )
