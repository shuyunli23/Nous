"""Node: save the assistant turn and record which skills were used."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.execution_trace import answer_step
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


async def persist_node(state: AgentState, *, session: AsyncSession) -> AgentState:
    """Write the user message, assistant reply, and skill usage ledger rows."""
    conversation_id = state["conversation_id"]
    repo = ConversationRepository(session)

    user_msg = await repo.add_message(
        conversation_id=conversation_id,
        role="user",
        content=state["query"],
    )

    usage = state.get("usage") or {}
    used_skill_ids = state.get("used_skill_ids") or []
    trace = list(state.get("execution_trace") or [])
    has_work = any(
        step.get("kind") in {"tool", "skill_retrieve", "plan", "verify", "think"}
        for step in trace
    )
    if has_work:
        if not any(step.get("kind") == "answer" for step in trace):
            trace.append(answer_step())
    else:
        # Pure Q&A with no tools/skills/plan — omit empty timeline noise.
        trace = []

    assistant_content = strip_unbacked_export_links(
        rewrite_invented_export_links(state.get("response") or "", trace),
        trace,
    )

    assistant_msg = await repo.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        token_usage=usage or None,
        used_skill_ids=used_skill_ids or None,
        execution_trace=trace or None,
    )

    # Ledger: one row per injected skill, so feedback can be attributed later.
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
        # Retrieval counts as a use; success/failure arrives via the feedback API.
        await skill_repo.increment_usage(skill_id)

    conversation = await repo.get(conversation_id)
    needs_llm = False
    if conversation:
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
        skills_used=len(used_skill_ids),
    )

    return {
        **state,
        "assistant_message_id": assistant_msg.id,
        "execution_trace": trace,
        "response": assistant_content,
    }
