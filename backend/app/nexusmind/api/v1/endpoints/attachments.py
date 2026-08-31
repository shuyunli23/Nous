"""附件 API。"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import FileResponse

from app.nexusmind.api.deps import DBSession
from app.nexusmind.schemas.attachment import AttachmentOut
from app.nexusmind.schemas.common import MessageResponse
from app.nexusmind.services import attachment_service, knowledge_service

router = APIRouter(tags=["attachments"])


@router.get(
    "/knowledge/{knowledge_id}/attachments",
    response_model=list[AttachmentOut],
    summary="列出知识附件",
)
def list_attachments(knowledge_id: str, db: DBSession) -> list[AttachmentOut]:
    knowledge_service.get_knowledge(db, knowledge_id)  # 确认知识存在
    items = attachment_service.list_attachments(db, knowledge_id)
    return [AttachmentOut.model_validate(i) for i in items]


@router.post(
    "/knowledge/{knowledge_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="上传附件",
)
async def upload_attachment(
    knowledge_id: str,
    db: DBSession,
    file: UploadFile = File(...),
) -> AttachmentOut:
    knowledge = knowledge_service.get_knowledge(db, knowledge_id)
    item = await attachment_service.save_upload(db, knowledge, file)
    return AttachmentOut.model_validate(item)


@router.get(
    "/attachments/{attachment_id}/download",
    summary="下载附件",
    responses={200: {"content": {"application/octet-stream": {}}}},
)
def download_attachment(attachment_id: str, db: DBSession) -> FileResponse:
    item = attachment_service.get_attachment(db, attachment_id)
    path = attachment_service.absolute_path(item)
    if not path.is_file():
        from app.nexusmind.utils.errors import NotFoundError

        raise NotFoundError("附件文件已丢失")

    # 兼容中文文件名：filename* (RFC 5987)
    quoted = quote(item.filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
    }
    return FileResponse(
        path,
        media_type=item.mime_type or "application/octet-stream",
        filename=item.filename,
        headers=headers,
    )


@router.delete(
    "/attachments/{attachment_id}",
    response_model=MessageResponse,
    summary="删除附件",
)
def delete_attachment(attachment_id: str, db: DBSession) -> MessageResponse:
    attachment_service.delete_attachment(db, attachment_id)
    return MessageResponse(message="附件已删除")
