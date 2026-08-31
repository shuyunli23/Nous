"""Serve generated export files and chat uploads."""

from __future__ import annotations

import re

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/files", tags=["files"])

_SAFE_NAME = re.compile(r"^[\w\u4e00-\u9fff.\-]+$")

_MEDIA_BY_SUFFIX = {
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".html": "text/html",
    ".htm": "text/html",
    ".svg": "image/svg+xml",
    ".xml": "application/xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


def _safe_file(folder: str, filename: str) -> FileResponse:
    if not _SAFE_NAME.match(filename) or ".." in filename or "/" in filename:
        raise ValidationError("Invalid filename.")
    path = settings.resolve_path(folder) / filename
    if not path.is_file():
        raise NotFoundError(f"File '{filename}' not found.")
    media = "application/octet-stream"
    lower = filename.lower()
    for suffix, mime in _MEDIA_BY_SUFFIX.items():
        if lower.endswith(suffix):
            media = mime
            break
    # HTML briefings and SVG diagrams must render in the browser, not download.
    if media.startswith("text/html"):
        return FileResponse(
            path,
            media_type="text/html; charset=utf-8",
            content_disposition_type="inline",
        )
    if media.startswith("image/svg"):
        return FileResponse(
            path,
            media_type="image/svg+xml; charset=utf-8",
            content_disposition_type="inline",
        )
    return FileResponse(path, filename=filename, media_type=media)


@router.get(
    "/exports/{filename}",
    summary="Download a generated export file",
)
async def download_export(filename: str) -> FileResponse:
    return _safe_file("./data/exports", filename)


@router.get(
    "/uploads/{filename}",
    summary="Download a chat-uploaded file",
)
async def download_upload(filename: str) -> FileResponse:
    return _safe_file("./data/uploads", filename)
