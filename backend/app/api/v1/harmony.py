"""Nous-side Harmony entry: owner check, share URL, one-time SSO ticket."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.harmony_host import ensure_harmony_path
from app.harmony_owner import is_nous_owner, public_harmony_url, require_nous_owner

router = APIRouter(prefix="/harmony", tags=["harmony"])


class HarmonyAccessOut(BaseModel):
    owner: bool
    share_url: str


class HarmonySSOOut(BaseModel):
    ticket: str
    redirect: str
    share_url: str


@router.get("/access", response_model=HarmonyAccessOut)
async def harmony_access(request: Request) -> HarmonyAccessOut:
    """Anyone may call this. True after loopback or admin-password unlock."""
    return HarmonyAccessOut(
        owner=is_nous_owner(request),
        share_url=public_harmony_url(request),
    )


@router.post("/sso", response_model=HarmonySSOOut)
async def harmony_sso(request: Request) -> HarmonySSOOut:
    require_nous_owner(request)
    if not ensure_harmony_path():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Harmony is not installed next to Nous.",
        )
    from services.sso import issue_host_ticket  # type: ignore[import-not-found]

    ticket = issue_host_ticket()
    return HarmonySSOOut(
        ticket=ticket,
        redirect=f"/harmony/?sso={ticket}",
        share_url=public_harmony_url(request),
    )
