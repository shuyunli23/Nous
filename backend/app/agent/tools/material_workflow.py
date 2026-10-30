"""Durable plans, source files and delivery bundles for authored materials.

These tools write artifacts, not arbitrary executable programs. Code execution
goes through the existing operator-controlled shell tool and its sandbox policy.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.agent.tools.export_urls import ascii_export_stem, export_download_url

_ID = re.compile(r"^[a-f0-9]{16}$")
_SOURCE_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,119}$")
_SOURCE_EXTENSIONS = {".java", ".py", ".js", ".ts", ".sql", ".txt", ".md", ".json", ".csv", ".html", ".css"}
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def exports_dir() -> Path:
    folder = settings.resolve_path("./data/exports")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def load_material_plan(plan_id: str) -> dict[str, Any]:
    if not _ID.fullmatch(plan_id or ""):
        raise ValueError("Invalid plan_id. Use the value returned by plan_materials.")
    path = exports_dir() / f"material_plan_{plan_id}.json"
    if not path.is_file():
        raise ValueError("Material plan not found. Call plan_materials before authoring.")
    return json.loads(path.read_text(encoding="utf-8"))


async def plan_materials(
    *, title: str, audience: str, objectives: list[str],
    deliverables: list[dict[str, Any]], outline: list[dict[str, Any]],
    acceptance_criteria: list[str] | None = None,
    references: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Record a concrete teaching/story outline before generating either format."""
    if not title.strip() or not audience.strip() or not objectives or not outline:
        raise ValueError("Provide title, audience, learning objectives and a purposeful outline.")
    if len(outline) > 80 or len(objectives) > 15 or not 1 <= len(deliverables) <= 3:
        raise ValueError("Use at most 80 outline entries, 15 objectives and 3 deliverables.")
    normalized = []
    seen = set()
    for item in deliverables:
        kind = item.get("kind")
        if kind not in {"pptx", "pdf"} or kind in seen:
            raise ValueError("Each deliverable kind must be pptx or pdf, without duplicates.")
        count = item.get("total_slides")
        if count is not None and (isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 60):
            raise ValueError("total_slides must be an integer from 1 to 60, including cover and closing.")
        normalized.append({"kind": kind, "purpose": str(item.get("purpose") or ""), "total_slides": count})
        seen.add(kind)
    for item in outline:
        if not isinstance(item, dict) or not str(item.get("heading") or "").strip() or not str(item.get("purpose") or "").strip():
            raise ValueError("Every outline item needs a heading and a concrete purpose.")
        if item.get("kind") not in seen:
            raise ValueError("Every outline item must name one of the requested deliverable kinds.")
    for item in normalized:
        if item["kind"] == "pptx" and item["total_slides"] is not None:
            count = sum(row.get("kind") == "pptx" for row in outline)
            if count != item["total_slides"]:
                raise ValueError(f"PPT outline has {count} entries, but total_slides={item['total_slides']}. Plan exactly the requested total.")
    plan_id = uuid.uuid4().hex[:16]
    plan = {
        "version": 1, "plan_id": plan_id, "title": title.strip(), "audience": audience.strip(),
        "objectives": objectives, "deliverables": normalized, "outline": outline,
        "acceptance_criteria": acceptance_criteria or [], "references": references or [],
    }
    (exports_dir() / f"material_plan_{plan_id}.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True, "plan_id": plan_id, "plan": plan,
        "message": "Plan saved. Pass plan_id to create_presentation/create_pdf. Author each format for its own use, preserve all requested pages, then call review_materials on BOTH final files. A plan is not a delivered document.",
    }


def apply_material_plan(plan_id: str | None, kind: str) -> dict[str, Any]:
    if not plan_id:
        return {}
    plan = load_material_plan(plan_id)
    spec = next((item for item in plan["deliverables"] if item["kind"] == kind), None)
    if spec is None:
        raise ValueError(f"The saved plan does not request {kind}.")
    return {**plan, "expected_slide_count": spec.get("total_slides")}


def load_material_draft(draft_id: str, kind: str, plan_id: str | None = None) -> dict[str, Any]:
    if not _ID.fullmatch(draft_id or ""):
        raise ValueError("Invalid draft_id. Use write_material_draft first.")
    path = exports_dir() / f"material_draft_{draft_id}.json"
    if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Material draft is missing or too large.")
    draft = json.loads(path.read_text(encoding="utf-8"))
    if draft.get("kind") != kind or (plan_id and draft.get("plan_id") != plan_id):
        raise ValueError("Draft format/plan does not match this authoring request. Use a new draft for the updated plan.")
    return draft


