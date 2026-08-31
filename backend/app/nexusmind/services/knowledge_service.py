"""知识条目业务服务：CRUD、导入、标记。"""

from __future__ import annotations

import io
import zipfile
from typing import Any

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.nexusmind.config import settings
from app.nexusmind.models import Knowledge, KnowledgeSource
from app.nexusmind.schemas.knowledge import KnowledgeCreate, KnowledgeUpdate
from app.nexusmind.services import attachment_service, markdown_service
from app.nexusmind.utils.errors import NotFoundError, ValidationError

CHAT_DRAFT = KnowledgeSource.CHAT_DRAFT.value


def searchable_clause():
    """Drafts stay out of the library, search, graph, and assistant."""
    return Knowledge.source_type != CHAT_DRAFT


def conversation_source_filename(conversation_id: str) -> str:
    return f"conversation:{conversation_id}"


def _load_options():
    return (
        selectinload(Knowledge.keywords),
        selectinload(Knowledge.attachments),
    )


def get_knowledge(db: Session, knowledge_id: str) -> Knowledge:
    item = db.scalar(
        select(Knowledge).options(*_load_options()).where(Knowledge.id == knowledge_id)
    )
    if item is None:
        raise NotFoundError("知识条目不存在")
    return item


def list_knowledge(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    category: str | None = None,
    is_favorite: bool | None = None,
    is_important: bool | None = None,
    include_archived: bool = False,
    pending_import: bool | None = None,
) -> tuple[list[Knowledge], int]:
    """分页列表。`q` 匹配标题 / 摘要 / 分类（全文检索留给 Phase 5）。"""
    filters = []
    if pending_import:
        filters.append(Knowledge.source_type == CHAT_DRAFT)
    else:
        filters.append(searchable_clause())
    if not include_archived:
        filters.append(Knowledge.is_archived.is_(False))
    if category:
        filters.append(Knowledge.category == category.strip())
    if is_favorite is not None:
        filters.append(Knowledge.is_favorite.is_(is_favorite))
    if is_important is not None:
        filters.append(Knowledge.is_important.is_(is_important))
    if q:
        keyword = f"%{q.strip()}%"
        filters.append(
            or_(
                Knowledge.title.ilike(keyword),
                Knowledge.summary.ilike(keyword),
                Knowledge.category.ilike(keyword),
                Knowledge.plain_text.ilike(keyword),
            )
        )

    count_stmt = select(func.count()).select_from(Knowledge)
    list_stmt = select(Knowledge).options(*_load_options())
    if filters:
        count_stmt = count_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)

    total = int(db.scalar(count_stmt) or 0)
    items = list(
        db.scalars(
            list_stmt.order_by(Knowledge.updated_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def list_categories(db: Session) -> list[tuple[str, int]]:
    stmt = (
        select(Knowledge.category, func.count())
        .where(
            Knowledge.category.is_not(None),
            Knowledge.is_archived.is_(False),
            searchable_clause(),
        )
        .group_by(Knowledge.category)
        .order_by(func.count().desc(), Knowledge.category.asc())
    )
    rows = db.execute(stmt).all()
    return [(str(name), int(count)) for name, count in rows if name]


def _apply_parsed(item: Knowledge, content: str, *, fallback_title: str) -> None:
    parsed = markdown_service.parse_markdown(content, fallback_title=fallback_title)
    # 手动指定标题时，解析只更新正文衍生字段；创建流程由调用方决定是否覆盖 title
    item.markdown_content = content
    item.plain_text = parsed["plain_text"]
    item.outline = parsed["outline"]
    item.word_count = parsed["word_count"]
    item.reading_minutes = parsed["reading_minutes"]


def create_knowledge(db: Session, payload: KnowledgeCreate) -> Knowledge:
    content = payload.markdown_content or ""
    parsed = markdown_service.parse_markdown(content, fallback_title=payload.title)
    item = Knowledge(
        title=payload.title,
        summary=payload.summary,
        markdown_content=content,
        plain_text=parsed["plain_text"],
        category=payload.category,
        is_favorite=payload.is_favorite,
        is_important=payload.is_important,
        source_type=KnowledgeSource.MANUAL.value,
        outline=parsed["outline"],
        word_count=parsed["word_count"],
        reading_minutes=parsed["reading_minutes"],
        extra_meta=payload.metadata or {},
    )
    db.add(item)
    db.commit()
    try:
        from app.nexusmind.services import embedding_service

        embedding_service.upsert_embedding(db, item.id)
    except Exception:  # noqa: BLE001
        pass
    return get_knowledge(db, item.id)


def create_chat_draft(
    db: Session,
    *,
    title: str,
    markdown_content: str,
    summary: str | None,
    category: str | None,
    conversation_id: str,
    conversation_title: str | None = None,
) -> Knowledge:
    """Learning-mode notes. Not searchable until confirm_import."""
    content = markdown_content or ""
    parsed = markdown_service.parse_markdown(content, fallback_title=title)
    item = Knowledge(
        title=title[:255],
        summary=summary,
        markdown_content=content,
        plain_text=parsed["plain_text"],
        category=category or "学习",
        source_type=CHAT_DRAFT,
        source_filename=conversation_source_filename(conversation_id),
        outline=parsed["outline"],
        word_count=parsed["word_count"],
        reading_minutes=parsed["reading_minutes"],
        extra_meta={
            "pending_import": True,
            "conversation_id": conversation_id,
            "conversation_title": conversation_title or "",
        },
    )
    db.add(item)
    db.commit()
    return get_knowledge(db, item.id)


def list_for_conversation(db: Session, conversation_id: str) -> list[Knowledge]:
    return list(
        db.scalars(
            select(Knowledge).where(
                Knowledge.source_filename
                == conversation_source_filename(conversation_id)
            )
        ).all()
    )


def confirm_import(db: Session, knowledge_id: str) -> Knowledge:
    item = get_knowledge(db, knowledge_id)
    if item.source_type != CHAT_DRAFT:
        raise ValidationError("只有待导入草稿才能确认入库")
    item.source_type = KnowledgeSource.CHAT.value
    meta = dict(item.extra_meta or {})
    meta["pending_import"] = False
    item.extra_meta = meta
    db.commit()
    try:
        from app.nexusmind.services import embedding_service

        embedding_service.upsert_embedding(db, item.id)
    except Exception:  # noqa: BLE001
        pass
    return get_knowledge(db, item.id)


def update_knowledge(
    db: Session, knowledge_id: str, payload: KnowledgeUpdate
) -> Knowledge:
    item = get_knowledge(db, knowledge_id)
    data = payload.model_dump(exclude_unset=True)

    if "metadata" in data:
        item.extra_meta = data.pop("metadata") or {}

    content_changed = "markdown_content" in data
    title_hint = data.get("title") or item.title

    for field, value in data.items():
        if field == "markdown_content":
            continue
        setattr(item, field, value)

    if content_changed:
        _apply_parsed(item, data["markdown_content"] or "", fallback_title=title_hint)

    db.commit()
    try:
        from app.nexusmind.services import embedding_service

        embedding_service.upsert_embedding(db, item.id)
    except Exception:  # noqa: BLE001
        pass
    return get_knowledge(db, item.id)


def delete_knowledge(db: Session, knowledge_id: str) -> None:
    item = get_knowledge(db, knowledge_id)
    kid = item.id
    try:
        from app.nexusmind.services import embedding_service

        embedding_service.delete_embedding(db, kid)
    except Exception:  # noqa: BLE001
        pass
    db.delete(item)
    db.commit()
    attachment_service.delete_knowledge_files(kid)


def toggle_flag(db: Session, knowledge_id: str, field: str) -> Knowledge:
    if field not in {"is_favorite", "is_important", "is_archived"}:
        raise ValidationError(f"不支持的标记字段: {field}")
    item = get_knowledge(db, knowledge_id)
    setattr(item, field, not bool(getattr(item, field)))
    db.commit()
    return get_knowledge(db, item.id)


async def _read_limited(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    data = await upload.read()
    if len(data) > max_bytes:
        raise ValidationError(f"{label}超过大小限制")
    if not data:
        raise ValidationError(f"{label}内容为空")
    return data


async def import_markdown(
    db: Session,
    *,
    markdown_file: UploadFile,
    archive_file: UploadFile | None = None,
    category: str | None = None,
    title: str | None = None,
) -> tuple[Knowledge, int, list[str]]:
    """导入 .md，可选附带附件 zip。

    返回：(knowledge, imported_attachment_count, warnings)
    """
    md_name = markdown_file.filename or "import.md"
    if not md_name.lower().endswith(".md"):
        raise ValidationError("请上传 .md 文件")

    raw = await _read_limited(markdown_file, settings.max_markdown_bytes, "Markdown 文件")
    # utf-8-sig 会自动剥掉 BOM，避免首行标题解析失败
    content = raw.decode("utf-8-sig", errors="replace")

    fallback = markdown_service.guess_title_from_filename(md_name)
    parsed = markdown_service.parse_markdown(content, fallback_title=fallback)
    resolved_title = (title or "").strip() or parsed["title"]

    source_type = (
        KnowledgeSource.ARCHIVE.value if archive_file is not None else KnowledgeSource.IMPORT.value
    )

    item = Knowledge(
        title=resolved_title[:255],
        summary=None,
        markdown_content=content,
        plain_text=parsed["plain_text"],
        category=(category.strip() if category else None) or None,
        source_type=source_type,
        source_filename=md_name[:255],
        outline=parsed["outline"],
        word_count=parsed["word_count"],
        reading_minutes=parsed["reading_minutes"],
        extra_meta={"imported": True},
    )
    db.add(item)
    db.flush()

    imported = 0
    warnings: list[str] = []

    if archive_file is not None:
        imported, warnings = await _import_zip_attachments(db, item, archive_file)

    db.commit()
    return get_knowledge(db, item.id), imported, warnings


async def _import_zip_attachments(
    db: Session,
    knowledge: Knowledge,
    archive_file: UploadFile,
) -> tuple[int, list[str]]:
    zip_name = archive_file.filename or "attachments.zip"
    if not zip_name.lower().endswith(".zip"):
        raise ValidationError("附件包仅支持 .zip")

    data = await _read_limited(archive_file, settings.max_attachment_bytes, "附件压缩包")
    warnings: list[str] = []
    imported = 0

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                # 跳过 macOS 元数据与隐藏文件
                name = info.filename.replace("\\", "/")
                base = name.rsplit("/", 1)[-1]
                if not base or base.startswith(".") or name.startswith("__MACOSX/"):
                    continue
                if info.file_size > settings.max_attachment_bytes:
                    warnings.append(f"跳过过大文件: {base}")
                    continue
                try:
                    payload = zf.read(info)
                    attachment_service.save_bytes(
                        db,
                        knowledge,
                        filename=base,
                        data=payload,
                        commit=False,
                    )
                    imported += 1
                except ValidationError as exc:
                    warnings.append(f"{base}: {getattr(exc, 'detail', None) or exc.message}")
                except Exception as exc:  # noqa: BLE001 - 导入时尽量容错
                    warnings.append(f"{base}: 导入失败 ({exc})")
    except zipfile.BadZipFile as exc:
        raise ValidationError("无效的 zip 文件") from exc

    return imported, warnings


def to_summary_dict(item: Knowledge) -> dict[str, Any]:
    """组装列表项额外字段。"""
    return {
        "attachment_count": len(item.attachments or []),
    }
