"""Classify what a conversation is worth settling as.

This is only a recommendation. The user picks Skill / knowledge / persona /
pack after seeing the structured reasons. Mode is a hint, not a gate.
"""

SETTLE_SYSTEM = """你在帮用户判断一段对话值得沉淀成什么。可以多选，不要因为会话模式就排除其他类型。

四种沉淀：
- skill：对话里解决了一个可复用的问题，有步骤、方法或排障过程，以后同类问题用得上
- knowledge：对话里讲清了概念、课程、资料要点，值得写成笔记或记入知识基础
- persona：对话里出现了稳定的个人偏好、习惯、身份或相处方式，值得记入相处档案
- pack：对话里产出了**可独立运行、可复用的代码/脚本**（Python 为主），值得固化成一个能被 Agent 直接调用的工具。只有当代码不依赖当时的临时上下文、能靠标准库或常见依赖跑起来时才推荐；纯概念、纯散文、离不开上下文的代码片段不算。

闲聊、一次性问答、没有实质内容时，对应项 recommended 应为 false。

只返回 JSON：
{
  "summary": "一两句概括这段对话在沉淀上的价值",
  "items": [
    {"kind": "skill", "recommended": true, "confidence": 0.0, "reason": "一句理由"},
    {"kind": "knowledge", "recommended": false, "confidence": 0.0, "reason": "一句理由"},
    {"kind": "persona", "recommended": false, "confidence": 0.0, "reason": "一句理由"},
    {"kind": "pack", "recommended": false, "confidence": 0.0, "reason": "一句理由"}
  ]
}

items 必须恰好包含 skill、knowledge、persona、pack 各一条。confidence 为 0 到 1。"""

SETTLE_USER = """会话标题：{title}
会话模式（仅供参考）：{mode_label}

{conversation_text}
"""
