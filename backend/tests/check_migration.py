"""Verify the Alembic migration matches the ORM models.

Runs upgrade head -> compares tables against Base.metadata -> downgrade base.
Uses a throwaway SQLite file so it never touches dev data.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND / "data" / "migrationtest.db"
DB_URL = "sqlite+aiosqlite:///./data/migrationtest.db"

def _python() -> str:
    """Interpreter that has alembic installed.

    Invoked as ``-m alembic`` rather than the ``alembic.exe`` console script:
    the shim exits 1 with an empty stdout/stderr when its recorded interpreter
    path has moved, which turned every migration bug into a bare
    ``[FAIL] alembic upgrade head``. It is also the only form that works off
    Windows.
    """
    for candidate in (
        BACKEND / ".venv" / "Scripts" / "python.exe",
        BACKEND / ".venv" / "bin" / "python",
    ):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def tables() -> set[str]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {row[0] for row in rows if not row[0].startswith("sqlite_")}


def alembic(*args: str) -> None:
    env = {**os.environ, "DATABASE_URL": DB_URL, "PYTHONPATH": str(BACKEND)}
    result = subprocess.run(
        [_python(), "-m", "alembic", *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        print(f"[FAIL] alembic {' '.join(args)}")
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])
        sys.exit(1)


def main() -> None:
    DB_PATH.unlink(missing_ok=True)

    alembic("upgrade", "head")
    created = tables()
    print(f"[OK] upgrade head  tables={sorted(created)}")

    # Compare against the ORM metadata, minus alembic's own bookkeeping table.
    os.environ["DATABASE_URL"] = DB_URL
    sys.path.insert(0, str(BACKEND))
    from app.database.base import Base
    from app.database import models  # noqa: F401

    expected = set(Base.metadata.tables)
    missing = expected - created
    extra = created - expected - {"alembic_version"}
    assert not missing, f"migration missing tables: {missing}"
    assert not extra, f"migration created unexpected tables: {extra}"
    print(f"[OK] migration matches ORM models  ({len(expected)} tables)")

    # Spot-check the seq column that fixed message ordering.
    with sqlite3.connect(DB_PATH) as conn:
        cols = {
            row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()
        }
    assert "seq" in cols, f"messages.seq missing: {sorted(cols)}"
    print("[OK] messages.seq present in migration")

    alembic("downgrade", "base")
    remaining = tables() - {"alembic_version"}
    assert not remaining, f"downgrade left tables behind: {remaining}"
    print("[OK] downgrade base  all tables dropped")

    # Windows keeps a handle briefly after the last connection closes; cleanup
    # failing here does not affect the verification result.
    try:
        DB_PATH.unlink(missing_ok=True)
    except PermissionError:
        pass
    print("\n[PASS] migration verified")


if __name__ == "__main__":
    main()
