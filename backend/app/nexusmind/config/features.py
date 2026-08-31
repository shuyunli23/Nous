"""能力开关。

后端按阶段交付，前端启动时读取 `/system/info` 拿到这张表，
把尚未实现的入口置灰，避免出现「点了没反应」的死链。
每完成一个 Phase，把对应开关翻成 True 即可。
"""

FEATURES: dict[str, bool] = {
    "knowledge_crud": True,      # Phase 2
    "markdown_import": True,     # Phase 2
    "attachments": True,         # Phase 2
    "markdown_reader": True,     # Phase 3
    "ai_analysis": True,         # Phase 4
    "model_center": True,        # Phase 4
    "search": True,              # Phase 5
    "ai_assistant": True,        # Phase 7
    "knowledge_graph": True,     # Phase 7
    "vector_search": True,       # Phase 7
}
