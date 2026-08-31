"""Signed cookie that lets a LAN client into Nous after the admin password.

Loopback is still owner without a password. Harmony guest accounts are not
accepted here — only the Nous / Harmony admin password.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Response

from app.core.config import settings

COOKIE_NAME = "nous_owner"
_ALGORITHM = "HS256"


def owner_password() -> str:
    """Dedicated password, else the Harmony admin password."""
    dedicated = (settings.nous_owner_password or "").strip()
    if dedicated:
        return dedicated
    return os.getenv("ADMIN_PASSWORD", "admin123")


def session_secret() -> str:
    dedicated = (settings.nous_session_secret or "").strip()
    if dedicated:
        return dedicated
    return os.getenv("SECRET_KEY", "nous-owner-session-secret")


def _password_stamp(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()[:16]


def passwords_match(given: str) -> bool:
    expected = hashlib.sha256(owner_password().encode("utf-8")).digest()
    got = hashlib.sha256((given or "").encode("utf-8")).digest()
    return secrets.compare_digest(expected, got)


def issue_owner_token() -> str:
    pwd = owner_password()
    payload = {
        "sub": "nous-owner",
        "pwd": _password_stamp(pwd),
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.nous_session_days),
    }
    return jwt.encode(payload, session_secret(), algorithm=_ALGORITHM)


def token_is_owner(token: str | None) -> bool:
    if not token:
        return False
    try:
        payload = jwt.decode(token, session_secret(), algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return False
    if payload.get("sub") != "nous-owner":
        return False
    return payload.get("pwd") == _password_stamp(owner_password())


def cookie_max_age() -> int:
    return max(1, settings.nous_session_days) * 86400


def set_owner_cookie(response: Response, token: str | None = None) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token or issue_owner_token(),
        max_age=cookie_max_age(),
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def clear_owner_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")
