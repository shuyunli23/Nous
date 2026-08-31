"""
Play history routes
"""
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models import User, Track, PlayHistory, get_db, TrackResponse, PlayHistoryResponse
from services import get_current_user

router = APIRouter(prefix="/api/history", tags=["History"])

# Maximum history records to keep per user
MAX_HISTORY_RECORDS = 100


@router.get("", response_model=List[PlayHistoryResponse])
async def get_play_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=100)
):
    """Get user's play history (most recent first)"""
    history = db.query(PlayHistory).filter(
        PlayHistory.user_id == current_user.id
    ).order_by(desc(PlayHistory.played_at)).limit(limit).all()
    
    result = []
    for h in history:
        if h.track:  # Make sure track still exists
            result.append(PlayHistoryResponse(
                id=h.id,
                track=TrackResponse(
                    id=h.track.id,
                    title=h.track.title,
                    artist=h.track.artist,
                    album=h.track.album,
                    duration=h.track.duration,
                    play_count=h.track.play_count,
                    file_path=h.track.file_path,
                    cover_path=h.track.cover_path,
                    created_at=h.track.created_at
                ),
                played_at=h.played_at
            ))
    
    return result


@router.post("/{track_id}")
async def add_to_history(
    track_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add track to user's play history and increment play count"""
    # Check if track exists
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    # ✅ Always increment play_count when a track is played
    track.play_count += 1
    
    # Check if this track already exists in user's history
    existing_history = db.query(PlayHistory).filter(
        PlayHistory.user_id == current_user.id,
        PlayHistory.track_id == track_id
    ).first()
    
    if existing_history:
        # Update the played_at time instead of creating a new record
        existing_history.played_at = datetime.utcnow()
        db.commit()
        return {"message": "History updated", "play_count": track.play_count}
    
    # Add new history record
    history = PlayHistory(
        user_id=current_user.id,
        track_id=track_id,
        played_at=datetime.utcnow()
    )
    db.add(history)
    db.commit()
    
    # Clean up old records if exceeded limit
    history_count = db.query(PlayHistory).filter(
        PlayHistory.user_id == current_user.id
    ).count()
    
    if history_count > MAX_HISTORY_RECORDS:
        # Delete oldest records
        oldest_records = db.query(PlayHistory).filter(
            PlayHistory.user_id == current_user.id
        ).order_by(PlayHistory.played_at).limit(history_count - MAX_HISTORY_RECORDS).all()
        
        for record in oldest_records:
            db.delete(record)
        db.commit()
    
    return {"message": "Added to history", "play_count": track.play_count}


@router.delete("")
async def clear_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Clear user's play history"""
    db.query(PlayHistory).filter(PlayHistory.user_id == current_user.id).delete()
    db.commit()
    return {"message": "History cleared"}


@router.delete("/{history_id}")
async def delete_history_item(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a specific history item"""
    history = db.query(PlayHistory).filter(
        PlayHistory.id == history_id,
        PlayHistory.user_id == current_user.id
    ).first()
    
    if not history:
        raise HTTPException(status_code=404, detail="History item not found")
    
    db.delete(history)
    db.commit()
    return {"message": "History item deleted"}