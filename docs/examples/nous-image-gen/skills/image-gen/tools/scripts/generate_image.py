"""Pack-local generate_image entrypoint.

Delegates to the shared Nous image generator so pack tools and the builtin
``generate_image`` stay in sync. Expects ``NOUS_BACKEND_ROOT`` / ``PYTHONPATH``
from the pack runner.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


def _ensure_backend_on_path() -> None:
    import os

    root = os.environ.get("NOUS_BACKEND_ROOT", "").strip()
    candidates = []
    if root:
        candidates.append(Path(root))
    # Fallback: walk up from this file toward a directory that contains ``app/``.
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "app" / "main.py").is_file():
            candidates.append(parent)
            break
    for cand in candidates:
        s = str(cand)
        if s not in sys.path:
            sys.path.insert(0, s)


def main() -> int:
    try:
        raw = sys.stdin.read()
        args = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"invalid stdin JSON: {exc}"}))
        return 1

    prompt = (args.get("prompt") or args.get("input") or "").strip()
    if not prompt:
        print(json.dumps({"ok": False, "error": "prompt is required"}))
        return 1

    _ensure_backend_on_path()
    try:
        from app.agent.tools.image_gen import generate_image
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"Failed to import Nous image generator: {exc}",
                }
            )
        )
        return 1

    result = asyncio.run(
        generate_image(
            prompt=prompt,
            size=str(args.get("size") or "1024x1024"),
            filename_hint=args.get("filename_hint"),
        )
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
