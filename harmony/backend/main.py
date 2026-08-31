"""
Harmony Music Player - Backend API
FastAPI + SQLAlchemy + SQLite + Real File Storage
"""

from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import MUSIC_DIR, DATABASE_PATH
from bootstrap import init_database
from routes import auth_router, music_router, playlists_router, requests_router, admin_router, history_router, ratings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle handler"""
    print("🎵 Harmony Music Player starting...")
    print(f"📁 Music directory: {MUSIC_DIR}")
    print(f"💾 Database: {DATABASE_PATH}")
    init_database()
    yield
    print("👋 Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Harmony Music Player",
    version="2.3.0",
    description="A modern music player API with user management, playlists, play history, and track ratings",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(music_router)
app.include_router(playlists_router)
app.include_router(requests_router)
app.include_router(admin_router)
app.include_router(history_router)
app.include_router(ratings_router)


# Health check endpoints
@app.get("/api/ping")
async def ping():
    """Health check"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/stats")
async def public_stats():
    """Public stats endpoint"""
    from models import Track, Playlist, SessionLocal
    
    db = SessionLocal()
    try:
        return {
            "total_tracks": db.query(Track).count(),
            "total_playlists": db.query(Playlist).count(),
        }
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
