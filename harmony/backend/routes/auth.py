"""
Authentication routes
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import ADMIN_USERNAME
from models import User, get_db, LoginRequest, UserResponse, TokenResponse
from services import verify_password, hash_password, create_token, get_current_user, require_admin
from services.sso import consume_host_ticket, public_harmony_url

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class ChangeUsernameRequest(BaseModel):
    """Schema for username change request"""
    new_username: str = Field(..., min_length=3, max_length=50)
    current_password: str = Field(..., description="Current password for verification")


class ChangePasswordRequest(BaseModel):
    """Schema for password change request"""
    current_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(..., min_length=4, description="New password")


class SSORequest(BaseModel):
    ticket: str


@router.post("/sso", response_model=TokenResponse)
async def sso_login(req: SSORequest, db: Session = Depends(get_db)):
    """Consume a one-time host ticket issued by Nous. Logs in as Harmony admin."""
    if not consume_host_ticket(req.ticket):
        raise HTTPException(status_code=401, detail="Invalid or expired host ticket")

    user = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    if not user:
        raise HTTPException(status_code=500, detail="Admin account missing")

    token = create_token(user.id, user.role)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            created_at=user.created_at,
        ),
    )


@router.get("/share-url")
async def guest_share_url(
    request: Request,
    _admin: User = Depends(require_admin),
):
    """LAN URL to give other people. Harmony only — they must log in."""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return {"url": public_harmony_url(host_header=host, scheme=proto)}


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login with username and password"""
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    token = create_token(user.id, user.role)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            created_at=user.created_at
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        created_at=current_user.created_at
    )


@router.put("/profile/username", response_model=UserResponse)
async def change_username(
    req: ChangeUsernameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Change current user's username
    Requires current password for verification
    Admin users cannot change their username through this endpoint
    """
    # Admin cannot change username through this endpoint
    if current_user.role == "admin":
        raise HTTPException(
            status_code=403, 
            detail="Admin username is managed through configuration"
        )
    
    # Verify current password
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    # Check if new username already exists
    existing = db.query(User).filter(
        User.username == req.new_username,
        User.id != current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Update username
    current_user.username = req.new_username
    db.commit()
    db.refresh(current_user)
    
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        created_at=current_user.created_at
    )


@router.put("/profile/password")
async def change_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Change current user's password
    Requires current password for verification
    Admin users cannot change their password through this endpoint
    """
    # Admin cannot change password through this endpoint
    if current_user.role == "admin":
        raise HTTPException(
            status_code=403, 
            detail="Admin password is managed through configuration"
        )
    
    # Verify current password
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    # Update password
    current_user.password_hash = hash_password(req.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}