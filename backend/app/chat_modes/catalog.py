"""Built-in chat mode catalog (keys, tool policy, prompt source)."""

from __future__ import annotations

from typing import Any

from app.llm.prompts.chat_system import build_system_prompt
from app.llm.prompts.companion_system import COMPANION_SYSTEM
from app.llm.prompts.tutor_system import TUTOR_SYSTEM

WORKBENCH = "workbench"
TUTOR = "tutor"
COMPANION = "companion"

TOOL_FULL = "full"
TOOL_LIGHT = "light"
TOOL_NONE = "none"

LIGHT_TOOLS = frozenset(
    {
        "web_search",
        "fetch_url",
        "get_weather",
        "calculator",
        "current_datetime",
    }
)

PERSONA_PLACEHOLDER = """
## 关于我（相处档案）
长期记忆已打开。会先给你概要和字段目录（字段可按需要增加：关系、情感、习惯等）；具体条目只展开和这轮对话有关的字段。先按你此刻说的来。不要把这些写进知识库，也不要拿到学习模式里用。
""".strip()

KNOWLEDGE_PLACEHOLDER = """
## 关于我（知识基础）
知识基础已打开。会先给你概要和字段目录（主题字段可按需要增加）；具体条目只展开和这轮问题有关的字段。先按你这次说的基础来讲，不必让用户再自我介绍一遍。不要写入情感、人际关系或私人社会经历。
""".strip()

# Backward-compatible alias used by older tests / copy.
MEMORY_PLACEHOLDER = PERSONA_PLACEHOLDER


def builtin_specs() -> list[dict[str, Any]]:
    """Rows upserted on startup. Prompts for builtins live in code, not DB."""
    return [
        {
            "key": WORKBENCH,
            "name": "工作台",
            "description": "办事：搜索、工具、网页 Demo、PPT、PDF。现在的主模式。",
            "tool_policy": TOOL_FULL,
            "use_long_term_memory": False,
            "use_knowledge_memory": False,
            "sort_order": 0,
        },
        {
            "key": TUTOR,
            "name": "学习",
            "description": "带你把问题搞懂。可选用知识基础，不必每次重说你会什么。",
            "tool_policy": TOOL_LIGHT,
            "use_long_term_memory": False,
            "use_knowledge_memory": False,
            "sort_order": 1,
        },
        {
            "key": COMPANION,
            "name": "陪伴",
            "description": "有温度的聊天，慢慢了解你的关系、情感和习惯。也可选用知识基础。",
            "tool_policy": TOOL_LIGHT,
            "use_long_term_memory": True,
            "use_knowledge_memory": False,
            "sort_order": 2,
        },
    ]


def resolve_system_prompt(
    *,
    key: str,
    custom_prompt: str = "",
    injected_skills: list[dict] | None = None,
    use_long_term_memory: bool = False,
    use_knowledge_memory: bool = False,
    persona_block: str = "",
    knowledge_block: str = "",
) -> str:
    if key == WORKBENCH:
        prompt = build_system_prompt(injected_skills=injected_skills)
    elif key == TUTOR:
        prompt = TUTOR_SYSTEM.strip()
    elif key == COMPANION:
        prompt = COMPANION_SYSTEM.strip()
    else:
        prompt = (custom_prompt or "").strip() or (
            "你是用户自定义的对话助手。按用户写的系统提示词行事；"
            "若提示词为空，就做一名简洁、真诚的助手。"
        )
    if use_long_term_memory:
        block = (persona_block or "").strip() or PERSONA_PLACEHOLDER
        prompt = prompt.rstrip() + "\n\n" + block
    if use_knowledge_memory:
        block = (knowledge_block or "").strip() or KNOWLEDGE_PLACEHOLDER
        prompt = prompt.rstrip() + "\n\n" + block
    return prompt
