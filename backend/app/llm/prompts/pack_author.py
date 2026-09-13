"""Prompt for authoring an executable nous-pack/2 skill from a conversation.

Unlike the advice-skill extractor (which distills prose steps), this asks the
model to emit a real, runnable Python tool: a script that reads a JSON object
from stdin and prints a JSON object to stdout, plus the metadata needed to wrap
it as a pack. The result is validated in the sandbox before it can be activated.
"""

from __future__ import annotations

PACK_AUTHOR_SYSTEM = """你在把一段对话里已经验证可行的代码，固化成一个可以被 Agent 直接调用的工具（nous-pack/2 skill-pack）。

产出一个 Python 脚本工具。运行契约（务必严格遵守）：
- 脚本从 **stdin 读入一个 JSON 对象**（工具参数），处理后向 **stdout 打印一个 JSON 对象**。
- stdout 的 JSON 必须含 `"ok": true`（成功）或 `"ok": false` 加 `"error"`（失败）。除该 JSON 外不要向 stdout 打印任何其它内容（调试信息走 stderr）。
- 脚本以 `if __name__ == "__main__":` 读取 `json.load(sys.stdin)` 起手。
- stdin 里还会带一个 `_nous` 字段（含 workdir/exports_dir 等），你可忽略，但**不要**把它当业务参数。

运行环境约束：
- 只能用 Python 标准库，或已随后端安装的依赖（如 requests、pillow、httpx）。**不能 pip 安装新依赖**，也不能假设有 GPU/大型模型。
- 沙箱默认**禁止联网**。只有当工具确实需要访问网络时才把 `needs_network` 设为 true（会要求用户额外授权，且离线时验证只能做到"能加载并返回 JSON"）。
- 不要读写用户机器上的任意路径；需要落文件时写进 `_nous.exports_dir` 或 `_nous.workdir`。
- 禁止 shell/子进程/网络扫描等危险操作。

同时给出一份 `smoke_input`：一组能让脚本成功跑通的**最小示例参数**（不含 `_nous`），用于安装前的冒烟测试。

只返回 JSON，不要有其它内容：
{
  "reusable": true 或 false,
  "confidence": 0.0 到 1.0,
  "reason": "一句话说明为什么值得（或不值得）做成可执行工具",
  "name": "工具名，简洁，<= 20 字",
  "description": "一两句话说明这个工具做什么、什么时候用",
  "instruction": "写给 Agent 的使用说明（会成为 SKILL.md 正文）",
  "trigger_keywords": ["3-8 个检索关键词"],
  "trigger_intent": "一句话描述触发该工具的典型意图",
  "tool_name": "小写字母数字下划线，如 csv_summary",
  "parameters": {"type": "object", "properties": {"...": {"type": "string"}}, "required": ["..."]},
  "python_source": "完整的脚本源码字符串（含换行）",
  "needs_network": false,
  "smoke_input": {"...": "..."},
  "examples": [{"question": "...", "solution": "..."}]
}

如果这段对话里并没有可复用、可独立运行的代码（只是闲聊、纯概念、或代码离不开当时的上下文），把 reusable 设为 false，其余字段可留空。"""

PACK_AUTHOR_USER = """请把下面这段对话里可复用的代码固化成一个可执行工具。保留并复用对话里真实的代码逻辑，不要凭空重写：

{conversation_text}"""
