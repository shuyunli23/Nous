"""Node: name the goal and required tools before the model acts."""

from __future__ import annotations

from app.agent.execution_trace import plan_step
from app.agent.goal import (
    describe_plan,
    infer_required_tools,
    resolve_goal_text,
    wants_document_photo,
)
from app.agent.skill_gate import is_retry_or_continue, is_social_turn
from app.agent.state import AgentState
from app.agent.todo import wants_structured_plan
from app.chat_modes.catalog import TOOL_FULL
from app.core.logging import get_logger

logger = get_logger(__name__)


async def plan_node(state: AgentState) -> AgentState:
    query = state.get("query") or ""
    goal = resolve_goal_text(
        query,
        history=state.get("history") or [],
        title_source=state.get("title_source"),
    )
    # A greeting is not a new step of the previous checklist. Leave that list
    # on the conversation, but do not show it or force tools for this turn.
    if (state.get("tool_policy") or TOOL_FULL) != TOOL_FULL or is_social_turn(query):
        return {
            **state,
            "goal_text": goal,
            "required_tools": [],
            "must_embed_image": False,
            "needs_retry": False,
        }
    continuing = is_retry_or_continue(query)
    required = infer_required_tools(goal)
    todos = list(state.get("todos") or [])
    if not required and continuing:
        todo_text = " ".join(
            str(item.get("content") or "")
            for item in todos
            if item.get("status") != "completed"
        )
        required = infer_required_tools(todo_text)
    must_embed = wants_document_photo(goal)
    trace = list(state.get("execution_trace") or [])
    structured = wants_structured_plan(goal, required)
    if required or structured or (continuing and todos):
        if required:
            plan = describe_plan(goal, required)
            logger.info(
                "turn_plan",
                conversation_id=state.get("conversation_id"),
                required_tools=required,
                must_embed_image=must_embed,
            )
        elif structured:
            plan = f"{describe_plan(goal, required)} · 先用 todo_write 列出步骤"
        else:
            plan = describe_plan(goal, [])
        trace.append(
            plan_step(plan, required, todos=todos if continuing else None)
        )
    return {
        **state,
        "goal_text": goal,
        "required_tools": required,
        "must_embed_image": must_embed,
        "execution_trace": trace,
        "needs_retry": False,
    }
