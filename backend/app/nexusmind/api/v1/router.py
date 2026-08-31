"""v1 路由汇总。

后续阶段新增的端点模块统一在这里挂载：
    Phase 2 -> knowledge / attachments
    Phase 4 -> models（AI 模型中心）
    Phase 5 -> search
    Phase 7 -> assistant / graph / vector search
"""

from __future__ import annotations

from fastapi import APIRouter

from app.nexusmind.api.v1.endpoints import (
    analysis,
    assistant,
    attachments,
    graph,
    knowledge,
    search,
    system,
)

api_router = APIRouter()
# 不挂 /health（与 Nous 冲突）和 models（模型中心已由 Nous Settings 承担）
api_router.include_router(system.router)
api_router.include_router(knowledge.router)
api_router.include_router(attachments.router)
api_router.include_router(analysis.router)
api_router.include_router(search.router)
api_router.include_router(assistant.router)
api_router.include_router(graph.router)
