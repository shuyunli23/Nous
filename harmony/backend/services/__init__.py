from .auth import (
    hash_password, verify_password, create_token, verify_token,
    get_current_user, require_admin, security
)
from .music import (
    scan_music_directory,
    get_track_file_path,
    generate_safe_filename,
    extract_metadata,
    extract_cover_art,
    get_cover_file_path,
    apply_lyrics_to_track,
    detect_lyrics_format,
    decode_lyrics_bytes,
    discover_lyrics,
)

__all__ = [
    "hash_password", "verify_password", "create_token", "verify_token",
    "get_current_user", "require_admin", "security",
    "scan_music_directory", "get_track_file_path", "generate_safe_filename",
    "extract_metadata", "extract_cover_art", "get_cover_file_path",
    "apply_lyrics_to_track", "detect_lyrics_format", "decode_lyrics_bytes",
    "discover_lyrics",
]
