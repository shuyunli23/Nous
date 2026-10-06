"""Live execution progress for the chat UI (SSE).

LangGraph only yields after a node finishes. Wrapping nodes with start/end
emits lets the frontend highlight the active step and show elapsed seconds
while the turn is still running. No-op when no sink is bound (blocking /chat).
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token
from typing import Any

from app.agent.execution_trace import think_step, verify_step
from app.chat_modes.catalog import TOOL_FULL, TOOL_LIGHT, TOOL_NONE

ProgressSink = Callable[[dict[str, Any]], None]

_sink: ContextVar[ProgressSink | None] = ContextVar("agent_progress_sink", default=None)

# Nodes shown in the live timeline. Internal glue (memory / compose / persist)
# stays hidden so the list matches what the user already sees after a turn.
VISIBLE_NODES: dict[str, dict[str, str]] = {
    "retrieve_skills": {"kind": "skill_retrieve", "title": "检索 Skill"},
    "plan": {"kind": "plan", "title": "计划"},
    "llm_call": {"kind": "think", "title": "模型推理"},
    "tool_executor": {"kind": "tool", "title": "调用工具"},
    "verify": {"kind": "verify", "title": "核对"},
}


def bind_progress(sink: ProgressSink) -> Token[ProgressSink | None]:
    return _sink.set(sink)


def reset_progress(token: Token[ProgressSink | None]) -> None:
    _sink.reset(token)


def emit(event: dict[str, Any]) -> None:
    sink = _sink.get()
    if sink is not None:
        sink(event)


def has_sink() -> bool:
    return _sink.get() is not None


def _visible_for(name: str, state: dict[str, Any] | None) -> bool:
    if name not in VISIBLE_NODES:
        return False
    policy = (state or {}).get("tool_policy") or TOOL_FULL
    if policy == TOOL_NONE:
        return name == "llm_call"
    if policy == TOOL_LIGHT:
        return name in {"llm_call", "tool_executor", "verify"}
    return True


def emit_node_start(name: str, state: dict[str, Any] | None = None) -> None:
    if not _visible_for(name, state):
        return
    meta = VISIBLE_NODES[name]
    emit(
        {
            "type": "step_start",
            "node": name,
            "kind": meta["kind"],
            "title": meta["title"],
            "status": "running",
        }
    )


def emit_node_end(
    name: str,
    *,
    elapsed_ms: int,
    execution_trace: list[dict[str, Any]] | None = None,
    status: str = "ok",
    state: dict[str, Any] | None = None,
) -> None:
    if not _visible_for(name, state):
        return
    meta = VISIBLE_NODES[name]
    emit(
        {
            "type": "step_end",
            "node": name,
            "kind": meta["kind"],
            "elapsed_ms": elapsed_ms,
            "status": status,
            "execution_trace": execution_trace or [],
        }
    )


def _tool_call_names(tool_calls: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(tool_calls, list):
        return names
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        fn = call.get("function")
        name = None
        if isinstance(fn, dict):
            name = fn.get("name")
        if not name:
            name = call.get("name")
        if name:
            names.append(str(name))
    return names


def _think_detail(state: dict[str, Any] | None) -> str | None:
    """Model text from this llm_call, plus tool names when it chose to act."""
    if not state:
        return None
    content = str(state.get("response") or "").strip()
    names = _tool_call_names(state.get("tool_calls"))
    if names:
        suffix = "→ " + "、".join(names)
        return f"{content}\n{suffix}".strip() if content else suffix
    return content or None


def stamp_node_trace(
    name: str,
    trace: list[dict[str, Any]],
    *,
    before: int,
    elapsed_ms: int,
    state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Attach elapsed_ms to steps this node added; synthesize think/verify if needed."""
    out = list(trace)
    for step in out[before:]:
        if step.get("elapsed_ms") is None:
            step["elapsed_ms"] = elapsed_ms

    if name == "llm_call":
        out.append(think_step(elapsed_ms=elapsed_ms, detail=_think_detail(state)))
    elif name == "verify" and not any(
        step.get("kind") == "verify" for step in out[before:]
    ):
        # A greeting has nothing to check. Only close the trace when this
        # turn actually planned or called a tool.
        had_work = any(step.get("kind") in {"plan", "tool"} for step in out)
        if had_work:
            step = verify_step(ok=True, detail="已核对")
            step["elapsed_ms"] = elapsed_ms
            out.append(step)

    return out
