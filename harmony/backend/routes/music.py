"""
Music routes with edit, batch upload, and directory management
Updated to include popularity_score in responses
"""
import re
import uuid
import shutil
import mimetypes
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from config import MUSIC_DIR, ALLOWED_AUDIO_EXTENSIONS
from models import User, Track, PlaylistItem, get_db, TrackResponse, LyricsResponse
from services import (
    get_current_user, require_admin, verify_token,
    scan_music_directory, extract_metadata, extract_cover_art, get_cover_file_path,
    apply_lyrics_to_track, detect_lyrics_format, decode_lyrics_bytes, get_track_file_path,
)

def is_garbled_text(text: str, filename: str) -> bool:
    """
    Check if text contains garbled characters by comparing with filename
    Returns True if text appears to be garbled
    """
    if not text or not filename:
        return False
    
    # Remove file extension from filename
    filename_base = Path(filename).stem
    
    # Check if at least one character from filename exists in the parsed text
    filename_chars = set(filename_base.lower())
    text_chars = set(text.lower())
    
    # Check for common garbled patterns
    garbled_patterns = [
        r'[\x80-\xff]{3,}',  # High-bit characters
        r'[À-ÿ]{3,}',  # Multiple accented characters
    ]
    
    for pattern in garbled_patterns:
        if re.search(pattern, text):
            return True
    
    # If no common characters between filename and text, likely garbled
    common_chars = filename_chars & text_chars
    if len(common_chars) == 0 and len(filename_chars) > 0:
        return True
        
    return False


def sanitize_filename(text: str) -> str:
    """
    Sanitize text to create a safe filename
    """
    if not text:
        return "unknown"
    
    # Remove or replace invalid characters for filesystem
    invalid_chars = r'[<>:"|?*\\/]'
    sanitized = re.sub(invalid_chars, '_', text)
    
    # Remove control characters
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32)
    
    # Trim whitespace and dots
    sanitized = sanitized.strip('. ')
    
    # If empty after sanitization, use default
    if not sanitized:
        sanitized = "unknown"
    
    # Limit length to 200 characters
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    
    return sanitized


router = APIRouter(prefix="/api/music", tags=["Music"])


