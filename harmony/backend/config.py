"""
Configuration settings for Harmony Music Player
"""
import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_MUSIC = Path(r"F:\202608\Nous\harmony\Music")
MUSIC_DIR = Path(os.getenv("HARMONY_MUSIC_DIR", str(
    _DEFAULT_MUSIC if _DEFAULT_MUSIC.is_dir() else (BASE_DIR / "Music")
)))
DATABASE_PATH = Path(
    os.getenv("HARMONY_DATABASE", str(BASE_DIR.parent / "backend" / "data" / "harmony.db"))
)

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "harmony-music-secret-key-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Admin credentials (Nous host SSO logs in as this account)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Allowed audio formats
ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".aac", ".wma"}

# Ensure music directory exists
MUSIC_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Database URL
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
