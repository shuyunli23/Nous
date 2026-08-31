"""系统信息与统计 Schema。"""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    version: str


class AppInfoResponse(BaseModel):
    """前端启动时拉取一次，用于展示版本号与后端能力开关。"""

    app: str
    version: str
    description: str
    api_prefix: str
    debug: bool
    max_attachment_size_mb: int
    max_markdown_size_mb: int
    # 后端已就绪的能力，前端据此灰化未完成的入口
    features: dict[str, bool]


class DashboardStats(BaseModel):
    """仪表盘概览数据。"""

    knowledge_total: int = 0
    keyword_total: int = 0
    attachment_total: int = 0
    favorite_total: int = 0
    important_total: int = 0
    category_total: int = 0
    model_config_total: int = 0
    pending_total: int = 0
