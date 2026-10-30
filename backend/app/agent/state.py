"""LangGraph agent state definition."""

from __future__ import annotations

from typing import Any, TypedDict

from app.llm.client import Message, Usage

# Extra tool batches allowed past ``agent_max_tool_loops`` so a call the model
# just issued is not dropped on the floor at the cap. Shared by the loop edge
# (llm_call), the retry gate (verify) and the graph recursion ceiling, which
# must all agree on where a turn really ends.
TOOL_LOOP_GRACE = 2

# Checklist-only rounds do no work, so tool_executor does not spend a work loop
# on them -- but they still cost an LLM call, so they get their own small budget.
# Without it a model that keeps re-emitting todo_write never moves the work
# counter and only the graph recursion ceiling stops the turn, as an opaque
# GraphRecursionError instead of a normal verify.
TODO_ONLY_LOOP_BUDGET = 3
# Only consecutive checklist-only batches count. Actual work resets the streak.
MATERIAL_TODO_ONLY_LOOP_BUDGET = 12


def is_material_turn(state: dict[str, Any]) -> bool:
    return bool({"plan_materials", "review_materials"}.intersection(state.get("required_tools") or []))


def todo_only_loop_limit(state: dict[str, Any]) -> int:
    return MATERIAL_TODO_ONLY_LOOP_BUDGET if is_material_turn(state) else TODO_ONLY_LOOP_BUDGET


def tool_loop_limit(state: dict[str, Any]) -> int:
    from app.core.config import settings

    if is_material_turn(state):
        return max(settings.agent_max_tool_loops, settings.materials_max_tool_loops)
    return settings.agent_max_tool_loops


class AgentState(TypedDict, total=False):
    # Inputs (set before graph runs)
    user_id: str
    conversation_id: str
    query: str                          # current user message
    title_source: str                   # short text used for auto titles
    vision_parts: list[dict[str, Any]]  # OpenAI image_url parts for this turn

    # Built during graph execution
    history: list[Message]              # loaded from DB
    retrieved_skills: list[dict[str, Any]]  # skill dicts from retriever
    system_prompt: str
    messages: list[Message]             # full prompt sent to LLM

    # LLM outputs
    response: str
    tool_calls: list[dict[str, Any]]
    finish_reason: str
    usage: dict[str, Any]

    # Control
    tool_loop_count: int
    todo_loop_count: int          # rounds that only touched the checklist
    verify_attempts: int
    needs_retry: bool
    verification_complete: bool
    required_tools: list[str]
    goal_text: str
    must_embed_image: bool
    material_plan_id: str | None
    material_plan: dict[str, Any] | None
    material_files: dict[str, str]
    material_drafts: dict[str, dict[str, Any]]
    material_resume: bool
    todos: list[dict[str, str]]
    error: str | None
    mode_key: str
    tool_policy: str
    use_long_term_memory: bool
    use_knowledge_memory: bool
    persona_block: str
    knowledge_block: str
    mode_system_prompt: str

    # Repeat-tool guard chain (in-turn, not persisted).
    repeat_chain: dict[str, Any]

    # Compact steps for the chat UI (skills / tools / answer)
    execution_trace: list[dict[str, Any]]

    # Written back to DB by the persist node
    assistant_message_id: str
    used_skill_ids: list[str]
    skill_similarities: dict[str, float]
