"""
Track rating routes - Like/Dislike functionality with daily limits
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from models import User, Track, get_db
from models.database import TrackRating
from services import get_current_user

router = APIRouter(prefix="/api/ratings", tags=["Ratings"])

# Daily rating limit per user
DAILY_RATING_LIMIT = 10


def get_today_start() -> datetime:
    """Get the start of today (midnight UTC)"""
    now = datetime.utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def get_user_daily_rating_count(db: Session, user_id: str) -> int:
    """Count how many ratings a user has made today"""
    today_start = get_today_start()
    return db.query(TrackRating).filter(
        TrackRating.user_id == user_id,
        TrackRating.updated_at >= today_start
    ).count()


@router.get("/status/{track_id}")
async def get_rating_status(
    track_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user's rating status for a track and remaining daily ratings"""
    # Check if track exists
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    # Get user's rating for this track
    rating = db.query(TrackRating).filter(
        TrackRating.user_id == current_user.id,
        TrackRating.track_id == track_id
    ).first()
    
    # Get today's rating count
    today_count = get_user_daily_rating_count(db, current_user.id)
    
    # Check if rating was updated today
    can_change_today = True
    if rating and rating.updated_at >= get_today_start():
        # Rating was already changed today, check if user has remaining ratings
        can_change_today = today_count < DAILY_RATING_LIMIT
    
    return {
        "track_id": track_id,
        "user_rating": rating.rating if rating else 0,  # -1, 0, or 1
        "daily_ratings_used": today_count,
        "daily_ratings_limit": DAILY_RATING_LIMIT,
        "can_rate_today": today_count < DAILY_RATING_LIMIT or (rating and rating.updated_at >= get_today_start())
    }


@router.post("/{track_id}")
async def rate_track(
    track_id: str,
    vote: int,  # Expecting 1 for Like, -1 for Dislike
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if vote not in [-1, 1]:
        raise HTTPException(status_code=400, detail="Vote must be 1 or -1")
    
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    rating_record = db.query(TrackRating).filter(
        TrackRating.user_id == current_user.id,
        TrackRating.track_id == track_id
    ).first()
    
    now = datetime.utcnow()
    DAILY_LIMIT_PER_TRACK = 10

    if not rating_record:
        # First time rating this specific song
        rating_record = TrackRating(
            user_id=current_user.id,
            track_id=track_id,
            rating=vote,
            count_today=1,
            updated_at=now
        )
        db.add(rating_record)
    else:
        # Check if 24 hours have passed since the last vote to reset the count
        time_since_last_vote = now - rating_record.updated_at
        if time_since_last_vote > timedelta(hours=24):
            rating_record.count_today = 0
            
        # Check if user reached the limit for this specific song
        if rating_record.count_today >= DAILY_LIMIT_PER_TRACK:
            raise HTTPException(
                status_code=429, 
                detail=f"Daily limit of {DAILY_LIMIT_PER_TRACK} votes reached for this track."
            )
        
        # Accumulate the score and increment the daily count
        rating_record.rating += vote
        rating_record.count_today += 1
        rating_record.updated_at = now

    # Save rating record
    db.commit()
    
    # Recalculate the total popularity_score for the Track
    # (Sum of all ratings from all users)
    total_popularity = db.query(func.sum(TrackRating.rating)).filter(
        TrackRating.track_id == track_id
    ).scalar() or 0
    
    track.popularity_score = total_popularity
    db.commit()
    
    return {
        "track_id": track_id,
        "track_popularity": track.popularity_score,
        "your_total_contribution": rating_record.rating,
        "count_today": rating_record.count_today,
        "remaining_today": DAILY_LIMIT_PER_TRACK - rating_record.count_today
    }


@router.get("/my-ratings")
async def get_my_ratings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all ratings by current user"""
    ratings = db.query(TrackRating).filter(
        TrackRating.user_id == current_user.id
    ).all()
    
    return {
        "ratings": [
            {
                "track_id": r.track_id,
                "rating": r.rating,
                "updated_at": r.updated_at
            }
            for r in ratings
        ],
        "daily_ratings_used": get_user_daily_rating_count(db, current_user.id),
        "daily_ratings_limit": DAILY_RATING_LIMIT
    }


@router.get("/daily-status")
async def get_daily_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user's daily rating status"""
    today_count = get_user_daily_rating_count(db, current_user.id)
    
    return {
        "daily_ratings_used": today_count,
        "daily_ratings_limit": DAILY_RATING_LIMIT,
        "daily_ratings_remaining": DAILY_RATING_LIMIT - today_count,
        "resets_at": (get_today_start() + timedelta(days=1)).isoformat() + "Z"
    }
