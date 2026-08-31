"""
Music file management service with metadata extraction
Updated to handle unique constraint (title + artist)
"""
import re
import uuid
import io
from pathlib import Path
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, APIC
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from PIL import Image

from config import MUSIC_DIR, ALLOWED_AUDIO_EXTENSIONS
from models import Track

_LRC_TAG = re.compile(r"\[\d{1,2}:\d{2}(?:[.:]\d{1,3})?\]")


def extract_metadata(file_path: Path) -> dict:
    """
    Extract metadata from audio file using mutagen
    Returns dict with: title, artist, album, duration, has_cover
    """
    metadata = {
        "title": None,
        "artist": None,
        "album": None,
        "duration": 0,
        "has_cover": False
    }
    
    try:
        audio = MutagenFile(file_path)
        if audio is None:
            return metadata
        
        # Get duration
        if hasattr(audio.info, 'length'):
            metadata["duration"] = int(audio.info.length)
        
        # Extract tags based on file type
        if hasattr(audio, 'tags') and audio.tags:
            tags = audio.tags
            
            # MP3 (ID3 tags)
            if hasattr(tags, 'getall'):
                metadata["title"] = tags.getall('TIT2')[0].text[0] if tags.getall('TIT2') else None
                metadata["artist"] = tags.getall('TPE1')[0].text[0] if tags.getall('TPE1') else None
                metadata["album"] = tags.getall('TALB')[0].text[0] if tags.getall('TALB') else None
                metadata["has_cover"] = bool(tags.getall('APIC'))
            
            # MP4/M4A
            elif isinstance(audio, MP4):
                metadata["title"] = tags.get('\xa9nam', [None])[0]
                metadata["artist"] = tags.get('\xa9ART', [None])[0]
                metadata["album"] = tags.get('\xa9alb', [None])[0]
                metadata["has_cover"] = bool(tags.get('covr'))
            
            # FLAC/OGG (Vorbis comments)
            else:
                metadata["title"] = tags.get('title', [None])[0] if 'title' in tags else None
                metadata["artist"] = tags.get('artist', [None])[0] if 'artist' in tags else None
                metadata["album"] = tags.get('album', [None])[0] if 'album' in tags else None
                
                if isinstance(audio, FLAC):
                    metadata["has_cover"] = bool(audio.pictures)
        
        # Fallback to filename if no title
        if not metadata["title"]:
            stem = file_path.stem
            if "-" in stem:
                parts = stem.split("-", 1)
                metadata["title"] = parts[0].strip()
                if not metadata["artist"]:
                    metadata["artist"] = parts[1].strip()
            else:
                metadata["title"] = stem
        
        # Default artist if missing
        if not metadata["artist"]:
            metadata["artist"] = "Unknown Artist"
            
    except Exception as e:
        print(f"Error extracting metadata from {file_path.name}: {e}")
        # Fallback to filename parsing
        stem = file_path.stem
        if "-" in stem:
            parts = stem.split("-", 1)
            metadata["title"] = parts[0].strip()
            metadata["artist"] = parts[1].strip()
        else:
            metadata["title"] = stem
            metadata["artist"] = "Unknown Artist"
    
    return metadata


def extract_cover_art(file_path: Path, output_dir: Path, track_id: str) -> Optional[str]:
    """
    Extract cover art from audio file and save as image
    Returns relative path to saved cover image or None
    """
    try:
        audio = MutagenFile(file_path)
        if audio is None:
            return None
        
        image_data = None
        
        # MP3 with ID3 tags
        if hasattr(audio, 'tags') and hasattr(audio.tags, 'getall'):
            apic_frames = audio.tags.getall('APIC')
            if apic_frames:
                image_data = apic_frames[0].data
        
        # MP4/M4A
        elif isinstance(audio, MP4):
            if 'covr' in audio.tags:
                image_data = bytes(audio.tags['covr'][0])
        
        # FLAC
        elif isinstance(audio, FLAC):
            if audio.pictures:
                image_data = audio.pictures[0].data
        
        if image_data:
            # Save cover image
            output_dir.mkdir(parents=True, exist_ok=True)
            cover_path = output_dir / f"{track_id}.jpg"
            
            # Convert to JPEG if needed and resize
            try:
                img = Image.open(io.BytesIO(image_data))
                # Convert to RGB if needed (for PNG with transparency)
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                
                # Resize to reasonable size (max 800x800)
                max_size = (800, 800)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Save as JPEG
                img.save(cover_path, "JPEG", quality=90, optimize=True)
                
                return f"covers/{track_id}.jpg"
            except Exception as e:
                print(f"Error processing cover image: {e}")
                return None
        
    except Exception as e:
        print(f"Error extracting cover from {file_path.name}: {e}")
    
    return None


def detect_lyrics_format(text: str) -> str:
    if text and len(_LRC_TAG.findall(text)) >= 2:
        return "lrc"
    return "plain"


