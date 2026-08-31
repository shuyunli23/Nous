"""
Database models for Harmony Music Player
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint, Index, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(String(50), primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    playlists = relationship("Playlist", back_populates="owner", cascade="all, delete-orphan")
    requests = relationship("MusicRequest", back_populates="user", cascade="all, delete-orphan")
    play_history = relationship("PlayHistory", back_populates="user", cascade="all, delete-orphan")


class Track(Base):
    __tablename__ = "tracks"
    
    id = Column(String(50), primary_key=True)
    title = Column(String(255), nullable=False, index=True)
    artist = Column(String(255), nullable=False, index=True)
    album = Column(String(255))
    duration = Column(Integer, default=0)
    file_path = Column(String(500), nullable=False)
    cover_path = Column(String(500))
    lyrics_text = Column(Text)
    lyrics_format = Column(String(20))  # plain | lrc
    lyrics_source = Column(String(20))  # embedded | sidecar | upload
    play_count = Column(Integer, default=0)
    popularity_score = Column(Integer, default=0, index=True)  # likes - dislikes
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('title', 'artist', name='uix_title_artist'),
        Index('idx_title_artist', 'title', 'artist'),
        Index('idx_popularity', 'popularity_score'),
    )


class TrackRating(Base):
    """User ratings for tracks (like/dislike)"""
    __tablename__ = "track_ratings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    track_id = Column(String(50), ForeignKey("tracks.id"), nullable=False, index=True)
    rating = Column(Integer, default=0, nullable=False) 
    count_today = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", backref="ratings")
    track = relationship("Track", backref="ratings")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'track_id', name='uix_user_track_rating'),
        Index('idx_user_track', 'user_id', 'track_id'),
        Index('idx_rating_updated', 'user_id', 'updated_at'),
    )


class Playlist(Base):
    __tablename__ = "playlists"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    owner_id = Column(String(50), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    owner = relationship("User", back_populates="playlists")
    items = relationship("PlaylistItem", back_populates="playlist", cascade="all, delete-orphan", order_by="PlaylistItem.position")


class PlaylistItem(Base):
    __tablename__ = "playlist_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    playlist_id = Column(String(50), ForeignKey("playlists.id"), nullable=False)
    track_id = Column(String(50), ForeignKey("tracks.id"), nullable=False)
    position = Column(Integer, default=0)
    
    playlist = relationship("Playlist", back_populates="items")
    track = relationship("Track")


class MusicRequest(Base):
    __tablename__ = "music_requests"
    
    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), ForeignKey("users.id"), nullable=False)
    music_name = Column(String(255), nullable=False)
    artist_name = Column(String(255))
    notes = Column(Text)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    
    user = relationship("User", back_populates="requests")


class PlayHistory(Base):
    """Play history for tracking user's recently played tracks"""
    __tablename__ = "play_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    track_id = Column(String(50), ForeignKey("tracks.id"), nullable=False)
    played_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    user = relationship("User", back_populates="play_history")
    track = relationship("Track")
    
    __table_args__ = (
        Index('idx_user_played_at', 'user_id', 'played_at'),
    )


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_tables():
    """Create all tables and add columns introduced after first install."""
    Base.metadata.create_all(bind=engine)
    _ensure_track_lyrics_columns()


def _ensure_track_lyrics_columns() -> None:
    inspector = inspect(engine)
    if "tracks" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("tracks")}
    additions = []
    if "lyrics_text" not in existing:
        additions.append("ALTER TABLE tracks ADD COLUMN lyrics_text TEXT")
    if "lyrics_format" not in existing:
        additions.append("ALTER TABLE tracks ADD COLUMN lyrics_format VARCHAR(20)")
    if "lyrics_source" not in existing:
        additions.append("ALTER TABLE tracks ADD COLUMN lyrics_source VARCHAR(20)")
    if not additions:
        return
    with engine.begin() as conn:
        for sql in additions:
            conn.execute(text(sql))
