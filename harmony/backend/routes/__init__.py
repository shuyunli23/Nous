from .auth import router as auth_router
from .music import router as music_router
from .playlists import router as playlists_router
from .requests import router as requests_router
from .admin import router as admin_router
from .history import router as history_router
from .ratings import router as ratings_router

__all__ = [
    "auth_router",
    "music_router", 
    "playlists_router",
    "requests_router",
    "admin_router",
    "history_router",
    "ratings_router"
]