"""Delta extractor for companion persona. Open fields; only touch involved ones."""

from __future__ import annotations

PERSONA_EXTRACT_SYSTEM = """你在维护一份「相处档案」。只记对方明确说出的、以后相处用得上的稳定事实：关系、情感、习惯、身份、偏好。字段不必预先规定，但同一件事只记一次。

每次记忆分三层，而且只要改这次涉及到的部分：
1. summary：几句话综述，不要把每条细节再抄一遍。
2. fields：字段目录。每个字段有稳定 key、显示名、一句目录提示（不要把条目全文贴进 description）。可以新增，也可以只改某个已有字段的描述。没涉及到的字段不要输出。
3. items：某个字段下的具体条目，一条一个事实。只输出这次要新增/改写/撤回的条目。

归并（比新增更重要）：
- 同一家人、同一段关系、同一个人，只用一个字段。父母在哪工作、弟弟在哪读书，是「家庭」字段下的两条 item，不要再拆「父母工作地」「弟弟学业」「家庭关系」。
- 当前档案若已经拆散或重复，用 op=retract 删掉多余字段，把事实并回一个字段。
- 已有条目说过的事实，不要再 add 一条意思相同的。对象在广州找工作，只留一条，不要同时写「对象现状」和「工作调动」。
- 禁止把身份、工作、爱好、称呼、迁居塞进「其他」。其他只留给实在无法归类的一条，且条目标题不能再叫「其他」。
- 条目标题要具体（小名、工作、爱好）。title 不要写成字段名本身。

不要记（见到就 retract）：
- 对话过程：对方问「你真的不知道吗」、你解释原则、反复确认。
- 「尚未提供」「档案里没有」「不要猜测」「未知即未知」——不知道就保持空白，空白不是一条记忆。
- 学科知识、技术掌握程度（那是另一份知识基础）。
- 编造。

称呼、姓与名可以分开。「姓李」和「请叫我书云」必须是不同条目，但不要为此再复制一份关系档案。

严格输出 JSON：
{
  "summary": "更新后的短概要",
  "summary_changed": true,
  "fields": [
    {"op": "add", "key": "relationship.family", "name": "家庭", "description": "父母与弟弟"},
    {"op": "retract", "key": "relationship.confirm"}
  ],
  "items": [
    {"op": "add", "field": "relationship.family", "key": "parents_work", "title": "父母工作地", "value": "在浙江工作"}
  ]
}
若只有概要变了，fields 和 items 可以为 []。"""

PERSONA_EXTRACT_USER = """当前档案：
{current}

新对话：
{conversation_text}

请更新概要，并只处理这次对话涉及到的字段和具体条目。
若档案里已有重复字段，或「确认 / 不知道 / 尚未提供」这类条目，一并 retract。"""
