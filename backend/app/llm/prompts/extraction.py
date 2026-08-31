"""Prompts for the Skill Extractor chain."""

from __future__ import annotations

import re

REUSABILITY_JUDGE_SYSTEM = """你是一个 AI 技能库管理专家。你的任务是分析一段用户与 AI Agent 的对话，判断这段对话是否值得提炼为可复用的 Skill（经验知识片段）。

判断标准：
1. 对话解决了一个具体的技术/业务问题（而非闲聊、简单问答或纯概念解释）
2. 解决方案有可重复使用的步骤或方法
3. 未来其他类似问题可以从这个经验中获益
4. 对话包含足够信息来提炼出可操作的步骤

请以 JSON 格式回复，不要有任何其他内容：
{
  "reusable": true 或 false,
  "confidence": 0.0 到 1.0 之间的浮点数（表示复用价值的置信度）,
  "reason": "一句话说明判断理由"
}"""

REUSABILITY_JUDGE_USER = """请分析以下对话：

{conversation_text}

---
消息数量：{message_count}
---
请判断该对话是否值得提炼为可复用 Skill。"""


SKILL_DRAFT_SYSTEM = """你是一个 AI 技能提炼专家。你的任务是将一段解决问题的对话提炼为结构化的 Skill JSON。

Skill 的作用：当用户未来遇到类似问题时，Agent 会检索到该 Skill 并用它辅助回答。

要求：
- name：简洁准确，不超过 20 个字
- description：一两句话说明适用场景
- instruction：给 Agent 的操作指南，说明应如何使用该 Skill 辅助回答
- trigger_keywords：3-8 个关键词，用于关键词检索，覆盖同义词和常见变体
- trigger_intent：一句话描述触发该 Skill 的典型用户意图
- workflow：按步骤列出解决方案，每步包含 step/action/command(可选)/expect(可选)
- examples：从对话中摘录 1-2 个典型问答对。不要粘贴完整 SVG / HTML 源码，只写要点

请严格以 JSON 格式回复，不要有任何其他内容：
{
  "name": "...",
  "description": "...",
  "instruction": "...",
  "trigger_keywords": ["...", "..."],
  "trigger_intent": "...",
  "workflow": [
    {"step": 1, "action": "...", "command": "...", "expect": "..."}
  ],
  "examples": [
    {"question": "...", "solution": "..."}
  ],
  "tools": []
}"""

SKILL_DRAFT_USER = """请将以下对话提炼为 Skill：

{conversation_text}"""

_SVG_BLOCK = re.compile(
    r"(?:<\?xml\b[\s\S]*?\?>\s*)?<svg\b[\s\S]*?</svg\s*>",
    re.IGNORECASE,
)
_HTML_DOC = re.compile(
    r"<!DOCTYPE\s+html[\s\S]*?</html\s*>",
    re.IGNORECASE,
)

# Keep extraction prompts small: full SVG/HTML dumps blow the context window
# and make the draft JSON empty or truncated.
_PER_MESSAGE_CHARS = 4_000
_TOTAL_CHARS = 24_000


def compact_extraction_text(text: str, limit: int = _PER_MESSAGE_CHARS) -> str:
    """Replace bulky diagrams with placeholders and cap length."""

    def svg_repl(match: re.Match[str]) -> str:
        return f"[SVG 图已省略，{len(match.group(0))} 字符]"

    def html_repl(match: re.Match[str]) -> str:
        return f"[HTML 页已省略，{len(match.group(0))} 字符]"

    compact = _SVG_BLOCK.sub(svg_repl, text)
    compact = _HTML_DOC.sub(html_repl, compact)
    compact = compact.strip()
    if len(compact) > limit:
        compact = compact[:limit].rstrip() + "\n…[截断]"
    return compact


def format_conversation(messages: list[dict]) -> str:
    """Format message list into a readable text block for the LLM."""
    lines: list[str] = []
    role_map = {"user": "用户", "assistant": "Agent", "system": "系统", "tool": "工具"}
    for m in messages:
        role = role_map.get(m.get("role", ""), m.get("role", ""))
        content = compact_extraction_text((m.get("content") or "").strip())
        if content:
            lines.append(f"【{role}】{content}")
    text = "\n\n".join(lines)
    if len(text) > _TOTAL_CHARS:
        text = text[:_TOTAL_CHARS].rstrip() + "\n…[对话过长，已截断]"
    return text
