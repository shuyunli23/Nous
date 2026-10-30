"""Node: build the final messages list sent to the LLM."""

from __future__ import annotations

from typing import Any
import json

from app.agent.goal import format_success_criteria
from app.agent.skill_gate import is_recall_query, is_retry_or_continue, is_social_turn
from app.agent.state import AgentState
from app.agent.todo import TODO_GUIDANCE, format_todos_for_prompt
from app.chat_modes.catalog import TOOL_FULL, WORKBENCH, resolve_system_prompt
from app.llm.client import Message


async def compose_prompt_node(state: AgentState) -> AgentState:
    policy = state.get("tool_policy") or TOOL_FULL
    skills = state.get("retrieved_skills") or [] if policy == TOOL_FULL else []
    system_prompt = resolve_system_prompt(
        key=state.get("mode_key") or WORKBENCH,
        custom_prompt=state.get("mode_system_prompt") or "",
        injected_skills=skills if skills else None,
        use_long_term_memory=bool(state.get("use_long_term_memory")),
        use_knowledge_memory=bool(state.get("use_knowledge_memory")),
        persona_block=state.get("persona_block") or "",
        knowledge_block=state.get("knowledge_block") or "",
    )
    query = state.get("query") or ""
    if policy == TOOL_FULL and not is_social_turn(query):
        criteria = format_success_criteria(
            state.get("goal_text") or "",
            list(state.get("required_tools") or []),
        )
        if criteria:
            system_prompt = f"{system_prompt}\n\n{criteria}"
        if state.get("material_plan") and "review_materials" in (state.get("required_tools") or []):
            previous = json.dumps({"latest_files": state.get("material_files") or {}, "drafts": state.get("material_drafts") or {}, "plan": state["material_plan"]}, ensure_ascii=False)
            instruction = (
                "本轮继续未完成的材料，复用plan_id，先用read_material_draft核对已保存内容，再接着追加和导出。无需重新调用plan_materials，也不要覆盖已有成果。"
                if state.get("material_resume") else
                "根据本轮修改要求更新计划并重新调用plan_materials。继承仍适用的受众、内容和约束，"
                "不要从头猜测；总页数变化时以本轮要求为准。"
            )
            system_prompt += (
                "\n\n## 本会话最近的材料计划与文件\n"
                + instruction + "旧审查不能证明新版已通过。\n"
                + previous[:14000]
            )
        system_prompt = f"{system_prompt}\n\n{TODO_GUIDANCE}"
        standing = format_todos_for_prompt(list(state.get("todos") or []))
        if standing:
            system_prompt = f"{system_prompt}\n\n{standing}"

    if is_recall_query(query) or is_retry_or_continue(query):
        system_prompt += (
            "\n\n## 本轮注意\n"
            "用户在回顾刚才说过的话，或让你再试一次。"
            "以对话历史里的用户原话为准，不要否认历史中出现过的内容。"
            "「再试试 / 在试试」默认重复最近一次可执行的任务。"
        )

    messages: list[Message] = [{"role": "system", "content": system_prompt}]
    messages.extend(state.get("history") or [])

    user_content: str | list[dict[str, Any]] = state["query"]
    vision = state.get("vision_parts") or []
    if vision:
        user_content = [{"type": "text", "text": state["query"]}, *vision]
    messages.append({"role": "user", "content": user_content})

    return {**state, "system_prompt": system_prompt, "messages": messages}
