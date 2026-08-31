"""Node: retrieve relevant skills and expose them for prompt injection."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.execution_trace import skill_retrieve_step
from app.agent.skill_gate import should_retrieve_skills
from app.agent.state import AgentState
from app.chat_modes.catalog import TOOL_FULL
from app.core.logging import get_logger
from app.skill.retriever import SkillRetriever

logger = get_logger(__name__)


async def retrieve_skills_node(
    state: AgentState, *, session: AsyncSession
) -> AgentState:
    """Hybrid-search the user's active skills for the current query.

    Retrieval failures degrade to "no skills" rather than failing the turn: the
    agent must still answer even when the vector store or embedding provider is
    unavailable.
    """
    if (state.get("tool_policy") or TOOL_FULL) != TOOL_FULL:
        return {
            **state,
            "retrieved_skills": [],
            "used_skill_ids": [],
            "skill_similarities": {},
        }
    query = state["query"]
    if not should_retrieve_skills(query):
        logger.info(
            "skills_skipped",
            conversation_id=state.get("conversation_id"),
            reason="not_a_task",
        )
        return {
            **state,
            "retrieved_skills": [],
            "used_skill_ids": [],
            "skill_similarities": {},
        }
    user_id = state["user_id"]

    try:
        retriever = SkillRetriever(session)
        retrieved = await retriever.retrieve(user_id=user_id, query=query)
    except Exception as exc:
        logger.warning("skill_retrieval_failed", error=str(exc))
        retrieved = []

    prompt_skills = [item.to_prompt_dict() for item in retrieved]
    used_skill_ids = [item.skill.id for item in retrieved]
    similarities = {item.skill.id: item.score for item in retrieved}

    if retrieved:
        logger.info(
            "skills_injected",
            conversation_id=state.get("conversation_id"),
            skills=[(item.skill.name, round(item.score, 3)) for item in retrieved],
        )

    trace = list(state.get("execution_trace") or [])
    trace.append(skill_retrieve_step(prompt_skills))

    return {
        **state,
        "retrieved_skills": prompt_skills,
        "used_skill_ids": used_skill_ids,
        "skill_similarities": similarities,
        "execution_trace": trace,
    }
