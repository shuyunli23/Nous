from starlette.requests import Request

from app.harmony_owner import client_ip, is_nous_owner
from app.owner_session import COOKIE_NAME, issue_owner_token, passwords_match


def test_passwords_match(monkeypatch) -> None:
    monkeypatch.setattr("app.owner_session.owner_password", lambda: "secret-admin")
    assert passwords_match("secret-admin")
    assert not passwords_match("wrong")
    assert not passwords_match("")


def _request(
    client: str,
    forwarded: str | None = None,
    cookie: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode()))
    if cookie is not None:
        headers.append((b"cookie", cookie.encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
        "client": (client, 12345),
        "server": ("127.0.0.1", 8000),
    }
    return Request(scope)


def test_loopback_is_owner() -> None:
    assert is_nous_owner(_request("127.0.0.1"))
    assert is_nous_owner(_request("::1"))


def test_lan_guest_is_not_owner() -> None:
    assert not is_nous_owner(_request("192.168.1.23"))


def test_proxy_trusts_forwarded_only_from_loopback() -> None:
    assert is_nous_owner(_request("127.0.0.1", "127.0.0.1"))
    assert not is_nous_owner(_request("127.0.0.1", "192.168.1.23"))
    # Direct hit on :8000 from the LAN cannot spoof X-Forwarded-For.
    assert client_ip(_request("192.168.1.23", "127.0.0.1")) == "192.168.1.23"
    assert not is_nous_owner(_request("192.168.1.23", "127.0.0.1"))


def test_admin_password_unlocks_lan() -> None:
    token = issue_owner_token()
    assert is_nous_owner(_request("192.168.1.23", cookie=f"{COOKIE_NAME}={token}"))


def test_bad_cookie_does_not_unlock() -> None:
    assert not is_nous_owner(
        _request("192.168.1.23", cookie=f"{COOKIE_NAME}=not-a-token")
    )
