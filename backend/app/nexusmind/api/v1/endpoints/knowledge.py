"""知识条目 API。"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, UploadFile, status

from app.nexusmind.api.deps import DBSession, Pagination
from app.nexusmind.schemas.common import MessageResponse, Page
from app.nexusmind.schemas.knowledge import (
    CategoryStat,
    KnowledgeCreate,
    KnowledgeDetail,
    KnowledgeImportResult,
    KnowledgeSummary,
    KnowledgeUpdate,
)
from app.nexusmind.services import ai_analysis_service, knowledge_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _to_summary(item) -> KnowledgeSummary:  # noqa: ANN001
    data = KnowledgeSummary.model_validate(item)
    return data.model_copy(update={"attachment_count": len(item.attachments or [])})


def _to_detail(item) -> KnowledgeDetail:  # noqa: ANN001
    return KnowledgeDetail.model_validate(item)


@router.get("", response_model=Page[KnowledgeSummary], summary="知识列表")
def list_knowledge(
    db: DBSession,
    pagination: Pagination,
    q: str | None = Query(default=None, description="标题/摘要/正文关键词"),
    category: str | None = Query(default=None),
    is_favorite: bool | None = Query(default=None),
    is_important: bool | None = Query(default=None),
    include_archived: bool = Query(default=False),
    pending_import: bool = Query(default=False, description="只看待导入的学习草稿"),
) -> Page[KnowledgeSummary]:
    items, total = knowledge_service.list_knowledge(
        db,
        page=pagination.page,
        page_size=pagination.page_size,
        q=q,
        category=category,
        is_favorite=is_favorite,
        is_important=is_important,
        include_archived=include_archived,
        pending_import=pending_import or None,
    )
    return Page(
        items=[_to_summary(i) for i in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/categories", response_model=list[CategoryStat], summary="分类统计")
def categories(db: DBSession) -> list[CategoryStat]:
    rows = knowledge_service.list_categories(db)
    return [CategoryStat(name=name, count=count) for name, count in rows]


@router.post(
    "",
    response_model=KnowledgeDetail,
    status_code=status.HTTP_201_CREATED,
    summary="创建笔记",
)
def create_knowledge(
    payload: KnowledgeCreate,
    db: DBSession,
    background_tasks: BackgroundTasks,
    auto_analyze: bool = Query(default=True, description="创建后自动触发 AI/本地分析"),
) -> KnowledgeDetail:
    item = knowledge_service.create_knowledge(db, payload)
    if auto_analyze:
        from app.nexusmind.models import AnalysisStatus

        item.analysis_status = AnalysisStatus.RUNNING.value
        db.commit()
        background_tasks.add_task(ai_analysis_service.analyze_knowledge_sync, item.id)
        item = knowledge_service.get_knowledge(db, item.id)
    return _to_detail(item)


@router.post(
    "/import",
    response_model=KnowledgeImportResult,
    status_code=status.HTTP_201_CREATED,
    summary="导入 Markdown（可选附件 zip）",
)
async def import_knowledge(
    db: DBSession,
    background_tasks: BackgroundTasks,
    markdown_file: UploadFile = File(..., description=".md 文件"),
    archive_file: UploadFile | None = File(
        default=None, description="可选附件压缩包 .zip"
    ),
    title: str | None = Form(default=None),
    category: str | None = Form(default=None),
    auto_analyze: bool = Form(default=True),
) -> KnowledgeImportResult:
    item, imported, warnings = await knowledge_service.import_markdown(
        db,
        markdown_file=markdown_file,
        archive_file=archive_file,
        category=category,
        title=title,
    )
    if auto_analyze:
        from app.nexusmind.models import AnalysisStatus

        item.analysis_status = AnalysisStatus.RUNNING.value
        db.commit()
        background_tasks.add_task(ai_analysis_service.analyze_knowledge_sync, item.id)
        item = knowledge_service.get_knowledge(db, item.id)
    return KnowledgeImportResult(
        knowledge=_to_detail(item),
        imported_attachments=imported,
        warnings=warnings,
    )


@router.post(
    "/{knowledge_id}/confirm-import",
    response_model=KnowledgeDetail,
    summary="确认把学习草稿写入知识库",
)
def confirm_import(
    knowledge_id: str,
    db: DBSession,
    background_tasks: BackgroundTasks,
) -> KnowledgeDetail:
    item = knowledge_service.confirm_import(db, knowledge_id)
    from app.nexusmind.models import AnalysisStatus

    item.analysis_status = AnalysisStatus.RUNNING.value
    db.commit()
    background_tasks.add_task(ai_analysis_service.analyze_knowledge_sync, item.id)
    item = knowledge_service.get_knowledge(db, item.id)
    return _to_detail(item)


@router.get("/{knowledge_id}", response_model=KnowledgeDetail, summary="知识详情")
def get_knowledge(knowledge_id: str, db: DBSession) -> KnowledgeDetail:
    return _to_detail(knowledge_service.get_knowledge(db, knowledge_id))


@router.patch("/{knowledge_id}", response_model=KnowledgeDetail, summary="更新笔记")
def update_knowledge(
    knowledge_id: str, payload: KnowledgeUpdate, db: DBSession
) -> KnowledgeDetail:
    return _to_detail(knowledge_service.update_knowledge(db, knowledge_id, payload))


@router.delete(
    "/{knowledge_id}",
    response_model=MessageResponse,
    summary="删除笔记",
)
def delete_knowledge(knowledge_id: str, db: DBSession) -> MessageResponse:
    knowledge_service.delete_knowledge(db, knowledge_id)
    return MessageResponse(message="已删除")


@router.post(
    "/{knowledge_id}/favorite",
    response_model=KnowledgeDetail,
    summary="切换收藏",
)
def toggle_favorite(knowledge_id: str, db: DBSession) -> KnowledgeDetail:
    return _to_detail(knowledge_service.toggle_flag(db, knowledge_id, "is_favorite"))


@router.post(
    "/{knowledge_id}/important",
    response_model=KnowledgeDetail,
    summary="切换重要标记",
)
def toggle_important(knowledge_id: str, db: DBSession) -> KnowledgeDetail:
    return _to_detail(knowledge_service.toggle_flag(db, knowledge_id, "is_important"))


@router.post(
    "/{knowledge_id}/archive",
    response_model=KnowledgeDetail,
    summary="切换归档",
)
def toggle_archive(knowledge_id: str, db: DBSession) -> KnowledgeDetail:
    return _to_detail(knowledge_service.toggle_flag(db, knowledge_id, "is_archived"))
