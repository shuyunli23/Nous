"""Node: check whether this turn actually met the success criteria.

Mirrors Codex's observe/verify habit: the model is not allowed to stop just
because it wrote a fluent answer. If a required tool never succeeded, or the
reply invented an export URL, steer another LLM turn.
"""

from __future__ import annotations

from app.agent.execution_trace import verify_step
from app.agent.goal import evaluate_turn
from app.agent.state import AgentState
from app.core.config import settings
from app.core.logging import get_logger
from app.llm.client import Message

logger = get_logger(__name__)


async def verify_node(state: AgentState) -> AgentState:
    required = list(state.get("required_tools") or [])
    trace = list(state.get("execution_trace") or [])
    response = state.get("response") or ""
    verdict = evaluate_turn(
        required_tools=required,
        response=response,
        trace=trace,
        exports_dir=settings.resolve_path("./data/exports"),
        must_embed_image=bool(state.get("must_embed_image")),
        goal_text=state.get("goal_text") or "",
    )

    if verdict.complete:
        has_inspect = (
            verdict.inspect_summary
            and "no files" not in verdict.inspect_summary
        )
        if required or has_inspect:
            last_verify = next(
                (step for step in reversed(trace) if step.get("kind") == "verify"),
                None,
            )
            if last_verify is None or last_verify.get("status") != "ok":
                detail = "已核对"
                if required:
                    detail += " · " + "、".join(required) + " 已产出"
                if has_inspect:
                    detail += " · " + verdict.inspect_summary.replace("inspect: ", "")
                trace.append(verify_step(ok=True, detail=detail))
        return {**state, "needs_retry": False, "execution_trace": trace}

    attempts = (state.get("verify_attempts") or 0) + 1
    loop_count = state.get("tool_loop_count") or 0
    can_retry = (
        attempts <= settings.agent_max_verify_retries
        and loop_count < settings.agent_max_tool_loops
    )
    bits = []
    if verdict.missing_tools:
        bits.append("缺少 " + "、".join(verdict.missing_tools))
    if verdict.failed_tools:
        bits.append("失败 " + "、".join(verdict.failed_tools))
    if verdict.invented_urls:
        bits.append("编造了不存在的导出链接")
    if verdict.missing_embedded_image:
        bits.append("网页里没有照片")
    if verdict.delivery_gaps and not verdict.missing_embedded_image:
        bits.append("交付物与目标不一致")
    detail = "；".join(bits) or "目标未完成"
    if can_retry:
        detail += f" · 继续第 {attempts} 次"
    else:
        detail += " · 已达重试上限"
    trace.append(verify_step(ok=False, detail=detail))

    logger.info(
        "turn_verify",
        conversation_id=state.get("conversation_id"),
        complete=False,
        missing=verdict.missing_tools,
        invented=len(verdict.invented_urls),
        retry=can_retry,
        attempt=attempts,
    )

    updated: AgentState = {
        **state,
        "needs_retry": can_retry,
        "verify_attempts": attempts,
        "execution_trace": trace,
        "tool_calls": [],
    }
    if can_retry:
        messages: list[Message] = list(state.get("messages") or [])
        messages.append({"role": "user", "content": verdict.critique()})
        updated["messages"] = messages
    elif verdict.delivery_gaps or verdict.missing_embedded_image:
        note = (
            "\n\n未能完成：我核对了刚生成的文件，里面没有你要的内容"
            "（例如照片/配图并未真正嵌进去）。请再试一次，或改口说只要文字版。"
        )
        if note.strip() not in response:
            updated["response"] = response.rstrip() + note
    elif verdict.missing_tools:
        note = (
            "\n\n未能完成：还没有成功调用 "
            + "、".join(verdict.missing_tools)
            + "，所以没有可打开的文件。请再发一次，或说明只要文字说明。"
        )
        if note.strip() not in response:
            updated["response"] = response.rstrip() + note
    return updated


def should_continue_after_verify(state: AgentState) -> str:
    if state.get("needs_retry"):
        return "llm_call"
    return "persist"
