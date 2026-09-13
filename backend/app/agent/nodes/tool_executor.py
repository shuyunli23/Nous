"""Node: execute tool calls requested by the LLM."""

from __future__ import annotations

import json
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context_guard import note_call
from app.agent.context_spill import maybe_spill
from app.agent.execution_trace import guard_step, tool_step
from app.agent.progress import emit
from app.agent.state import AgentState
from app.agent.tools import execute_tool
from app.core.logging import get_logger
from app.llm.client import Message

logger = get_logger(__name__)


async def tool_executor_node(state: AgentState, *, session: AsyncSession) -> AgentState:
    tool_calls: list[dict] = state.get("tool_calls") or []
    messages: list[Message] = list(state.get("messages") or [])
    user_id = state.get("user_id")
    todos = list(state.get("todos") or [])
    trace = list(state.get("execution_trace") or [])
    chain = dict(state.get("repeat_chain") or {})
    conversation_id = state.get("conversation_id")

    for tc in tool_calls:
        fn = tc.get("function", {}) or {}
        name = fn.get("name", "unknown")
        call_id = tc.get("id", "")
        raw_args = fn.get("arguments", "{}")

        emit(
            {
                "type": "step_start",
                "node": "tool_executor",
                "kind": "tool",
                "title": name,
                "tool": name,
                "status": "running",
            }
        )
        logger.info("tool_invoke", tool=name, call_id=call_id)
        started = time.perf_counter()
        result = await execute_tool(
            name, raw_args, session=session, user_id=user_id
        )
        if not isinstance(result, dict):
            result = {"ok": True, "result": result}
        from app.agent.artifacts import attach_inspect

        result = attach_inspect(result)
        result = maybe_spill(
            result, tool=name, conversation_id=conversation_id
        )
        if name == "todo_write" and result.get("ok") and isinstance(result.get("todos"), list):
            todos = list(result["todos"])
        chain, reminder = note_call(chain, name=name, raw_args=raw_args)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        step = tool_step(
            name=name,
            call_id=call_id,
            raw_args=raw_args,
            result=result,
        )
        step["elapsed_ms"] = elapsed_ms
        if isinstance(result.get("inspect"), dict):
            step["inspect"] = result["inspect"]
        trace.append(step)
        emit(
            {
                "type": "step_end",
                "node": "tool_executor",
                "kind": "tool",
                "title": name,
                "tool": name,
                "elapsed_ms": elapsed_ms,
                "status": step.get("status") or "ok",
                "execution_trace": trace,
            }
        )
        result_msg: Message = {
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps(result, ensure_ascii=False, default=str),
        }
        messages.append(result_msg)
        if reminder:
            messages.append({"role": "user", "content": reminder})
            trace.append(guard_step(reminder))

    names = [
        str((tc.get("function") or {}).get("name") or "")
        for tc in tool_calls
    ]
    # Checklist updates are not work; counting them burned the 12-loop cap
    # before stats.py / create_webpage could run. They are not free either --
    # each still costs an LLM call, so they draw on their own budget.
    work_calls = [name for name in names if name and name != "todo_write"]
    loop_count = state.get("tool_loop_count") or 0
    todo_loop_count = state.get("todo_loop_count") or 0
    if work_calls:
        loop_count += 1
    elif names:
        todo_loop_count += 1

    return {
        **state,
        "messages": messages,
        "tool_calls": [],
        "todos": todos,
        "repeat_chain": chain,
        "tool_loop_count": loop_count,
        "todo_loop_count": todo_loop_count,
        "execution_trace": trace,
    }
