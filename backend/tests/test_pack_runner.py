"""Pre-install smoke validation of generated pack scripts (real subprocess)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from app.skill.pack_runner import smoke_run_script


def _write(skill_dir: Path, source: str) -> Path:
    scripts = skill_dir / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    path = scripts / "main.py"
    path.write_text(source, encoding="utf-8")
    return path


def test_smoke_passes_on_contract_abiding_script() -> None:
    with TemporaryDirectory() as raw:
        skill_dir = Path(raw)
        script = _write(
            skill_dir,
            "import json, sys\n"
            "data = json.load(sys.stdin)\n"
            "print(json.dumps({'ok': True, 'echo': data.get('x')}))\n",
        )
        result = asyncio.run(
            smoke_run_script(
                script_path=script,
                skill_dir=skill_dir,
                stdin_json={"x": 42},
            )
        )
    assert result.ok is True
    assert result.returned == {"ok": True, "echo": 42}
    assert result.timed_out is False


def test_smoke_fails_when_script_reports_error() -> None:
    with TemporaryDirectory() as raw:
        skill_dir = Path(raw)
        script = _write(
            skill_dir,
            "import json, sys\n"
            "sys.stderr.write('boom trace\\n')\n"
            "print(json.dumps({'ok': False, 'error': 'nope'}))\n",
        )
        result = asyncio.run(
            smoke_run_script(
                script_path=script,
                skill_dir=skill_dir,
                stdin_json={},
            )
        )
    assert result.ok is False
    assert "nope" in result.error


def test_smoke_fails_on_crash_and_captures_stderr() -> None:
    with TemporaryDirectory() as raw:
        skill_dir = Path(raw)
        script = _write(
            skill_dir,
            "import sys\n"
            "sys.stderr.write('kaboom\\n')\n"
            "raise SystemExit(1)\n",
        )
        result = asyncio.run(
            smoke_run_script(
                script_path=script,
                skill_dir=skill_dir,
                stdin_json={},
            )
        )
    assert result.ok is False
    # Empty stdout -> contract violation surfaced, stderr carried for debugging.
    assert "kaboom" in result.stderr


def test_smoke_flags_timeout() -> None:
    with TemporaryDirectory() as raw:
        skill_dir = Path(raw)
        script = _write(
            skill_dir,
            "import time\ntime.sleep(30)\n",
        )
        result = asyncio.run(
            smoke_run_script(
                script_path=script,
                skill_dir=skill_dir,
                stdin_json={},
                timeout_sec=1,
            )
        )
    assert result.ok is False
    assert result.timed_out is True


def test_smoke_rejects_script_outside_skill_dir() -> None:
    with TemporaryDirectory() as raw:
        root = Path(raw)
        skill_dir = root / "skill"
        skill_dir.mkdir()
        outside = root / "evil.py"
        outside.write_text("print('{}')\n", encoding="utf-8")
        result = asyncio.run(
            smoke_run_script(
                script_path=outside,
                skill_dir=skill_dir,
                stdin_json={},
            )
        )
    assert result.ok is False
    assert "escapes" in result.error.lower()


if __name__ == "__main__":
    test_smoke_passes_on_contract_abiding_script()
    test_smoke_fails_when_script_reports_error()
    test_smoke_fails_on_crash_and_captures_stderr()
    test_smoke_flags_timeout()
    test_smoke_rejects_script_outside_skill_dir()
    print("ok")
