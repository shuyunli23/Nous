"""
Music request routes
"""
import uuid
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models import (
    User, MusicRequest, get_db,
    MusicRequestCreate, MusicRequestResponse
)
from services import get_current_user, require_admin

router = APIRouter(prefix="/api/requests", tags=["Requests"])


@router.get("", response_model=List[MusicRequestResponse])
async def list_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List music requests"""
    if current_user.role == "admin":
        requests = db.query(MusicRequest).order_by(MusicRequest.created_at.desc()).all()
    else:
        requests = db.query(MusicRequest).filter(
            MusicRequest.user_id == current_user.id
        ).order_by(MusicRequest.created_at.desc()).all()
    
    return [MusicRequestResponse(
        id=r.id, user_id=r.user_id, username=r.user.username,
        music_name=r.music_name, artist_name=r.artist_name,
        notes=r.notes, status=r.status, created_at=r.created_at
    ) for r in requests]


@router.post("", response_model=MusicRequestResponse)
async def create_request(
    req: MusicRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit music request"""
    if current_user.role == "admin":
        raise HTTPException(status_code=400, detail="Admins cannot submit requests")
    
    music_request = MusicRequest(
        id=f"req-{uuid.uuid4().hex[:8]}",
        user_id=current_user.id,
        music_name=req.music_name,
        artist_name=req.artist_name,
        notes=req.notes
    )
    db.add(music_request)
    db.commit()
    db.refresh(music_request)
    
    return MusicRequestResponse(
        id=music_request.id, user_id=music_request.user_id,
        username=current_user.username, music_name=music_request.music_name,
        artist_name=music_request.artist_name, notes=music_request.notes,
        status=music_request.status, created_at=music_request.created_at
    )


@router.post("/{request_id}/process")
async def process_request(
    request_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Mark request as processed (Admin only)"""
    request = db.query(MusicRequest).filter(MusicRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    request.status = "processed"
    request.processed_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Request processed"}


@router.delete("/{request_id}")
async def delete_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete request"""
    request = db.query(MusicRequest).filter(MusicRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if current_user.role != "admin" and request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if request.status != "processed":
        raise HTTPException(status_code=400, detail="Can only delete processed requests")
    
    db.delete(request)
    db.commit()
    return {"message": "Request deleted"}
