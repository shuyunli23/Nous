#!/bin/sh
# Container entrypoint: wait for the database, apply migrations, then exec the
# main process. A failed migration aborts startup rather than serving traffic
# against an unknown schema.
set -eu

echo "[entrypoint] waiting for database..."
python - <<'PY'
import os
import sys
import time
import urllib.parse

url = os.environ.get("DATABASE_URL", "")
if "postgres" not in url:
    print("[entrypoint] non-postgres database, skipping wait")
    sys.exit(0)

# Parse host/port out of the SQLAlchemy URL without extra dependencies.
parsed = urllib.parse.urlparse(url.replace("+asyncpg", ""))
host = parsed.hostname or "postgres"
port = parsed.port or 5432

import socket

deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=3):
            print(f"[entrypoint] database reachable at {host}:{port}")
            sys.exit(0)
    except OSError:
        time.sleep(1.5)

print(f"[entrypoint] database unreachable at {host}:{port} after 60s", file=sys.stderr)
sys.exit(1)
PY

echo "[entrypoint] applying migrations..."
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"
