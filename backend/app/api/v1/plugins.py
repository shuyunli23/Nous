"""Stable plugin install: zip / GitHub URL → Skill Pack tools."""

from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, UploadFile, status
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, SessionDep
from app.core.exceptions import ValidationError
from app.schemas.skill_pack import PackArchiveImportResult, PackArchivePreview
from app.services.pack_service import PackService

router = APIRouter(prefix="/plugins", tags=["plugins"])


class PluginFromUrlRequest(BaseModel):
    url: str = Field(min_length=3, max_length=500)
    grant_permissions: list[str] | None = None
    activate: bool = True
    replace_existing: bool = True


async def _read_upload(file: UploadFile) -> bytes:
    name = (file.filename or "").lower()
    if name and not name.endswith((".zip", ".nouspack", ".nousplugin")):
        raise ValidationError("Upload a .zip, .nouspack, or .nousplugin file.")
    data = await file.read()
    if not data:
        raise ValidationError("Empty upload.")
    return data


@router.post(
    "/preview",
    response_model=PackArchivePreview,
    summary="Validate a plugin zip without installing",
)
async def preview_plugin(
    user: CurrentUser,
    file: UploadFile = File(...),
) -> PackArchivePreview:
    del user
    data = await _read_upload(file)
    return await PackService().preview_bytes(data, origin="zip")


@router.post(
    "/preview-url",
    response_model=PackArchivePreview,
    summary="Fetch and validate a GitHub plugin without installing",
)
async def preview_plugin_url(
    payload: PluginFromUrlRequest,
    user: CurrentUser,
) -> PackArchivePreview:
    del user
    return await PackService().preview_url(payload.url)


@router.post(
    "",
    response_model=PackArchiveImportResult,
    status_code=status.HTTP_201_CREATED,
    summary="Install a plugin zip (nous-plugin/1, nous-pack/2, or dsh-plugin)",
)
async def import_plugin_zip(
    session: SessionDep,
    user: CurrentUser,
    file: UploadFile = File(...),
    grant_permissions: str = Form(default="[]"),
    activate: bool = Form(default=True),
    replace_existing: bool = Form(default=True),
) -> PackArchiveImportResult:
    data = await _read_upload(file)
    try:
        grants = json.loads(grant_permissions) if grant_permissions else []
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "grant_permissions must be a JSON array of strings."
        ) from exc
    if not isinstance(grants, list):
        raise ValidationError("grant_permissions must be a JSON array of strings.")
    svc = PackService(session)
    return await svc.import_bytes(
        user_id=user.id,
        data=data,
        grant_permissions=[str(x) for x in grants],
        activate=activate,
        replace_existing=replace_existing,
        origin="zip",
    )


@router.post(
    "/from-url",
    response_model=PackArchiveImportResult,
    status_code=status.HTTP_201_CREATED,
    summary="Install a plugin from a GitHub repository URL",
)
async def import_plugin_url(
    payload: PluginFromUrlRequest,
    session: SessionDep,
    user: CurrentUser,
) -> PackArchiveImportResult:
    svc = PackService(session)
    return await svc.import_url(
        user_id=user.id,
        url=payload.url,
        grant_permissions=payload.grant_permissions,
        activate=payload.activate,
        replace_existing=payload.replace_existing,
    )