def decode_lyrics_bytes(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    for encoding in ("utf-8", "gb18030", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _tag_to_text(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value is None:
        return None
    if isinstance(value, bytes):
        return decode_lyrics_bytes(value).strip() or None
    text = str(value).strip()
    return text or None


def _sylt_to_lrc(frame) -> Optional[str]:
    entries = getattr(frame, "text", None) or []
    if not entries:
        return None
    lines = []
    for item in entries:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            word, time_ms = item[0], item[1]
        else:
            continue
        try:
            total = float(time_ms) / 1000.0
        except (TypeError, ValueError):
            continue
        minutes = int(total // 60)
        seconds = total % 60
        lines.append(f"[{minutes:02d}:{seconds:05.2f}]{word}")
    return "\n".join(lines) if lines else None


def read_sidecar_lyrics(audio_path: Path) -> Optional[dict]:
    for suffix in (".lrc", ".LRC", ".txt", ".TXT"):
        sidecar = audio_path.with_suffix(suffix)
        if not sidecar.is_file():
            continue
        try:
            text = decode_lyrics_bytes(sidecar.read_bytes()).strip()
        except OSError:
            continue
        if not text:
            continue
        return {
            "text": text,
            "format": detect_lyrics_format(text),
            "source": "sidecar",
        }
    return None


def extract_embedded_lyrics(file_path: Path) -> Optional[dict]:
    try:
        audio = MutagenFile(file_path)
        if audio is None or not getattr(audio, "tags", None):
            return None
        tags = audio.tags
        text = None
        fmt = None

        if hasattr(tags, "getall"):
            sylt_frames = tags.getall("SYLT")
            if sylt_frames:
                converted = _sylt_to_lrc(sylt_frames[0])
                if converted:
                    text, fmt = converted, "lrc"
            if not text:
                uslt_frames = tags.getall("USLT")
                if uslt_frames:
                    text = _tag_to_text(getattr(uslt_frames[0], "text", None))
        elif isinstance(audio, MP4):
            text = _tag_to_text(tags.get("\xa9lyr"))
        else:
            for key in ("LYRICS", "lyrics", "UNSYNCEDLYRICS", "unsyncedlyrics"):
                if key in tags:
                    text = _tag_to_text(tags.get(key))
                    if text:
                        break

        if not text:
            return None
        return {
            "text": text,
            "format": fmt or detect_lyrics_format(text),
            "source": "embedded",
        }
    except Exception as exc:
        print(f"Error extracting lyrics from {file_path.name}: {exc}")
        return None


def discover_lyrics(file_path: Path) -> Optional[dict]:
    """Sidecar .lrc/.txt wins over tags inside the audio file."""
    return read_sidecar_lyrics(file_path) or extract_embedded_lyrics(file_path)


def apply_lyrics_to_track(
    track: Track,
    file_path: Path,
    *,
    overwrite_upload: bool = False,
) -> bool:
    """Fill lyrics from sidecar or tags. Does not replace a user upload unless asked."""
    if track.lyrics_text and track.lyrics_source == "upload" and not overwrite_upload:
        return False
    if track.lyrics_text and not overwrite_upload:
        return False
    found = discover_lyrics(file_path)
    if not found:
        return False
    track.lyrics_text = found["text"]
    track.lyrics_format = found["format"]
    track.lyrics_source = found["source"]
    return True


def scan_music_directory(db: Session) -> int:
    """
    Scan music directory and add unregistered files with metadata
    Respects unique constraint on title + artist
    """
    added_count = 0
    skipped_count = 0
    covers_dir = MUSIC_DIR / "covers"
    
    for file_path in MUSIC_DIR.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in ALLOWED_AUDIO_EXTENSIONS:
            relative_path = str(file_path.relative_to(MUSIC_DIR))
            
            # Check if file path already exists
            existing = db.query(Track).filter(Track.file_path == relative_path).first()
            
            if not existing:
                # Extract metadata
                metadata = extract_metadata(file_path)
                
                title = metadata["title"] or file_path.stem
                artist = metadata["artist"] or "Unknown Artist"
                
                # Check if title + artist combination already exists
                duplicate = db.query(Track).filter(
                    Track.title == title,
                    Track.artist == artist
                ).first()
                
                if duplicate:
                    print(f"Skipped duplicate: {title} - {artist} (from {file_path.name})")
                    skipped_count += 1
                    continue
                
                track_id = f"track-{uuid.uuid4().hex[:8]}"
                
                # Extract cover art if available
                cover_path = None
                if metadata["has_cover"]:
                    cover_path = extract_cover_art(file_path, covers_dir, track_id)
                
                try:
                    track = Track(
                        id=track_id,
                        title=title,
                        artist=artist,
                        album=metadata["album"],
                        file_path=relative_path,
                        cover_path=cover_path,
                        duration=metadata["duration"]
                    )
                    apply_lyrics_to_track(track, file_path)
                    db.add(track)
                    db.commit()
                    added_count += 1
                except IntegrityError:
                    db.rollback()
                    print(f"Skipped duplicate (DB constraint): {title} - {artist}")
                    skipped_count += 1
            else:
                # Update existing track if metadata is missing
                updated = False
                metadata = extract_metadata(file_path)
                
                if existing.duration == 0 and metadata["duration"] > 0:
                    existing.duration = metadata["duration"]
                    updated = True
                
                if not existing.album and metadata["album"]:
                    existing.album = metadata["album"]
                    updated = True
                
                if not existing.cover_path and metadata["has_cover"]:
                    cover_path = extract_cover_art(file_path, covers_dir, existing.id)
                    if cover_path:
                        existing.cover_path = cover_path
                        updated = True

                if apply_lyrics_to_track(existing, file_path):
                    updated = True
                
                if updated:
                    db.commit()
    
    if added_count > 0 or skipped_count > 0:
        print(f"Harmony scan complete: added {added_count} tracks, skipped {skipped_count} duplicates")
    
    return added_count


def get_track_file_path(track: Track) -> Path:
    """Get the full file path for a track"""
    return MUSIC_DIR / track.file_path


def get_cover_file_path(track: Track) -> Optional[Path]:
    """Get the full file path for track cover art"""
    if not track.cover_path:
        return None
    return MUSIC_DIR / track.cover_path


def generate_safe_filename(title: str, artist: str, extension: str) -> str:
    """Generate a safe filename for uploaded music"""
    safe_name = f"{title}-{artist}{extension}".replace("/", "_").replace("\\", "_")
    return safe_name