async def write_material_draft(*, plan_id: str, kind: str, items: list[dict[str, Any]],
                               draft_id: str | None = None) -> dict[str, Any]:
    """Append a small authored batch, keeping long documents out of one LLM call."""
    plan = load_material_plan(plan_id)
    if kind not in {"pptx", "pdf", "sources"}:
        raise ValueError("Draft kind must be pptx, pdf or sources.")
    if kind != "sources" and not any(item["kind"] == kind for item in plan["deliverables"]):
        raise ValueError("This format is not in the material plan.")
    if not isinstance(items, list) or not 1 <= len(items) <= 8 or any(not isinstance(item, dict) for item in items):
        raise ValueError("Write 1 to 8 items per batch. Prefer 2-4 slides, 1-3 chapters, or 1-2 source files.")
    if draft_id:
        draft = load_material_draft(draft_id, kind, plan_id)
    else:
        draft_id = uuid.uuid4().hex[:16]
        draft = {"draft_id": draft_id, "plan_id": plan_id, "kind": kind, "items": []}
    merged = [*draft["items"], *items]
    limit = {"pptx": 60, "pdf": 80, "sources": 20}[kind]
    expected = next((item.get("total_slides") for item in plan["deliverables"] if item["kind"] == "pptx"), None) if kind == "pptx" else None
    if len(merged) > limit or (expected and len(merged) > expected):
        raise ValueError(f"Draft would contain {len(merged)} items, exceeding its planned/format limit. Start a new corrected draft; no existing content was discarded.")
    draft["items"] = merged
    raw = json.dumps(draft, ensure_ascii=False, indent=2)
    if len(raw.encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError("Material draft exceeds 2 MiB. Split this into separate materials.")
    path = exports_dir() / f"material_draft_{draft_id}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(raw, encoding="utf-8")
    temporary.replace(path)
    return {"ok": True, "draft_id": draft_id, "plan_id": plan_id, "kind": kind,
            "item_count": len(merged), "expected_slide_count": expected,
            "message": "Batch saved. Continue with this draft_id, then export with create_presentation/create_pdf/create_code_files using draft_id instead of resending the complete content. A draft is not the final file."}


async def read_material_draft(*, draft_id: str, kind: str, start: int = 0, count: int = 3) -> dict[str, Any]:
    """Recover a bounded range after interruption without rereading a whole kit."""
    if type(start) is not int or start < 0 or type(count) is not int or not 1 <= count <= 8:
        raise ValueError("Use a nonnegative start and a count between 1 and 8.")
    draft = load_material_draft(draft_id, kind)
    selected = draft["items"][start:start + count]
    if len(json.dumps(selected, ensure_ascii=False).encode("utf-8")) > 128000:
        raise ValueError("Requested draft range exceeds 128000 bytes. Read fewer items at a time.")
    return {"ok": True, "draft_id": draft_id, "kind": kind, "plan_id": draft["plan_id"],
            "item_count": len(draft["items"]), "start": start, "items": selected,
            "message": "These are saved draft items, not a new export. Continue writing the unfinished draft or create a corrected draft for changed requirements."}


async def create_code_files(*, title: str, files: list[dict[str, str]] | None = None,
                            draft_id: str | None = None, plan_id: str | None = None) -> dict[str, Any]:
    """Deliver complete UTF-8 sources with their original compilable filenames."""
    from app.agent.tools.shell_config import resolve_shell

    if draft_id:
        if files is not None:
            raise ValueError("Pass files or draft_id, not both.")
        files = load_material_draft(draft_id, "sources", plan_id)["items"]
    if not files or not 1 <= len(files) <= 20:
        raise ValueError("Provide between 1 and 20 source files.")
    names = set()
    total = 0
    for item in files:
        name, content = item.get("filename", ""), item.get("content", "")
        if (not _SOURCE_NAME.fullmatch(name) or ".." in name
                or Path(name).stem.upper() in _RESERVED_NAMES
                or Path(name).suffix.lower() not in _SOURCE_EXTENSIONS):
            raise ValueError("Source filenames must be simple names with a supported text/code extension, without directories.")
        if name.casefold() in names or not content.strip():
            raise ValueError("Source filenames must be unique and contents must be nonempty.")
        names.add(name.casefold())
        total += len(content.encode("utf-8"))
    if total > 1024 * 1024:
        raise ValueError("Combined source size must not exceed 1 MiB.")
    resolved = resolve_shell()
    root = Path(resolved.workspace_path).resolve()
    source_id = uuid.uuid4().hex[:16]
    workspace = (root / f"materials_{source_id}").resolve()
    if not workspace.is_relative_to(root):
        raise ValueError("Source workspace escapes the configured shell workspace.")
    workspace.mkdir(parents=True, exist_ok=False)
    manifest = []
    archive = exports_dir() / f"{ascii_export_stem(title, fallback='sources')}_{source_id}_sources.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for item in files:
            # Preserve original spacing, including ordinary ASCII indentation.
            content = item["content"].replace("\r\n", "\n")
            path = workspace / item["filename"]
            path.write_text(content, encoding="utf-8", newline="\n")
            bundle.write(path, item["filename"])
            manifest.append({"filename": item["filename"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {
        "ok": True, "workspace": str(workspace), "files": manifest,
        "path": str(archive), "filename": archive.name, "download_url": export_download_url(archive.name),
        "execution_enabled": resolved.enabled,
        "verification_status": "not_run",
        "message": "Complete source files delivered. They have NOT been executed. Call verify_code_examples with compile and run commands when execution is enabled; otherwise disclose that the code is unverified. Keep these filenames when compiling.",
    }


async def verify_code_examples(*, workspace: str, commands: list[str]) -> dict[str, Any]:
    """Run explicit compile/test commands using the existing shell consent gate."""
    from app.agent.tools.shell import run_command
    from app.agent.tools.shell_config import resolve_shell

    if not resolve_shell().enabled:
        return {"ok": False, "verification_status": "unavailable", "error": "Code execution is disabled. Enable command execution in Settings to verify examples; never claim code has run."}
    if not 1 <= len(commands) <= 8 or any(not isinstance(cmd, str) or not cmd.strip() or len(cmd) > 4000 for cmd in commands):
        raise ValueError("Provide 1 to 8 bounded compile/run commands.")
    root = Path(resolve_shell().workspace_path).resolve()
    folder = Path(workspace).resolve()
    if not folder.is_relative_to(root) or not folder.name.startswith("materials_") or not folder.is_dir():
        raise ValueError("Use the workspace returned by create_code_files.")
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file() and p.suffix.lower() in _SOURCE_EXTENSIONS}
    results = []
    for command in commands:
        result = await run_command(command=command, workdir=str(folder), timeout_ms=60000, description="验证材料配套代码")
        results.append({"command": command, **result})
        if not result.get("ok") or result.get("exit_code", 0) != 0:
            break
    passed = len(results) == len(commands) and all(r.get("ok") and r.get("exit_code", 0) == 0 for r in results)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file() and p.suffix.lower() in _SOURCE_EXTENSIONS}
    unchanged = before == after
    passed = passed and bool(before) and unchanged
    log = exports_dir() / f"code_verification_{uuid.uuid4().hex[:16]}.json"
    payload = {"verification_status": "passed" if passed else "failed", "source_sha256": before, "sources_unchanged": unchanged, "commands": results}
    log.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": passed, **payload, "path": str(log), "download_url": export_download_url(log.name), "message": "Only the listed commands and source hashes were verified. Correctness beyond these observations still needs technical review."}


async def package_materials(*, title: str, files: list[str], readme: str = "") -> dict[str, Any]:
    """Package only explicit authored files; never sweep a working directory."""
    from app.agent.tools.material_assets import resolve_material_asset

    if not 1 <= len(files) <= 30:
        raise ValueError("Select 1 to 30 explicit material files to package.")
    paths = [resolve_material_asset(item) for item in files]
    if len({p.name.casefold() for p in paths}) != len(paths):
        raise ValueError("Selected files have duplicate names. Select unique output files.")
    if readme and (len(readme) > 100000 or any(p.name.casefold() == "readme.md" for p in paths)):
        raise ValueError("README must be at most 100000 characters and must not duplicate a selected README.md.")
    if sum(p.stat().st_size for p in paths) > 100 * 1024 * 1024:
        raise ValueError("Material bundle exceeds 100 MiB.")
    name = f"{ascii_export_stem(title, fallback='materials')}_{uuid.uuid4().hex[:16]}_kit.zip"
    path = exports_dir() / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in paths:
            archive.write(item, item.name)
        if readme:
            archive.writestr("README.md", readme)
    return {"ok": True, "path": str(path), "filename": name, "download_url": export_download_url(name), "file_count": len(paths), "message": "Bundle ready. Packaging does not certify content or visual quality; use the review report for those claims."}
