"""Dev server: watch app code, ignore workspace writes under data/.

Uvicorn always adds cwd to the WatchFiles set and reloads on any ``*.py``.
Agent scripts in ``data/shell_workspace`` would otherwise recycle the process
mid-turn and leave the chat UI spinning.
"""

from __future__ import annotations

from pathlib import Path

import uvicorn

HERE = Path(__file__).resolve().parent


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(HERE / "app")],
        reload_excludes=[
            str(HERE / "data"),
            str(HERE / ".venv"),
            str(HERE / "tests"),
            "_tmp_*.py",
        ],
        timeout_graceful_shutdown=5,
    )
