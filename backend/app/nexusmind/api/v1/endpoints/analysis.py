"""知识 AI 分析 API。"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Query

from app.nexusmind.api.deps import DBSession
from app.nexusmind.schemas.knowledge import KnowledgeDetail
from app.nexusmind.schemas.model_config import AnalysisResultOut
from app.nexusmind.services import ai_analysis_service, knowledge_service

router = APIRouter(tags=["analysis"])


def _to_detail(item) -> KnowledgeDetail:  # noqa: ANN001
    return KnowledgeDetail.model_validate(item)


@router.post(
    "/knowledge/{knowledge_id}/analyze",
    response_model=AnalysisResultOut,
    summary="分析知识（关键词 / 分类 / 摘要）",
)
async def analyze_knowledge(
    knowledge_id: str,
    db: DBSession,
    model_id: str | None = Query(default=None, description="指定模型；默认用 is_default"),
    force_local: bool = Query(default=False, description="强制使用本地算法"),
) -> AnalysisResultOut:
    return await ai_analysis_service.analyze_knowledge(
        db,
        knowledge_id,
        model_id=model_id,
        force_local=force_local,
    )


@router.post(
    "/knowledge/{knowledge_id}/analyze/async",
    response_model=KnowledgeDetail,
    summary="后台异步分析（立即返回）",
)
async def analyze_knowledge_async(
    knowledge_id: str,
    db: DBSession,
    background_tasks: BackgroundTasks,
    force_local: bool = Query(default=False),
) -> KnowledgeDetail:
    """创建/导入后可调用；前端轮询详情的 analysis_status。"""
    item = knowledge_service.get_knowledge(db, knowledge_id)
    from app.nexusmind.models import AnalysisStatus

    item.analysis_status = AnalysisStatus.RUNNING.value
    item.analysis_error = None
    db.commit()
    background_tasks.add_task(
        ai_analysis_service.analyze_knowledge_sync,
        knowledge_id,
        force_local=force_local,
    )
    return _to_detail(knowledge_service.get_knowledge(db, knowledge_id))
