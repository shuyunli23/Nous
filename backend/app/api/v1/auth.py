"""Admin-password unlock so a LAN browser can use Nous."""

from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.core.exceptions import UnauthorizedError
from app.owner_session import passwords_match, set_owner_cookie

router = APIRouter(prefix="/auth", tags=["auth"])


class UnlockIn(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class UnlockOut(BaseModel):
    owner: bool


@router.post("/unlock", response_model=UnlockOut)
async def unlock(body: UnlockIn, response: Response) -> UnlockOut:
    if not passwords_match(body.password):
        raise UnauthorizedError("Wrong password.")
    set_owner_cookie(response)
    return UnlockOut(owner=True)
