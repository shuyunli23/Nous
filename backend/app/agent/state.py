"""LangGraph agent state definition."""

from __future__ import annotations

from typing import Any, TypedDict

from app.llm.client import Message, Usage


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
    verify_attempts: int
    needs_retry: bool
    required_tools: list[str]
    goal_text: str
    must_embed_image: bool
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
