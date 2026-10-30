"""A material turn can spend each allowed checklist streak without crashing."""

from __future__ import annotations

import asyncio

from app.agent import graph
from app.agent.nodes import tool_executor
from app.agent.state import MATERIAL_TODO_ONLY_LOOP_BUDGET, TOOL_LOOP_GRACE
from app.core.config import settings


def test_real_work_resets_can_use_the_full_graph_budget(monkeypatch):
    monkeypatch.setattr(settings, "agent_max_tool_loops", 3)
    monkeypatch.setattr(settings, "materials_max_tool_loops", 3)
    work_limit = 3 + TOOL_LOOP_GRACE
    calls = []

    async def keep(state, **kwargs):
        return state

    async def model(state, **kwargs):
        work = state.get("tool_loop_count", 0)
        streak = state.get("todo_loop_count", 0)
        if streak < MATERIAL_TODO_ONLY_LOOP_BUDGET:
            name = "todo_write"
        elif work < work_limit:
            name = "web_search"
        else:
            return {**state, "tool_calls": [], "response": "Finished"}
        return {**state, "tool_calls": [{"id": f"batch-{len(calls)}", "function": {
            "name": name, "arguments": "{}",
        }}]}

    async def execute(name, arguments, **kwargs):
        calls.append(name)
        return {"ok": True, "todos": []} if name == "todo_write" else {"ok": True}

    async def verify(state, **kwargs):
        return {**state, "needs_retry": False, "verification_complete": True}

    for name in ("load_memory_node", "retrieve_skills_node", "plan_node", "compose_prompt_node", "persist_node"):
        monkeypatch.setattr(graph, name, keep)
    monkeypatch.setattr(graph, "llm_call_node", model)
    monkeypatch.setattr(graph, "verify_node", verify)
    monkeypatch.setattr(tool_executor, "execute_tool", execute)
    app = graph.build_graph(object())
    result = asyncio.run(app.ainvoke({
        "query": "Build training materials", "required_tools": ["review_materials"],
        "tool_loop_count": 0, "todo_loop_count": 0,
    }, config={"recursion_limit": graph.graph_recursion_limit()}))
    assert result["verification_complete"] is True
    assert result["response"] == "Finished"
    assert calls.count("web_search") == work_limit
    assert calls.count("todo_write") == (work_limit + 1) * MATERIAL_TODO_ONLY_LOOP_BUDGET
