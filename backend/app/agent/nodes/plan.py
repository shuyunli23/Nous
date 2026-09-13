"""Node: name the goal and required tools before the model acts."""

from __future__ import annotations

from app.agent.execution_trace import plan_step
from app.agent.goal import (
    describe_plan,
    infer_required_tools,
    resolve_goal_text,
    wants_document_photo,
)
from app.agent.state import AgentState
from app.agent.todo import wants_structured_plan
from app.chat_modes.catalog import TOOL_FULL
from app.core.logging import get_logger

logger = get_logger(__name__)


async def plan_node(state: AgentState) -> AgentState:
    goal = resolve_goal_text(
        state.get("query") or "",
        history=state.get("history") or [],
        title_source=state.get("title_source"),
    )
    if (state.get("tool_policy") or TOOL_FULL) != TOOL_FULL:
        return {
            **state,
            "goal_text": goal,
            "required_tools": [],
            "must_embed_image": False,
            "needs_retry": False,
        }
    required = infer_required_tools(goal)
    if not required:
        todo_text = " ".join(
            str(item.get("content") or "")
            for item in list(state.get("todos") or [])
            if item.get("status") != "completed"
        )
        required = infer_required_tools(todo_text)
    must_embed = wants_document_photo(goal)
    todos = list(state.get("todos") or [])
    trace = list(state.get("execution_trace") or [])
    if required:
        plan = describe_plan(goal, required)
        logger.info(
            "turn_plan",
            conversation_id=state.get("conversation_id"),
            required_tools=required,
            must_embed_image=must_embed,
        )
    elif todos:
        plan = describe_plan(goal, [])
    elif wants_structured_plan(goal, required):
        plan = f"{describe_plan(goal, required)} · 先用 todo_write 列出步骤"
    else:
        plan = "无需调用工具，直接作答"
    trace.append(plan_step(plan, required, todos=todos))
    return {
        **state,
        "goal_text": goal,
        "required_tools": required,
        "must_embed_image": must_embed,
        "execution_trace": trace,
        "needs_retry": False,
    }
