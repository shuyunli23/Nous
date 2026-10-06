"""Node: save the assistant turn and record which skills were used."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.execution_trace import answer_step, interrupt_step
from app.agent.state import AgentState
from app.agent.tools.export_urls import (
    rewrite_invented_export_links,
    strip_unbacked_export_links,
)
from app.core.logging import get_logger
from app.database.models import SkillUsage
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.skill_repo import SkillRepository
from app.services.conversation_service import ConversationService, _refine_title_job
from app.services.conversation_title import schedule_title_job

logger = get_logger(__name__)

FAILED_KEEP_NOTE = (
    "问题、已完成的步骤和工作区文件都已保留。"
    "直接在本对话继续即可，不必从头再做。"
)


def failed_turn_content(state: AgentState, reason: str) -> str:
    """User-visible reply for a turn that died before persist."""
    parts: list[str] = []
    partial = str(state.get("response") or "").strip()
    if partial:
        parts.append(partial)
    text = (reason or "").strip()
    if text:
        parts.append(text)
    parts.append(FAILED_KEEP_NOTE)
    return "\n\n".join(parts)


def finalize_failed_trace(
    trace: list[dict[str, Any]],
    reason: str,
) -> list[dict[str, Any]]:
    """Keep the live timeline, mark leftover running steps, append an interrupt."""
    out: list[dict[str, Any]] = []
    for step in trace:
        item = dict(step)
        if item.get("status") == "running":
            item["status"] = "error"
        out.append(item)
    detail = (reason or "turn interrupted").strip() or "turn interrupted"
    if not any(step.get("title") == "本轮中断" for step in out):
        out.append(interrupt_step(detail))
    return out


async def persist_failed_turn(
    state: AgentState,
    *,
    session: AsyncSession,
    reason: str,
) -> AgentState:
    """Commit the user question, partial trace, and todos after a crash.

    Uses a fresh transaction so a failed graph hop cannot roll this write back.
    """
    if state.get("assistant_message_id"):
        return state
    if not state.get("conversation_id") or not str(state.get("query") or "").strip():
        return state
    try:
        await session.rollback()
    except Exception:
        logger.exception("persist_failed_turn_rollback")
        return state

    trace = finalize_failed_trace(list(state.get("execution_trace") or []), reason)
    content = failed_turn_content(state, reason)
    try:
        return await _write_turn(
            {**state, "error": reason, "execution_trace": trace},
            session=session,
            assistant_content=content,
            trace=trace,
            record_skill_usage=False,
        )
    except Exception:
        logger.exception("persist_failed_turn_failed")
        return state


async def persist_node(state: AgentState, *, session: AsyncSession) -> AgentState:
    """Write the user message, assistant reply, and skill usage ledger rows."""
    trace = list(state.get("execution_trace") or [])
    has_work = any(
        step.get("kind") in {"tool", "skill_retrieve", "plan", "verify", "think", "guard"}
        for step in trace
    )
    if has_work:
        if not any(step.get("kind") == "answer" for step in trace):
            used_tools = any(step.get("kind") == "tool" for step in trace)
            trace.append(answer_step(used_tools=used_tools))
    else:
        # Pure Q&A with no tools/skills/plan — omit empty timeline noise.
        trace = []

    assistant_content = strip_unbacked_export_links(
        rewrite_invented_export_links(state.get("response") or "", trace),
        trace,
    )
    return await _write_turn(
        state,
        session=session,
        assistant_content=assistant_content,
        trace=trace,
        record_skill_usage=True,
    )


async def _write_turn(
    state: AgentState,
    *,
    session: AsyncSession,
    assistant_content: str,
    trace: list[dict[str, Any]],
    record_skill_usage: bool,
) -> AgentState:
    conversation_id = state["conversation_id"]
    repo = ConversationRepository(session)

    user_msg = await repo.add_message(
        conversation_id=conversation_id,
        role="user",
        content=state["query"],
    )

    usage = state.get("usage") or {}
    used_skill_ids = state.get("used_skill_ids") or []

    assistant_msg = await repo.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        token_usage=usage or None,
        used_skill_ids=used_skill_ids or None,
        execution_trace=trace or None,
    )

    if record_skill_usage:
        similarities = state.get("skill_similarities") or {}
        skill_repo = SkillRepository(session)
        for skill_id in used_skill_ids:
            session.add(
                SkillUsage(
                    skill_id=skill_id,
                    conversation_id=conversation_id,
                    message_id=assistant_msg.id,
                    similarity=similarities.get(skill_id),
                )
            )
            await skill_repo.increment_usage(skill_id)

    conversation = await repo.get(conversation_id)
    needs_llm = False
    if conversation:
        if "todos" in state:
            conversation.todos = list(state.get("todos") or []) or None
        svc = ConversationService(session)
        needs_llm = await svc.ensure_title(
            conversation, state.get("title_source") or state["query"]
        )
        await repo.touch(conversation)

    await session.commit()
    if needs_llm:
        schedule_title_job(conversation_id, _refine_title_job, force=True)

    logger.debug(
        "turn_persisted",
        conversation_id=conversation_id,
        user_msg_id=user_msg.id,
        assistant_msg_id=assistant_msg.id,
        skills_used=len(used_skill_ids) if record_skill_usage else 0,
        failed=not record_skill_usage,
    )

    return {
        **state,
        "assistant_message_id": assistant_msg.id,
        "execution_trace": trace,
        "response": assistant_content,
    }
