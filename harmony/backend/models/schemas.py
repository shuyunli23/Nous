"""
Pydantic schemas for request/response validation
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# Auth schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4)


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Track schemas
class TrackResponse(BaseModel):
    id: str
    title: str
    artist: str
    album: Optional[str] = None
    duration: int
    play_count: int
    popularity_score: int = 0  # likes - dislikes
    file_path: str
    cover_path: Optional[str] = None
    has_lyrics: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True


class LyricsResponse(BaseModel):
    track_id: str
    text: Optional[str] = None
    format: Optional[str] = None  # plain | lrc
    source: Optional[str] = None  # embedded | sidecar | upload
    has_lyrics: bool = False


# Playlist schemas
class PlaylistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class PlaylistResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    track_count: int
    created_at: datetime


class PlaylistDetailResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    tracks: List[TrackResponse]
    created_at: datetime


# Music request schemas
class MusicRequestCreate(BaseModel):
    music_name: str
    artist_name: Optional[str] = None
    notes: Optional[str] = None


class MusicRequestResponse(BaseModel):
    id: str
    user_id: str
    username: str
    music_name: str
    artist_name: Optional[str]
    notes: Optional[str]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Play history schemas
class PlayHistoryResponse(BaseModel):
    id: int
    track: TrackResponse
    played_at: datetime
    
    class Config:
        from_attributes = True


# Rating schemas
class RatingStatusResponse(BaseModel):
    track_id: str
    user_rating: int  # -1, 0, or 1
    daily_ratings_used: int
    daily_ratings_limit: int
    can_rate_today: bool


class RatingResponse(BaseModel):
    message: str
    track_id: str
    new_rating: int
    old_rating: int
    track_popularity: int
    daily_ratings_used: int
    daily_ratings_remaining: int
