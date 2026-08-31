"""nous-pack/2 zip archive install endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, UploadFile, status

from app.core.deps import CurrentUser, SessionDep
from app.core.exceptions import ValidationError
from app.schemas.common import OkResponse
from app.schemas.skill_pack import (
    InstalledPackDetail,
    InstalledPackSummary,
    PackArchiveImportResult,
    PackArchivePreview,
    PackStatusPatch,
)
from app.services.pack_service import PackService

router = APIRouter(prefix="/pack-archives", tags=["skill-packs"])


async def _read_upload(file: UploadFile) -> bytes:
    name = (file.filename or "").lower()
    if name and not (name.endswith(".zip") or name.endswith(".nouspack")):
        raise ValidationError("Upload a .zip or .nouspack file.")
    data = await file.read()
    if not data:
        raise ValidationError("Empty upload.")
    return data


@router.post(
    "/preview",
    response_model=PackArchivePreview,
    summary="Validate a nous-pack/2 zip without installing",
)
async def preview_pack_archive(
    user: CurrentUser,
    file: UploadFile = File(...),
) -> PackArchivePreview:
    del user
    data = await _read_upload(file)
    return await PackService().preview_bytes(data)


@router.post(
    "",
    response_model=PackArchiveImportResult,
    status_code=status.HTTP_201_CREATED,
    summary="Install a nous-pack/2 zip (granted permissions enable auto-run tools)",
)
async def import_pack_archive(
    session: SessionDep,
    user: CurrentUser,
    file: UploadFile = File(...),
    grant_permissions: str = Form(
        default="[]",
        description='JSON array of permissions to grant, e.g. ["script.python","network"]',
    ),
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
    )


@router.get(
    "",
    response_model=list[InstalledPackSummary],
    summary="List installed nous-pack/2 archives",
)
async def list_installed_packs(
    session: SessionDep,
    user: CurrentUser,
) -> list[InstalledPackSummary]:
    svc = PackService(session)
    return await svc.list_installed(user_id=user.id)


@router.get(
    "/{pack_row_id}",
    response_model=InstalledPackDetail,
    summary="Installed pack detail",
)
async def get_installed_pack(
    pack_row_id: str,
    session: SessionDep,
    user: CurrentUser,
) -> InstalledPackDetail:
    svc = PackService(session)
    return await svc.get_installed(user_id=user.id, pack_row_id=pack_row_id)


@router.patch(
    "/{pack_row_id}",
    response_model=InstalledPackDetail,
    summary="Enable or disable an installed pack",
)
async def patch_installed_pack(
    pack_row_id: str,
    payload: PackStatusPatch,
    session: SessionDep,
    user: CurrentUser,
) -> InstalledPackDetail:
    svc = PackService(session)
    return await svc.set_status(
        user_id=user.id, pack_row_id=pack_row_id, status=payload.status
    )


@router.delete(
    "/{pack_row_id}",
    response_model=OkResponse,
    summary="Uninstall a pack (removes skills + files)",
)
async def delete_installed_pack(
    pack_row_id: str,
    session: SessionDep,
    user: CurrentUser,
) -> OkResponse:
    svc = PackService(session)
    await svc.uninstall(user_id=user.id, pack_row_id=pack_row_id)
    return OkResponse(ok=True, message="Pack uninstalled.")
