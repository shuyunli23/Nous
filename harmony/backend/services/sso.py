"""One-time host tickets so Nous can open Harmony without a password."""

from __future__ import annotations

import ipaddress
import os
import socket
import time
import uuid
from dataclasses import dataclass

TICKET_TTL_SECONDS = 60
FRONTEND_PORT = os.getenv("NOUS_FRONTEND_PORT", "5173")
BACKEND_PORTS = {"8000", "8001"}


@dataclass
class _Ticket:
    expires_at: float


_tickets: dict[str, _Ticket] = {}


def issue_host_ticket() -> str:
    _purge()
    ticket = uuid.uuid4().hex
    _tickets[ticket] = _Ticket(expires_at=time.time() + TICKET_TTL_SECONDS)
    return ticket


def consume_host_ticket(ticket: str) -> bool:
    """Accept a host ticket until it expires.

    React StrictMode can redeem the same ticket twice in development, so we
    do not delete it on first use.
    """
    _purge()
    key = (ticket or "").strip()
    return key in _tickets


def _purge() -> None:
    now = time.time()
    stale = [key for key, item in _tickets.items() if item.expires_at < now]
    for key in stale:
        _tickets.pop(key, None)


def _usable_private_ipv4(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if not isinstance(addr, ipaddress.IPv4Address):
        return False
    if addr.is_loopback or addr.is_link_local:
        return False
    # Clash TUN / benchmark range — not reachable by guests on the LAN.
    if addr in ipaddress.ip_network("198.18.0.0/15"):
        return False
    return addr.is_private


def lan_ipv4() -> str:
    found: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if _usable_private_ipv4(ip):
                found.append(ip)
    except OSError:
        pass

    def rank(ip: str) -> tuple[int, str]:
        if ip.startswith("192.168."):
            return (0, ip)
        if ip.startswith("10."):
            return (1, ip)
        return (2, ip)

    if found:
        return sorted(set(found), key=rank)[0]

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if _usable_private_ipv4(ip):
            return ip
    except OSError:
        pass
    return "127.0.0.1"


def public_harmony_url(*, host_header: str, scheme: str) -> str:
    """URL other people on the LAN should open. Always /harmony/, never Nous."""
    host = (host_header or "127.0.0.1").split(",")[0].strip()
    hostname = host.split(":")[0]
    port = host.split(":", 1)[1] if ":" in host else ""
    loopback = hostname in {"127.0.0.1", "localhost", "::1"} or hostname.startswith("127.")
    if loopback:
        hostname = lan_ipv4()
        if port in {"", *BACKEND_PORTS}:
            port = FRONTEND_PORT
    elif port in BACKEND_PORTS:
        port = FRONTEND_PORT
    port_part = f":{port}" if port else ""
    proto = (scheme or "http").split(",")[0].strip() or "http"
    return f"{proto}://{hostname}{port_part}/harmony/"
