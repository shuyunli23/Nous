"""Node: call the LLM and handle tool_calls loop."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.progress import emit, has_sink
from app.agent.state import AgentState
from app.agent.tools import openai_tool_schemas
from app.chat_modes.catalog import LIGHT_TOOLS, TOOL_FULL, TOOL_LIGHT, TOOL_NONE
from app.core.config import settings
from app.core.logging import get_logger
from app.llm.client import Message, chat_complete

logger = get_logger(__name__)


async def llm_call_node(state: AgentState, *, session: AsyncSession) -> AgentState:
    """Call the LLM with the current messages list and available tools."""
    messages: list[Message] = list(state.get("messages") or [])
    policy = state.get("tool_policy") or TOOL_FULL
    tools = None
    if policy == TOOL_FULL:
        tools = await openai_tool_schemas(
            session=session, user_id=state.get("user_id")
        )
    elif policy == TOOL_LIGHT:
        tools = await openai_tool_schemas(
            session=session,
            user_id=state.get("user_id"),
            allowed=LIGHT_TOOLS,
            include_packs=False,
        )

    on_text = None
    if has_sink():

        def on_text(text: str) -> None:
            emit({"type": "token", "text": text})

    result = await chat_complete(messages, tools=tools, on_text=on_text)
    if result.tool_calls:
        emit({"type": "token_clear"})

    logger.debug(
        "llm_call",
        conversation_id=state.get("conversation_id"),
        finish_reason=result.finish_reason,
        tokens=result.usage.total_tokens,
        tool_calls=len(result.tool_calls),
    )

    updated: AgentState = {
        **state,
        "response": result.content,
        "tool_calls": result.tool_calls,
        "finish_reason": result.finish_reason,
        "usage": result.usage.model_dump(),
        "tool_loop_count": (state.get("tool_loop_count") or 0),
    }

    # Append assistant message so subsequent loop iterations keep full context.
    assistant_msg: Message = {"role": "assistant", "content": result.content}
    if result.tool_calls:
        assistant_msg["tool_calls"] = result.tool_calls
    updated["messages"] = messages + [assistant_msg]

    return updated


def should_call_tools(state: AgentState) -> str:
    """Edge condition: keep looping if tools were requested and limit not hit."""
    if (state.get("tool_policy") or TOOL_FULL) == TOOL_NONE:
        return "verify"
    tool_calls = state.get("tool_calls") or []
    loop_count = state.get("tool_loop_count") or 0
    if tool_calls and loop_count < settings.agent_max_tool_loops:
        return "tools"
    return "verify"
