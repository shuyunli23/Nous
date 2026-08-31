"""系统级端点：健康检查、应用信息、仪表盘统计。"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from app.nexusmind.api.deps import DBSession
from app.nexusmind.config import settings
from app.nexusmind.config.features import FEATURES
from app.nexusmind.models import Attachment, Keyword, Knowledge, ModelConfig
from app.nexusmind.schemas.system import AppInfoResponse, DashboardStats
from app.nexusmind.services.knowledge_service import CHAT_DRAFT, searchable_clause

router = APIRouter(tags=["knowledge-system"])


@router.get("/system/info", response_model=AppInfoResponse, summary="知识库应用信息与能力开关")
def app_info() -> AppInfoResponse:
    return AppInfoResponse(
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        api_prefix=settings.API_PREFIX,
        debug=settings.DEBUG,
        max_attachment_size_mb=settings.MAX_ATTACHMENT_SIZE_MB,
        max_markdown_size_mb=settings.MAX_MARKDOWN_SIZE_MB,
        features=FEATURES,
    )


@router.get("/system/stats", response_model=DashboardStats, summary="仪表盘统计")
def dashboard_stats(db: DBSession) -> DashboardStats:
    """一次性聚合首页需要的所有计数，避免前端并发打多个接口。"""

    def count(stmt) -> int:  # noqa: ANN001 - 局部辅助
        return int(db.scalar(stmt) or 0)

    active = Knowledge.is_archived.is_(False)
    library = (active, searchable_clause())

    return DashboardStats(
        knowledge_total=count(select(func.count()).select_from(Knowledge).where(*library)),
        keyword_total=count(select(func.count()).select_from(Keyword)),
        attachment_total=count(select(func.count()).select_from(Attachment)),
        favorite_total=count(
            select(func.count()).select_from(Knowledge).where(*library, Knowledge.is_favorite.is_(True))
        ),
        important_total=count(
            select(func.count()).select_from(Knowledge).where(*library, Knowledge.is_important.is_(True))
        ),
        category_total=count(
            select(func.count(func.distinct(Knowledge.category))).where(
                Knowledge.category.is_not(None),
                *library,
            )
        ),
        model_config_total=count(select(func.count()).select_from(ModelConfig)),
        pending_total=count(
            select(func.count()).select_from(Knowledge).where(
                Knowledge.source_type == CHAT_DRAFT,
                Knowledge.is_archived.is_(False),
            )
        ),
    )
