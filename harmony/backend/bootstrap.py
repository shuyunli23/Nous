"""Initialize Harmony tables, admin account, and music scan."""

from __future__ import annotations

import threading

from config import ADMIN_PASSWORD, ADMIN_USERNAME, DATABASE_PATH, MUSIC_DIR
from models import SessionLocal, User, init_tables
from services import hash_password, scan_music_directory, verify_password


def init_database(*, scan_in_background: bool = True) -> None:
    """Initialize database and admin account.

    Music scan walks the whole library and must not block Nous startup.
    """
    init_tables()

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                id="admin-001",
                username=ADMIN_USERNAME,
                password_hash=hash_password(ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin)
            db.commit()
            print(f"Harmony admin created: {ADMIN_USERNAME}")
            print(f"Harmony music dir: {MUSIC_DIR}")
            print(f"Harmony database: {DATABASE_PATH}")
        elif not verify_password(ADMIN_PASSWORD, admin.password_hash):
            admin.password_hash = hash_password(ADMIN_PASSWORD)
            db.commit()
            print("Harmony admin password updated from config")
    finally:
        db.close()

    if scan_in_background:
        threading.Thread(
            target=_scan_music_safe, name="harmony-music-scan", daemon=True
        ).start()
        return
    _scan_music_safe()


def _scan_music_safe() -> None:
    db = SessionLocal()
    try:
        scan_music_directory(db)
    except Exception as exc:
        print(f"Harmony music scan failed: {exc}")
    finally:
        db.close()
