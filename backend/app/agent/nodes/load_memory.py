"""Node: load conversation history from the database."""

from __future__ import annotations

from app.agent.state import AgentState
from app.core.logging import get_logger
from app.memory.conversation_memory import load_history
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def load_memory_node(state: AgentState, *, session: AsyncSession) -> AgentState:
    conversation_id = state["conversation_id"]
    history = await load_history(session, conversation_id)
    logger.debug("memory_loaded", conversation_id=conversation_id, turns=len(history))
    return {**state, "history": history}
