"""
Admin routes for user management
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models import User, Track, Playlist, MusicRequest, get_db, UserCreate, UserResponse
from services import require_admin, hash_password

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class PasswordResetRequest(BaseModel):
    """Schema for password reset request"""
    new_password: str = Field(..., min_length=4, description="New password (minimum 4 characters)")


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """List all users (Admin only)"""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserResponse(
        id=u.id, username=u.username, role=u.role, created_at=u.created_at
    ) for u in users]


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create new user (Admin only)"""
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    user = User(
        id=f"user-{uuid.uuid4().hex[:8]}",
        username=user_data.username,
        password_hash=hash_password(user_data.password),
        role="user"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id, username=user.username, role=user.role, created_at=user.created_at
    )


@router.put("/users/{user_id}/password")
async def reset_user_password(
    user_id: str,
    password_data: PasswordResetRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Reset user password (Admin only)
    
    Note: Passwords are securely hashed and cannot be viewed.
    This endpoint allows admins to set a new password for any non-admin user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot reset admin password through this endpoint")
    
    # Hash and update the new password
    user.password_hash = hash_password(password_data.new_password)
    db.commit()
    
    return {"message": "Password reset successfully"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete user (Admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin account")
    
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


@router.get("/stats")
async def get_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get system statistics (Admin only)"""
    return {
        "total_tracks": db.query(Track).count(),
        "total_users": db.query(User).count(),
        "total_playlists": db.query(Playlist).count(),
        "pending_requests": db.query(MusicRequest).filter(MusicRequest.status == "pending").count()
    }