@router.get("", response_model=List[TrackResponse])
async def list_music(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: Optional[str] = None,
    garbled_only: bool = Query(False, description="Only show tracks with garbled metadata"),  # ADD THIS LINE
    sort_by: str = Query("title", enum=["title", "artist", "play_count", "popularity_score", "created_at"]),
    sort_order: str = Query("asc", enum=["asc", "desc"])
):
    """List all music tracks"""
    query = db.query(Track)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Track.title.ilike(search_term)) | 
            (Track.artist.ilike(search_term)) |
            (Track.album.ilike(search_term))
        )
    
    sort_column = getattr(Track, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    tracks = query.all()
    
    # ADD THIS BLOCK - Filter garbled tracks if requested
    result_tracks = []
    for t in tracks:
        # Check if track has garbled metadata
        filename = Path(t.file_path).name
        is_garbled = (
            is_garbled_text(t.title, filename) or
            is_garbled_text(t.artist, filename)
        )
        
        # Include track based on filter
        if garbled_only:
            if is_garbled:
                result_tracks.append(TrackResponse(
                    id=t.id, title=t.title, artist=t.artist, album=t.album,
                    duration=t.duration, play_count=t.play_count, 
                    popularity_score=t.popularity_score or 0,
                    file_path=t.file_path, cover_path=t.cover_path,
                    has_lyrics=bool(t.lyrics_text),
                    created_at=t.created_at,
                    is_garbled=is_garbled  # Add this field if TrackResponse model supports it
                ))
        else:
            result_tracks.append(TrackResponse(
                id=t.id, title=t.title, artist=t.artist, album=t.album,
                duration=t.duration, play_count=t.play_count, 
                popularity_score=t.popularity_score or 0,
                file_path=t.file_path, cover_path=t.cover_path,
                has_lyrics=bool(t.lyrics_text),
                created_at=t.created_at,
                is_garbled=is_garbled
            ))
    
    return result_tracks


@router.get("/directories")
async def list_directories(
    current_path: str = Query("", description="Path relative to the Music directory"),
    admin: User = Depends(require_admin)
):
    """List directories and files (Admin only)"""
    try:
        # Build full path
        if current_path:
            full_path = MUSIC_DIR / current_path
        else:
            full_path = MUSIC_DIR
        
        # Security check: Make sure the path is within MUSIC_DIR
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(MUSIC_DIR)):
            raise HTTPException(status_code=400, detail="Invalid path")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Directory not found")
        
        # List directory contents
        items = []
        for item in full_path.iterdir():
            if item.name.startswith('.') or item.name == 'covers':
                continue
            
            relative_path = str(item.relative_to(MUSIC_DIR))
            
            if item.is_dir():
                items.append({
                    "name": item.name,
                    "path": relative_path,
                    "type": "directory",
                    "size": 0
                })
            elif item.is_file() and item.suffix.lower() in ALLOWED_AUDIO_EXTENSIONS:
                items.append({
                    "name": item.name,
                    "path": relative_path,
                    "type": "file",
                    "size": item.stat().st_size,
                    "extension": item.suffix.lower()
                })
        
        # Sort: directory first, then by name
        items.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
        
        return {
            "current_path": current_path,
            "parent_path": str(full_path.parent.relative_to(MUSIC_DIR)) if full_path != MUSIC_DIR else None,
            "items": items
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/directories")
async def create_directory(
    path: str = Form("", description="Path relative to the Music directory"),
    name: str = Form(..., description="New directory name"),
    admin: User = Depends(require_admin)
):
    """Create new directory (Admin only)"""
    try:
        # Build full path
        if path:
            base_path = MUSIC_DIR / path
        else:
            base_path = MUSIC_DIR
        
        new_dir = base_path / name
        
        # security check
        new_dir = new_dir.resolve()
        if not str(new_dir).startswith(str(MUSIC_DIR)):
            raise HTTPException(status_code=400, detail="Invalid path")
        
        if new_dir.exists():
            raise HTTPException(status_code=400, detail="Directory already exists")
        
        new_dir.mkdir(parents=True, exist_ok=False)
        
        return {
            "message": "Directory created",
            "path": str(new_dir.relative_to(MUSIC_DIR))
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/directories")
async def delete_directory(
    path: str = Query(..., description="Path relative to the Music directory"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete directory (Admin only)"""
    if not path:
        raise HTTPException(status_code=400, detail="Cannot delete root directory")
    
    try:
        full_path = (MUSIC_DIR / path).resolve()
        
        # Security check
        if not str(full_path).startswith(str(MUSIC_DIR)):
            raise HTTPException(status_code=400, detail="Invalid path")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Directory not found")
        
        if not full_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        # Check if directory contains tracked files and remove them from DB
        for file_path in full_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in ALLOWED_AUDIO_EXTENSIONS:
                relative_path = str(file_path.relative_to(MUSIC_DIR))
                track = db.query(Track).filter(Track.file_path == relative_path).first()
                if track:
                    # Remove from playlists
                    db.query(PlaylistItem).filter(PlaylistItem.track_id == track.id).delete()
                    # Delete cover if exists
                    if track.cover_path:
                        cover_path = MUSIC_DIR / track.cover_path
                        if cover_path.exists():
                            cover_path.unlink()
                    db.delete(track)
        
        db.commit()
        
        # Delete the directory and all its contents
        shutil.rmtree(full_path)
        
        return {"message": "Directory deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/directories/rename")
async def rename_directory(
    path: str = Form(..., description="Current path relative to the Music directory"),
    new_name: str = Form(..., description="New directory name"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Rename directory (Admin only)"""
    if not path:
        raise HTTPException(status_code=400, detail="Cannot rename root directory")
    
    try:
        full_path = (MUSIC_DIR / path).resolve()
        
        # Security check
        if not str(full_path).startswith(str(MUSIC_DIR)):
            raise HTTPException(status_code=400, detail="Invalid path")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Directory not found")
        
        if not full_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        # Build new path
        new_path = full_path.parent / new_name
        
        if new_path.exists():
            raise HTTPException(status_code=400, detail="A directory with this name already exists")
        
        # Update all track paths in database
        old_relative = str(full_path.relative_to(MUSIC_DIR))
        new_relative = str(new_path.relative_to(MUSIC_DIR))
        
        tracks = db.query(Track).filter(Track.file_path.startswith(old_relative + "/")).all()
        for track in tracks:
            track.file_path = track.file_path.replace(old_relative + "/", new_relative + "/", 1)
        
        db.commit()
        
        # Rename the directory
        full_path.rename(new_path)
        
        return {
            "message": "Directory renamed",
            "new_path": new_relative
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files")
async def delete_file(
    path: str = Query(..., description="File path relative to the Music directory"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a music file (Admin only)"""
    if not path:
        raise HTTPException(status_code=400, detail="File path is required")
    
    try:
        full_path = (MUSIC_DIR / path).resolve()
        
        # Security check
        if not str(full_path).startswith(str(MUSIC_DIR)):
            raise HTTPException(status_code=400, detail="Invalid path")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not full_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        # Check if file is tracked in database
        relative_path = str(full_path.relative_to(MUSIC_DIR))
        track = db.query(Track).filter(Track.file_path == relative_path).first()
        
        if track:
            # Remove from playlists
            db.query(PlaylistItem).filter(PlaylistItem.track_id == track.id).delete()
            # Delete cover if exists
            if track.cover_path:
                cover_path = MUSIC_DIR / track.cover_path
                if cover_path.exists():
                    cover_path.unlink()
            db.delete(track)
            db.commit()
        
        # Delete the file
        full_path.unlink()
        
        return {"message": "File deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/files/rename")
async def rename_file(
    path: str = Form(..., description="Current file path relative to the Music directory"),
    new_name: str = Form(..., description="New file name (with extension)"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Rename a music file (Admin only)"""
    if not path:
        raise HTTPException(status_code=400, detail="File path is required")
    
    try:
        full_path = (MUSIC_DIR / path).resolve()
        
        # Security check
        if not str(full_path).startswith(str(MUSIC_DIR)):
            raise HTTPException(status_code=400, detail="Invalid path")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not full_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        # Validate extension
        new_ext = Path(new_name).suffix.lower()
        if new_ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Invalid file extension: {new_ext}")
        
        # Build new path
        new_path = full_path.parent / new_name
        
        if new_path.exists():
            raise HTTPException(status_code=400, detail="A file with this name already exists")
        
        # Update track path in database if exists
        relative_path = str(full_path.relative_to(MUSIC_DIR))
        track = db.query(Track).filter(Track.file_path == relative_path).first()
        
        if track:
            new_relative_path = str(new_path.relative_to(MUSIC_DIR))
            track.file_path = new_relative_path
            db.commit()
        
        # Rename the file
        full_path.rename(new_path)
        
        return {
            "message": "File renamed",
            "new_path": str(new_path.relative_to(MUSIC_DIR))
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-upload")
async def batch_upload_music(
    files: List[UploadFile] = File(...),
    directory: str = Form("", description="target directory"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Batch upload music files and automatically parse metadata (Admin only)"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    results = {
        "success": [],
        "failed": [],
        "duplicate": []
    }
    
    # Determine target directory
    if directory:
        target_dir = MUSIC_DIR / directory
        target_dir.mkdir(parents=True, exist_ok=True)
    else:
        target_dir = MUSIC_DIR
    
    # security check
    target_dir = target_dir.resolve()
    if not str(target_dir).startswith(str(MUSIC_DIR)):
        raise HTTPException(status_code=400, detail="Invalid directory path")
    
    for file in files:
        try:
            ext = Path(file.filename).suffix.lower()
            if ext not in ALLOWED_AUDIO_EXTENSIONS:
                results["failed"].append({
                    "filename": file.filename,
                    "reason": f"Unsupported format: {ext}"
                })
                continue
            
            # Generate track ID
            track_id = f"track-{uuid.uuid4().hex[:8]}"
            
            # save file
            temp_filename = f"temp_{track_id}{ext}"
            temp_path = target_dir / temp_filename
            
            with open(temp_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            # Extract metadata
            metadata = extract_metadata(temp_path)
            
            title = metadata.get("title") or Path(file.filename).stem
            artist = metadata.get("artist") or "Unknown Artist"
            album = metadata.get("album")
            duration = metadata.get("duration", 0)
            
            # Check if it already exists（title + artist）
            existing = db.query(Track).filter(
                Track.title == title,
                Track.artist == artist
            ).first()
            
            if existing:
                temp_path.unlink()  # Delete temporary files
                results["duplicate"].append({
                    "filename": file.filename,
                    "title": title,
                    "artist": artist
                })
                continue
            
            # Generate final file name using sanitize_filename
            safe_title = sanitize_filename(title)
            safe_artist = sanitize_filename(artist)

            if safe_artist.lower() != 'unknown artist':
                safe_filename = f"{safe_artist}-{safe_title}{ext}"
            else:
                safe_filename = f"{safe_title}{ext}"

            final_path = target_dir / safe_filename
            
            # If the file name already exists, add the ID suffix
            counter = 1
            while final_path.exists():
                safe_filename = f"{title}-{artist}-{counter}{ext}".replace("/", "_").replace("\\", "_")
                final_path = target_dir / safe_filename
                counter += 1
            
            # Rename file
            temp_path.rename(final_path)
            
            # Extract cover
            cover_path = None
            if metadata.get("has_cover"):
                covers_dir = MUSIC_DIR / "covers"
                cover_path = extract_cover_art(final_path, covers_dir, track_id)
            
            # Create database records
            relative_path = str(final_path.relative_to(MUSIC_DIR))
            track = Track(
                id=track_id,
                title=title,
                artist=artist,
                album=album,
                file_path=relative_path,
                cover_path=cover_path,
                duration=duration,
                popularity_score=0
            )
            apply_lyrics_to_track(track, final_path)
            db.add(track)
            db.commit()
            db.refresh(track)
            
            results["success"].append({
                "filename": file.filename,
                "track_id": track.id,
                "title": title,
                "artist": artist
            })
            
        except IntegrityError:
            db.rollback()
            if temp_path.exists():
                temp_path.unlink()
            results["duplicate"].append({
                "filename": file.filename,
                "reason": "Duplicate title + artist"
            })
        except Exception as e:
            db.rollback()
            if 'temp_path' in locals() and temp_path.exists():
                temp_path.unlink()
            results["failed"].append({
                "filename": file.filename,
                "reason": str(e)
            })
    
    return results


@router.put("/{track_id}", response_model=TrackResponse)
async def update_track_info(
    track_id: str,
    title: str = Form(...),
    artist: str = Form(...),
    album: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update music information (Admin only)"""
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    # Check if this will cause duplication (exclude yourself)
    existing = db.query(Track).filter(
        Track.title == title,
        Track.artist == artist,
        Track.id != track_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"A track with title '{title}' and artist '{artist}' already exists"
        )
    
    try:
        track.title = title
        track.artist = artist
        track.album = album
        db.commit()
        db.refresh(track)
        
        return TrackResponse(
            id=track.id, title=track.title, artist=track.artist, album=track.album,
            duration=track.duration, play_count=track.play_count,
            popularity_score=track.popularity_score or 0,
            file_path=track.file_path, cover_path=track.cover_path, created_at=track.created_at
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate title + artist combination")


@router.get("/top", response_model=List[TrackResponse])
async def get_top_tracks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get top tracks sorted by popularity (likes - dislikes) first, then by play count.
    This is used for the Trending section.
    """
    # Sort by popularity_score DESC, then play_count DESC
    tracks = db.query(Track).order_by(
        Track.popularity_score.desc(),
        Track.play_count.desc()
    ).limit(limit).all()
    
    return [TrackResponse(
        id=t.id, title=t.title, artist=t.artist, album=t.album,
        duration=t.duration, play_count=t.play_count,
        popularity_score=t.popularity_score or 0,
        file_path=t.file_path, cover_path=t.cover_path,
        has_lyrics=bool(t.lyrics_text),
        created_at=t.created_at
    ) for t in tracks]


def _lyrics_payload(track: Track) -> LyricsResponse:
    text = (track.lyrics_text or "").strip() or None
    return LyricsResponse(
        track_id=track.id,
        text=text,
        format=track.lyrics_format if text else None,
        source=track.lyrics_source if text else None,
        has_lyrics=bool(text),
    )


@router.get("/{track_id}/lyrics", response_model=LyricsResponse)
async def get_track_lyrics(
    track_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return stored lyrics, filling from the audio file or a sidecar if missing."""
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if not track.lyrics_text:
        path = get_track_file_path(track)
        if path.exists() and apply_lyrics_to_track(track, path):
            db.commit()
    return _lyrics_payload(track)


@router.post("/{track_id}/lyrics", response_model=LyricsResponse)
async def upload_track_lyrics(
    track_id: str,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import lyrics from a .lrc/.txt file or pasted text."""
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    body = (text or "").strip()
    if file and file.filename:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in {".lrc", ".txt", ""}:
            raise HTTPException(status_code=400, detail="Only .lrc or .txt lyrics files are allowed")
        raw = await file.read()
        if len(raw) > 512_000:
            raise HTTPException(status_code=400, detail="Lyrics file is too large")
        body = decode_lyrics_bytes(raw).strip()

    if not body:
        raise HTTPException(status_code=400, detail="No lyrics content provided")

    track.lyrics_text = body
    track.lyrics_format = detect_lyrics_format(body)
    track.lyrics_source = "upload"
    db.commit()
    db.refresh(track)
    return _lyrics_payload(track)


@router.delete("/{track_id}/lyrics")
async def delete_track_lyrics(
    track_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Clear imported/extracted lyrics (Admin only)."""
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    track.lyrics_text = None
    track.lyrics_format = None
    track.lyrics_source = None
    db.commit()
    return {"message": "Lyrics removed"}


@router.post("/{track_id}/cover")
async def upload_track_cover(
    track_id: str,
    cover: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Upload or replace cover art for a track (Admin only)"""
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    # Validate file type
    allowed_image_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if cover.content_type not in allowed_image_types:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP, and GIF images are allowed")
    
    try:
        from PIL import Image
        import io
        
        # Read image data
        image_data = await cover.read()
        img = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if needed
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
        covers_dir = MUSIC_DIR / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)
        cover_path = covers_dir / f"{track_id}.jpg"
        img.save(cover_path, "JPEG", quality=90, optimize=True)
        
        # Delete old cover if it was a different file
        if track.cover_path and track.cover_path != f"covers/{track_id}.jpg":
            old_cover = MUSIC_DIR / track.cover_path
            if old_cover.exists():
                old_cover.unlink()
        
        # Update database
        track.cover_path = f"covers/{track_id}.jpg"
        db.commit()
        
        return {"message": "Cover uploaded successfully", "cover_path": track.cover_path}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")


@router.get("/{track_id}/cover")
async def get_track_cover(
    track_id: str,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get track cover art"""
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    
    try:
        payload = verify_token(token)
        user = db.query(User).filter(User.id == payload.get("sub")).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    cover_path = get_cover_file_path(track)
    if not cover_path or not cover_path.exists():
        raise HTTPException(status_code=404, detail="Cover art not found")
    
    return FileResponse(
        path=cover_path,
        media_type="image/jpeg",
        filename=f"{track_id}.jpg"
    )


@router.get("/{track_id}/stream")
async def stream_track(
    track_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Stream music file with Range request support for seeking"""
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    
    try:
        payload = verify_token(token)
        user = db.query(User).filter(User.id == payload.get("sub")).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    file_path = MUSIC_DIR / track.file_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Music file not found")
    
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        mime_type = "audio/mpeg"
    
    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")
    
    if range_header:
        # Parse Range header: "bytes=start-end"
        range_spec = range_header.replace("bytes=", "")
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        
        # Clamp values
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        content_length = end - start + 1
        
        def iter_file():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data
        
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": mime_type,
        }
        
        return StreamingResponse(
            iter_file(),
            status_code=206,
            headers=headers,
            media_type=mime_type
        )
    else:
        # No Range header - return full file with Accept-Ranges hint
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        }
        return FileResponse(
            path=file_path,
            media_type=mime_type,
            filename=file_path.name,
            headers=headers
        )


@router.delete("/{track_id}")
async def delete_track(
    track_id: str,
    delete_file: bool = Query(True),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete track (Admin only)"""
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    db.query(PlaylistItem).filter(PlaylistItem.track_id == track_id).delete()
    
    if delete_file:
        file_path = MUSIC_DIR / track.file_path
        if file_path.exists():
            file_path.unlink()
        
        if track.cover_path:
            cover_path = MUSIC_DIR / track.cover_path
            if cover_path.exists():
                cover_path.unlink()
    
    db.delete(track)
    db.commit()
    
    return {"message": "Track deleted"}


@router.post("/scan")
async def scan_music(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Scan music catalog (Admin only)"""
    count = scan_music_directory(db)
    total = db.query(Track).count()
    return {"message": "Scan complete", "added": count, "total_tracks": total}


@router.put("/files/move")
async def move_file(
    source_path: str = Form(..., description="Source file path relative to Music directory"),
    destination_path: str = Form(..., description="Destination directory path"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Move a music file to a different directory (Admin only)"""
    if not source_path:
        raise HTTPException(status_code=400, detail="Source path is required")
    
    try:
        source_full = (MUSIC_DIR / source_path).resolve()
        
        # Security check
        if not str(source_full).startswith(str(MUSIC_DIR)):
            raise HTTPException(status_code=400, detail="Invalid source path")
        
        if not source_full.exists():
            raise HTTPException(status_code=404, detail="Source file not found")
        
        if not source_full.is_file():
            raise HTTPException(status_code=400, detail="Source is not a file")
        
        # Build destination path
        if destination_path:
            dest_dir = (MUSIC_DIR / destination_path).resolve()
        else:
            dest_dir = MUSIC_DIR
        
        # Security check
        if not str(dest_dir).startswith(str(MUSIC_DIR)):
            raise HTTPException(status_code=400, detail="Invalid destination path")
        
        if not dest_dir.exists():
            raise HTTPException(status_code=404, detail="Destination directory not found")
        
        if not dest_dir.is_dir():
            raise HTTPException(status_code=400, detail="Destination is not a directory")
        
        # Build new file path
        new_file_path = dest_dir / source_full.name
        
        if new_file_path.exists():
            raise HTTPException(status_code=400, detail="A file with this name already exists in the destination")
        
        # Update database if file is tracked
        relative_source = str(source_full.relative_to(MUSIC_DIR))
        track = db.query(Track).filter(Track.file_path == relative_source).first()
        
        if track:
            new_relative = str(new_file_path.relative_to(MUSIC_DIR))
            track.file_path = new_relative
            db.commit()
        
        # Move the file
        shutil.move(str(source_full), str(new_file_path))
        
        return {
            "message": "File moved successfully",
            "new_path": str(new_file_path.relative_to(MUSIC_DIR))
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/directories/move")
async def move_directory(
    source_path: str = Form(..., description="Source directory path"),
    destination_path: str = Form(..., description="Destination directory path"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Move a directory to a different location (Admin only)"""
    if not source_path:
        raise HTTPException(status_code=400, detail="Cannot move root directory")
    
    try:
        source_full = (MUSIC_DIR / source_path).resolve()
        
        # Security check
        if not str(source_full).startswith(str(MUSIC_DIR)):
            raise HTTPException(status_code=400, detail="Invalid source path")
        
        if not source_full.exists():
            raise HTTPException(status_code=404, detail="Source directory not found")
        
        if not source_full.is_dir():
            raise HTTPException(status_code=400, detail="Source is not a directory")
        
        # Build destination path
        if destination_path:
            dest_dir = (MUSIC_DIR / destination_path).resolve()
        else:
            dest_dir = MUSIC_DIR
        
        # Security check
        if not str(dest_dir).startswith(str(MUSIC_DIR)):
            raise HTTPException(status_code=400, detail="Invalid destination path")
        
        if not dest_dir.exists():
            raise HTTPException(status_code=404, detail="Destination directory not found")
        
        # Check if destination is a subdirectory of source
        if str(dest_dir).startswith(str(source_full)):
            raise HTTPException(status_code=400, detail="Cannot move directory into itself")
        
        # Build new directory path
        new_dir_path = dest_dir / source_full.name
        
        if new_dir_path.exists():
            raise HTTPException(status_code=400, detail="A directory with this name already exists in the destination")
        
        # Update all track paths in database
        old_relative = str(source_full.relative_to(MUSIC_DIR))
        new_relative = str(new_dir_path.relative_to(MUSIC_DIR))
        
        tracks = db.query(Track).filter(Track.file_path.startswith(old_relative + "/")).all()
        for track in tracks:
            track.file_path = track.file_path.replace(old_relative + "/", new_relative + "/", 1)
        
        db.commit()
        
        # Move the directory
        shutil.move(str(source_full), str(new_dir_path))
        
        return {
            "message": "Directory moved successfully",
            "new_path": new_relative
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
