"""Mount Harmony Music Player routes onto the Nous FastAPI app."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, FastAPI

from app.core.logging import get_logger

logger = get_logger(__name__)

HARMONY_BACKEND = Path(__file__).resolve().parents[2] / "harmony" / "backend"

_mounted = False


def harmony_backend_dir() -> Path:
    return HARMONY_BACKEND


def ensure_harmony_path() -> bool:
    if not HARMONY_BACKEND.is_dir():
        return False
    root = str(HARMONY_BACKEND)
    if root not in sys.path:
        sys.path.insert(0, root)
    return True


def mount_harmony(app: FastAPI) -> bool:
    """Include Harmony /api/* routers. Safe to call once at import."""
    global _mounted
    if _mounted:
        return True
    if not ensure_harmony_path():
        logger.warning("harmony_missing", path=str(HARMONY_BACKEND))
        return False

    from routes import (  # type: ignore[import-not-found]
        admin_router,
        auth_router,
        history_router,
        music_router,
        playlists_router,
        ratings_router,
        requests_router,
    )

    extra = APIRouter()

    @extra.get("/api/ping")
    async def harmony_ping() -> dict[str, str]:
        return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

    @extra.get("/api/stats")
    async def harmony_stats() -> dict[str, int]:
        from models import Playlist, SessionLocal, Track  # type: ignore[import-not-found]

        db = SessionLocal()
        try:
            return {
                "total_tracks": db.query(Track).count(),
                "total_playlists": db.query(Playlist).count(),
            }
        finally:
            db.close()

    app.include_router(auth_router)
    app.include_router(music_router)
    app.include_router(playlists_router)
    app.include_router(requests_router)
    app.include_router(admin_router)
    app.include_router(history_router)
    app.include_router(ratings_router)
    app.include_router(extra)
    _mounted = True
    # Reload watch: Harmony lyrics routes live under harmony/backend.
    logger.info("harmony_mounted", backend=str(HARMONY_BACKEND))
    return True


def init_harmony() -> None:
    if not ensure_harmony_path():
        return
    from bootstrap import init_database as init_harmony_db  # type: ignore[import-not-found]

    # Tables + admin on the request thread; library scan is a daemon thread.
    init_harmony_db()
