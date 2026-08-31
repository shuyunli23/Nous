"""Delta extractor for knowledge background. Open fields; only touch involved ones."""

from __future__ import annotations

KNOWLEDGE_EXTRACT_SYSTEM = """你在维护一份「知识基础」。字段不必预先规定：主题、缺口、讲解偏好、用语，或这次新出现的知识切片都可以新增字段。

每次记忆分三层，而且只要改这次涉及到的部分：
1. summary：更新知识基础的短概要。
2. fields：字段目录（key、显示名、一句描述）。可新增，也可只改涉及字段的描述。没涉及到的不要输出。
3. items：字段下的具体条目。只输出这次要新增/改写/撤回的。

严禁：
- 不要整份重写。
- 不要覆盖无关主题。
- 不要记录心情、恋爱、家人朋友、人际关系。
- 不要编造。

严格输出 JSON：
{
  "summary": "更新后的短概要",
  "summary_changed": true,
  "fields": [
    {"op": "add", "key": "topic.linear_algebra", "name": "线性代数", "description": "中等；会矩阵乘法"}
  ],
  "items": [
    {"op": "update", "field": "topic.linear_algebra", "key": "level", "title": "程度", "value": "intermediate；会矩阵乘法，特征值还不熟"}
  ]
}
若只有概要变了，fields 和 items 可以为 []。"""

KNOWLEDGE_EXTRACT_USER = """当前知识基础：
{current}

学习对话：
{conversation_text}

请更新概要，并只处理这次对话涉及到的字段和具体条目。"""
