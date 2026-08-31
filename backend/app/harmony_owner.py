"""Who may use Nous vs Harmony-only guests.

Nous is personal. Harmony guest accounts may use music only.

Owner is either:
- a loopback client (this machine, no password), or
- a LAN client that unlocked with the admin password (signed cookie).

Vite proxies from the browser, so the backend only trusts X-Forwarded-*
when the TCP peer is loopback — a guest talking to :8000 cannot spoof
their way in.
"""

from __future__ import annotations

import ipaddress

from fastapi import HTTPException, Request, status


def _is_loopback(host: str) -> bool:
    raw = (host or "").split("%", 1)[0].strip().strip("[]")
    if not raw:
        return False
    if raw in {"localhost", "0:0:0:0:0:0:0:1"}:
        return True
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return False
    if addr.is_loopback:
        return True
    mapped = getattr(addr, "ipv4_mapped", None)
    return bool(mapped and mapped.is_loopback)


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else ""
    if _is_loopback(peer):
        forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return peer


def is_nous_owner(request: Request) -> bool:
    if _is_loopback(client_ip(request)):
        return True
    from app.owner_session import COOKIE_NAME, token_is_owner

    return token_is_owner(request.cookies.get(COOKIE_NAME))


def require_nous_owner(request: Request) -> None:
    if not is_nous_owner(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unlock Nous with the admin password, or open /harmony/ for music.",
        )


def request_public_host(request: Request) -> str:
    return (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or "127.0.0.1"
    ).split(",")[0].strip()


def request_public_scheme(request: Request) -> str:
    return (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").split(",")[0].strip()


def public_harmony_url(request: Request) -> str:
    """URL other people on the LAN should open. Always Harmony, never Nous."""
    from app.harmony_host import ensure_harmony_path

    ensure_harmony_path()
    from services.sso import public_harmony_url as build  # type: ignore[import-not-found]

    return build(
        host_header=request_public_host(request),
        scheme=request_public_scheme(request),
    )
