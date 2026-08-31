"""附件存储与元数据管理。

文件落盘：`settings.attachments_dir / <knowledge_id> / <uuid><ext>`
数据库只保存相对路径与元信息。
"""

from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nexusmind.config import settings
from app.nexusmind.db.base import new_uuid
from app.nexusmind.models import Attachment, Knowledge
from app.nexusmind.utils.errors import NotFoundError, ValidationError


def _safe_ext(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    # 只保留常见安全字符，防止奇怪后缀
    if ext and all(c.isalnum() or c in {".", "_", "-"} for c in ext):
        return ext[:32]
    return ""


def _validate_upload(filename: str, size: int) -> str:
    if not filename or not filename.strip():
        raise ValidationError("附件文件名无效")
    if size <= 0:
        raise ValidationError("附件内容为空")
    if size > settings.max_attachment_bytes:
        raise ValidationError(
            f"附件超过大小限制（{settings.MAX_ATTACHMENT_SIZE_MB} MB）"
        )
    ext = _safe_ext(filename)
    allowed = settings.ALLOWED_ATTACHMENT_EXTS
    if allowed and ext and ext not in allowed:
        raise ValidationError(f"不支持的附件类型: {ext or '(无扩展名)'}")
    if allowed and not ext:
        raise ValidationError("附件缺少扩展名")
    return ext


def knowledge_dir(knowledge_id: str) -> Path:
    path = settings.attachments_dir / knowledge_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def absolute_path(attachment: Attachment) -> Path:
    return settings.attachments_dir / attachment.relative_path


def get_attachment(db: Session, attachment_id: str) -> Attachment:
    item = db.get(Attachment, attachment_id)
    if item is None:
        raise NotFoundError("附件不存在")
    return item


def list_attachments(db: Session, knowledge_id: str) -> list[Attachment]:
    stmt = (
        select(Attachment)
        .where(Attachment.knowledge_id == knowledge_id)
        .order_by(Attachment.created_time.asc())
    )
    return list(db.scalars(stmt).all())


async def save_upload(
    db: Session,
    knowledge: Knowledge,
    upload: UploadFile,
    *,
    commit: bool = True,
) -> Attachment:
    """接收 UploadFile 并落盘。"""
    raw_name = upload.filename or "unnamed.bin"
    data = await upload.read()
    return save_bytes(
        db,
        knowledge,
        filename=raw_name,
        data=data,
        content_type=upload.content_type,
        commit=commit,
    )


def save_bytes(
    db: Session,
    knowledge: Knowledge,
    *,
    filename: str,
    data: bytes,
    content_type: str | None = None,
    commit: bool = True,
) -> Attachment:
    """把字节流保存为附件。"""
    ext = _validate_upload(filename, len(data))
    stored_name = f"{new_uuid()}{ext}"
    relative = f"{knowledge.id}/{stored_name}"
    dest = settings.attachments_dir / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    # 清理路径穿越：只用 basename
    safe_filename = Path(filename).name[:255] or stored_name

    attachment = Attachment(
        knowledge_id=knowledge.id,
        filename=safe_filename,
        stored_name=stored_name,
        relative_path=relative.replace("\\", "/"),
        extension=ext,
        mime_type=mime,
        size_bytes=len(data),
    )
    db.add(attachment)
    if commit:
        db.commit()
        db.refresh(attachment)
    else:
        db.flush()
        db.refresh(attachment)
    return attachment


def delete_attachment(db: Session, attachment_id: str, *, commit: bool = True) -> None:
    attachment = get_attachment(db, attachment_id)
    path = absolute_path(attachment)
    db.delete(attachment)
    if commit:
        db.commit()
    else:
        db.flush()
    # 文件删除失败不回滚元数据删除，避免孤儿记录；尽力清理即可
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


def delete_knowledge_files(knowledge_id: str) -> None:
    """删除某条知识下的整个附件目录。"""
    folder = settings.attachments_dir / knowledge_id
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
