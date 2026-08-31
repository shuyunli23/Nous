"""知识 AI 分析编排：LLM 优先，失败/未配置则本地兜底。"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.nexusmind.models import AnalysisStatus, Knowledge
from app.nexusmind.schemas.model_config import AnalysisResultOut
from app.nexusmind.services import keyword_service, knowledge_service, local_keyword_service, model_config_service
from app.nexusmind.services.llm_service import ModelEndpoint, analyze_document

logger = logging.getLogger(__name__)


async def analyze_knowledge(
    db: Session,
    knowledge_id: str,
    *,
    model_id: str | None = None,
    force_local: bool = False,
) -> AnalysisResultOut:
    item = knowledge_service.get_knowledge(db, knowledge_id)

    item.analysis_status = AnalysisStatus.RUNNING.value
    item.analysis_error = None
    db.commit()

    source = "local"
    analyzed_by = "local:jieba"
    error_msg: str | None = None
    result: dict

    model = None
    if not force_local:
        if model_id:
            model = model_config_service.get_model(db, model_id)
        else:
            model = model_config_service.get_default_model(db)

    if model is not None and model.is_active:
        try:
            endpoint = ModelEndpoint.from_config(model)
            result = await analyze_document(
                endpoint,
                title=item.title,
                content=item.markdown_content or item.plain_text or "",
            )
            source = "ai"
            analyzed_by = f"{model.provider}/{model.model_name}"
            status = AnalysisStatus.DONE.value
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM analysis failed for %s: %s", knowledge_id, exc)
            error_msg = str(exc)
            result = local_keyword_service.extract_local_analysis(
                item.plain_text or item.markdown_content or "",
                title=item.title,
            )
            source = "local"
            analyzed_by = "local:jieba"
            status = AnalysisStatus.FALLBACK.value
    else:
        from app.nexusmind.services.nous_llm import nous_analyze_document, nous_llm_ready

        if not force_local and nous_llm_ready():
            try:
                result, analyzed_by = await nous_analyze_document(
                    title=item.title,
                    content=item.markdown_content or item.plain_text or "",
                )
                source = "ai"
                status = AnalysisStatus.DONE.value
            except Exception as exc:  # noqa: BLE001
                logger.warning("Nous LLM analysis failed for %s: %s", knowledge_id, exc)
                error_msg = str(exc)
                result = local_keyword_service.extract_local_analysis(
                    item.plain_text or item.markdown_content or "",
                    title=item.title,
                )
                source = "local"
                analyzed_by = "local:jieba"
                status = AnalysisStatus.FALLBACK.value
        else:
            result = local_keyword_service.extract_local_analysis(
                item.plain_text or item.markdown_content or "",
                title=item.title,
            )
            status = AnalysisStatus.FALLBACK.value
            if not force_local:
                error_msg = "未配置可用模型，已使用本地算法"

    keyword_names = _apply_result(
        db, item, result, source=source, status=status, analyzed_by=analyzed_by, error=error_msg
    )
    db.commit()
    try:
        from app.nexusmind.services import embedding_service

        embedding_service.upsert_embedding(db, knowledge_id)
    except Exception:  # noqa: BLE001
        logger.debug("embedding upsert after analysis skipped", exc_info=True)
    db.expire_all()
    item = knowledge_service.get_knowledge(db, knowledge_id)

    return AnalysisResultOut(
        knowledge_id=item.id,
        analysis_status=item.analysis_status,
        summary=item.summary,
        category=item.category,
        keywords=keyword_names or [k.name for k in item.keywords],
        analyzed_by_model=item.analyzed_by_model,
        analysis_error=item.analysis_error,
        source=source,
    )


def _apply_result(
    db: Session,
    item: Knowledge,
    result: dict,
    *,
    source: str,
    status: str,
    analyzed_by: str,
    error: str | None,
) -> list[str]:
    weights = result.get("keyword_weights")
    if not weights:
        weights = [(k, 1.0) for k in result.get("keywords") or []]

    bound = keyword_service.replace_knowledge_keywords(
        db,
        item.id,
        [(str(n), float(w)) for n, w in weights],
        source=source,
    )

    summary = (result.get("summary") or "").strip()
    if summary:
        item.summary = summary[:1000]

    category = (result.get("category") or "").strip()
    # 仅在原分类为空时写入，避免覆盖用户手动分类；若用户未设则采用 AI
    if category and not item.category:
        item.category = category[:64]

    item.analysis_status = status
    item.analysis_error = (error[:1000] if error else None)
    item.analyzed_by_model = analyzed_by[:128]
    return [k.name for k in bound]


def analyze_knowledge_sync(knowledge_id: str, *, force_local: bool = False) -> None:
    """供 BackgroundTasks 调用的同步包装。"""
    import asyncio

    from app.nexusmind.db.session import SessionLocal

    db = SessionLocal()
    try:
        asyncio.run(analyze_knowledge(db, knowledge_id, force_local=force_local))
    except Exception:  # noqa: BLE001
        logger.exception("Background analysis failed for %s", knowledge_id)
        try:
            item = db.get(Knowledge, knowledge_id)
            if item is not None:
                item.analysis_status = AnalysisStatus.FAILED.value
                item.analysis_error = "后台分析失败"
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()
