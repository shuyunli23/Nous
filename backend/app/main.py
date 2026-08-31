"""FastAPI application entrypoint."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger, request_id_ctx
from app.database.init_db import init_database
from app.database.session import dispose_engine
from app.harmony_host import init_harmony, mount_harmony
from app.harmony_owner import is_nous_owner
from app.llm.provider_store import resolve_llm
from app.nexusmind.db.session import init_db as init_nexusmind_db

configure_logging()
logger = get_logger(__name__)


GUEST_ALLOWED_API_V1 = {
    "/api/v1/harmony/access",
    "/api/v1/auth/unlock",
}


class NousOwnerGateMiddleware:
    """Guests on the LAN may use Harmony APIs only — not the rest of Nous."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = (scope.get("path") or "").rstrip("/") or "/"
        if path.startswith("/api/v1") and path not in GUEST_ALLOWED_API_V1:
            request = Request(scope, receive)
            if not is_nous_owner(request):
                response = JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "owner_only",
                            "message": (
                                "Unlock Nous with the admin password, "
                                "or open /harmony/ for music."
                            ),
                        }
                    },
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


class RequestContextMiddleware:
    """Request-id + access log without buffering the response body.

    Starlette's ``@app.middleware("http")`` (BaseHTTPMiddleware) reads the
    entire body before sending. That would freeze SSE on /chat/stream until
    the agent turn finished.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = MutableHeaders(scope=scope)
        request_id = headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status") or 500)
                out_headers = MutableHeaders(scope=message)
                out_headers["X-Request-Id"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_ctx.reset(token)
            path = scope.get("path") or ""
            if path != "/api/v1/health":
                logger.info(
                    "request",
                    method=scope.get("method"),
                    path=path,
                    status=status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    request_id=request_id,
                )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    llm = resolve_llm()
    logger.info(
        "startup",
        app=settings.app_name,
        environment=settings.environment,
        database=settings.database_url.split("://", 1)[0],
        llm_configured=llm.configured,
        llm_source=llm.source,
        llm_provider=llm.label,
        llm_model=llm.model,
    )
    await init_database()
    init_nexusmind_db()
    init_harmony()
    yield
    await dispose_engine()
    logger.info("shutdown")


app = FastAPI(
    title="Nous",
    description=(
        "Nous — a personal agent workbench that uses tools, imports skill packs, "
        "and compounds experience into reusable Skills."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|(\d{1,3}\.){3}\d{1,3})(:\d+)?"
    if settings.environment == "development"
    else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(NousOwnerGateMiddleware)


register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_prefix)
mount_harmony(app)  # Harmony /api/* alongside Nous /api/v1


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "name": "Nous",
        "tagline": "Personal Agent Workbench",
        "version": "0.2.0",
        "docs": "/docs",
        "api": settings.api_prefix,
    }
