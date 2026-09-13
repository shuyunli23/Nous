"""LangGraph agent graph.

Codex-inspired turn loop, adapted to Nous (LangGraph, no OS sandbox):

  load_memory → retrieve_skills → plan → compose_prompt → llm_call
                                                             ↓
                                                   should_call_tools?
                                                  /              \\
                                              tools            verify
                                                ↑                  ↓
                                                └── llm_call ← retry?
                                                                   ↓
                                                                persist

Each node that needs DB access receives a pre-bound ``session`` kwarg via
``functools.partial`` at call time so the graph definition stays session-free.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger

from app.agent.nodes.compose_prompt import compose_prompt_node
from app.agent.nodes.llm_call import llm_call_node, should_call_tools
from app.agent.nodes.load_memory import load_memory_node
from app.agent.nodes.persist import persist_failed_turn, persist_node
from app.agent.nodes.plan import plan_node
from app.agent.nodes.retrieve_skills import retrieve_skills_node
from app.agent.nodes.tool_executor import tool_executor_node
from app.agent.nodes.verify import should_continue_after_verify, verify_node
from app.agent.progress import emit_node_end, emit_node_start, stamp_node_trace
from app.agent.state import (
    TODO_ONLY_LOOP_BUDGET,
    TOOL_LOOP_GRACE,
    AgentState,
)

NodeFn = Callable[..., Awaitable[AgentState]]

logger = get_logger(__name__)

_last_state: ContextVar[AgentState | None] = ContextVar(
    "agent_last_state", default=None
)


def remember_state(state: AgentState | None) -> None:
    _last_state.set(state)


def take_last_state() -> AgentState | None:
    return _last_state.get()


def graph_recursion_limit() -> int:
    """LangGraph hops allowed for one turn.

    Default is 25. A tool-heavy turn is startup (~5 hops) plus two hops
    per tool batch (llm_call → tool_executor), plus verify/persist and
    optional verify retries. Size the ceiling from the same knobs that
    already cap the loop -- including the grace batches, which the loop
    edge will happily spend -- so a 12-loop brief cannot die as an opaque
    ``GraphRecursionError``.
    """
    loops = (
        max(1, settings.agent_max_tool_loops)
        + TOOL_LOOP_GRACE
        + TODO_ONLY_LOOP_BUDGET
    )
    retries = max(0, settings.agent_max_verify_retries)
    return max(60, 8 + 3 * (loops + retries + 2))


def _track(name: str, fn: NodeFn) -> NodeFn:
    """Emit live start/end events and stamp elapsed_ms onto new trace steps."""

    async def wrapped(state: AgentState, **_kwargs: object) -> AgentState:
        emit_node_start(name, state)
        before = len(state.get("execution_trace") or [])
        started = time.perf_counter()
        try:
            result = await fn(state)
        except Exception:
            remember_state(state)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            emit_node_end(
                name,
                elapsed_ms=elapsed_ms,
                execution_trace=list(state.get("execution_trace") or []),
                status="error",
                state=state,
            )
            raise
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        trace = stamp_node_trace(
            name,
            list(result.get("execution_trace") or []),
            before=before,
            elapsed_ms=elapsed_ms,
            state=result,
        )
        updated = {**result, "execution_trace": trace}
        remember_state(updated)
        emit_node_end(
            name, elapsed_ms=elapsed_ms, execution_trace=trace, state=updated
        )
        return updated

    wrapped.__name__ = name
    wrapped.__qualname__ = name
    return wrapped


def build_graph(session: AsyncSession) -> StateGraph:
    """Return a compiled graph bound to the given async session."""

    graph = StateGraph(AgentState)

    # Bind session-aware nodes.
    _load = functools.partial(load_memory_node, session=session)
    _retrieve = functools.partial(retrieve_skills_node, session=session)
    _llm = functools.partial(llm_call_node, session=session)
    _tools = functools.partial(tool_executor_node, session=session)
    _persist = functools.partial(persist_node, session=session)

    graph.add_node("load_memory", _track("load_memory", _load))
    graph.add_node("retrieve_skills", _track("retrieve_skills", _retrieve))
    graph.add_node("plan", _track("plan", plan_node))
    graph.add_node("compose_prompt", _track("compose_prompt", compose_prompt_node))
    graph.add_node("llm_call", _track("llm_call", _llm))
    graph.add_node("tool_executor", _track("tool_executor", _tools))
    graph.add_node("verify", _track("verify", verify_node))
    graph.add_node("persist", _track("persist", _persist))

    graph.set_entry_point("load_memory")
    graph.add_edge("load_memory", "retrieve_skills")
    graph.add_edge("retrieve_skills", "plan")
    graph.add_edge("plan", "compose_prompt")
    graph.add_edge("compose_prompt", "llm_call")
    graph.add_conditional_edges(
        "llm_call",
        should_call_tools,
        {"tools": "tool_executor", "verify": "verify"},
    )
    graph.add_edge("tool_executor", "llm_call")
    graph.add_conditional_edges(
        "verify",
        should_continue_after_verify,
        {"llm_call": "llm_call", "persist": "persist"},
    )
    graph.add_edge("persist", END)

    return graph.compile()


async def run_agent(
    *,
    session: AsyncSession,
    user_id: str,
    conversation_id: str,
    query: str,
    title_source: str | None = None,
    vision_parts: list | None = None,
    mode_key: str = "workbench",
    tool_policy: str = "full",
    use_long_term_memory: bool = False,
    use_knowledge_memory: bool = False,
    persona_block: str = "",
    knowledge_block: str = "",
    mode_system_prompt: str = "",
) -> AgentState:
    """Execute the graph and return the final state."""
    app = build_graph(session)
    initial: AgentState = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "query": query,
        "title_source": title_source or query,
        "vision_parts": list(vision_parts or []),
        "tool_loop_count": 0,
        "todo_loop_count": 0,
        "verify_attempts": 0,
        "needs_retry": False,
        "required_tools": [],
        "must_embed_image": False,
        "mode_key": mode_key,
        "tool_policy": tool_policy,
        "use_long_term_memory": use_long_term_memory,
        "use_knowledge_memory": use_knowledge_memory,
        "persona_block": persona_block,
        "knowledge_block": knowledge_block,
        "mode_system_prompt": mode_system_prompt,
    }
    remember_state(initial)
    try:
        try:
            final: AgentState = await app.ainvoke(
                initial,
                config={"recursion_limit": graph_recursion_limit()},
            )
        except Exception as exc:
            snapshot = take_last_state() or initial
            mapped = _map_run_error(exc, conversation_id)
            if not isinstance(exc, AppError | GraphRecursionError):
                logger.exception("agent_run_failed", error=str(exc))
            await persist_failed_turn(
                snapshot,
                session=session,
                reason=mapped.message,
            )
            raise mapped from exc
        return final
    finally:
        remember_state(None)


def _map_run_error(exc: Exception, conversation_id: str) -> AppError:
    details: dict = {"conversation_id": conversation_id}
    if isinstance(exc, GraphRecursionError):
        details["recursion_limit"] = graph_recursion_limit()
        return AppError(
            "This turn used too many graph steps before finishing. "
            "Split the task, or raise AGENT_MAX_TOOL_LOOPS and retry.",
            details=details,
        )
    if isinstance(exc, AppError):
        merged = {**exc.details, **details}
        exc.details = merged
        return exc
    # Anything else is a bug or an environment problem. The traceback only goes
    # to the server log, which is gone by the time anyone reads the chat, so
    # name the exception in details -- otherwise the stored turn says nothing.
    details["exception"] = type(exc).__name__
    details["exception_message"] = str(exc)[:300]
    if _is_db_contention(exc):
        return AppError(
            "The database was locked by another process, so this turn could "
            "not be saved. Send it again. (SQLite allows one writer: stop any "
            "test script or second server writing the same data/*.db file.)",
            details=details,
        )
    return AppError(
        "This turn stopped before a reply was finished.",
        details=details,
    )


def _is_db_contention(exc: Exception) -> bool:
    """SQLite single-writer contention -- transient, worth retrying verbatim."""
    text = str(exc).lower()
    return "database is locked" in text or "database table is locked" in text
