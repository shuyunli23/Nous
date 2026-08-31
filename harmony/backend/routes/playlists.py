"""
Playlist routes
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models import (
    User, Track, Playlist, PlaylistItem, get_db,
    PlaylistCreate, PlaylistResponse, TrackResponse
)
from services import get_current_user

router = APIRouter(prefix="/api/playlists", tags=["Playlists"])


@router.get("", response_model=List[PlaylistResponse])
async def list_playlists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List user's playlists"""
    playlists = db.query(Playlist).filter(Playlist.owner_id == current_user.id).all()
    return [PlaylistResponse(
        id=p.id, name=p.name, owner_id=p.owner_id,
        track_count=len(p.items), created_at=p.created_at
    ) for p in playlists]


@router.post("", response_model=PlaylistResponse)
async def create_playlist(
    playlist: PlaylistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new playlist"""
    new_playlist = Playlist(
        id=f"playlist-{uuid.uuid4().hex[:8]}",
        name=playlist.name,
        owner_id=current_user.id
    )
    db.add(new_playlist)
    db.commit()
    db.refresh(new_playlist)
    
    return PlaylistResponse(
        id=new_playlist.id, name=new_playlist.name, owner_id=new_playlist.owner_id,
        track_count=0, created_at=new_playlist.created_at
    )


@router.get("/{playlist_id}")
async def get_playlist(
    playlist_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get playlist with tracks"""
    playlist = db.query(Playlist).filter(
        Playlist.id == playlist_id,
        Playlist.owner_id == current_user.id
    ).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    tracks = []
    for item in playlist.items:
        if item.track:
            tracks.append(TrackResponse(
                id=item.track.id, title=item.track.title, artist=item.track.artist,
                album=item.track.album, duration=item.track.duration,
                play_count=item.track.play_count, file_path=item.track.file_path,
                cover_path=item.track.cover_path, created_at=item.track.created_at
            ))
    
    return {
        "id": playlist.id,
        "name": playlist.name,
        "owner_id": playlist.owner_id,
        "tracks": tracks,
        "created_at": playlist.created_at
    }


@router.post("/{playlist_id}/tracks/{track_id}")
async def add_track_to_playlist(
    playlist_id: str,
    track_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add track to playlist"""
    playlist = db.query(Playlist).filter(
        Playlist.id == playlist_id,
        Playlist.owner_id == current_user.id
    ).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    existing = db.query(PlaylistItem).filter(
        PlaylistItem.playlist_id == playlist_id,
        PlaylistItem.track_id == track_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Track already in playlist")
    
    max_pos = db.query(PlaylistItem).filter(PlaylistItem.playlist_id == playlist_id).count()
    
    item = PlaylistItem(playlist_id=playlist_id, track_id=track_id, position=max_pos)
    db.add(item)
    db.commit()
    
    return {"message": "Track added to playlist"}


@router.delete("/{playlist_id}/tracks/{track_id}")
async def remove_track_from_playlist(
    playlist_id: str,
    track_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove track from playlist"""
    playlist = db.query(Playlist).filter(
        Playlist.id == playlist_id,
        Playlist.owner_id == current_user.id
    ).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    item = db.query(PlaylistItem).filter(
        PlaylistItem.playlist_id == playlist_id,
        PlaylistItem.track_id == track_id
    ).first()
    if item:
        db.delete(item)
        db.commit()
    
    return {"message": "Track removed from playlist"}


@router.put("/{playlist_id}/reorder")
async def reorder_playlist_tracks(
    playlist_id: str,
    track_ids: List[str],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reorder tracks in playlist"""
    playlist = db.query(Playlist).filter(
        Playlist.id == playlist_id,
        Playlist.owner_id == current_user.id
    ).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    for position, track_id in enumerate(track_ids):
        item = db.query(PlaylistItem).filter(
            PlaylistItem.playlist_id == playlist_id,
            PlaylistItem.track_id == track_id
        ).first()
        if item:
            item.position = position
    
    db.commit()
    return {"message": "Playlist reordered"}


@router.delete("/{playlist_id}")
async def delete_playlist(
    playlist_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete playlist"""
    playlist = db.query(Playlist).filter(
        Playlist.id == playlist_id,
        Playlist.owner_id == current_user.id
    ).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    db.delete(playlist)
    db.commit()
    return {"message": "Playlist deleted"}