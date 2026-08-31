"""Parse and validate nous-pack/2 manifests (in-memory, no I/O side effects)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.skill.pack_names import (
    exposed_tool_name,
    validate_pack_id,
    validate_tool_name,
)

FORMAT_ID = "nous-pack/2"

ALLOWED_PERMISSIONS = frozenset(
    {
        "script.python",
        "network",
        "fs.read.pack",
        "fs.write.exports",
        "fs.write.workdir",
    }
)
# env.* is handled via prefix match
ENV_PERM_PREFIX = "env."

# Shell is intentionally unsupported in v2.0 (least privilege).
REJECTED_RUNNER_KINDS = frozenset({"shell", "bash", "cmd", "powershell", "node"})


@dataclass
class ParsedTool:
    name: str
    exposed_name: str
    description: str
    parameters: dict[str, Any]
    runner: dict[str, Any]
    skill_key: str
    source_path: str  # relative to pack root


@dataclass
class ParsedSkill:
    key: str
    name: str
    description: str
    instruction: str
    trigger_keywords: list[str]
    trigger_intent: str | None
    workflow: list[dict[str, Any]]
    examples: list[dict[str, Any]]
    tools_builtin: list[str]
    tools_local: list[str]
    confidence: float
    tools: list[ParsedTool] = field(default_factory=list)
    rel_dir: str = ""


@dataclass
class ParsedPack:
    pack_id: str
    name: str
    version: str
    description: str
    author: str | None
    license: str | None
    min_nous: str | None
    tags: list[str]
    permissions_requested: list[str]
    skills: list[ParsedSkill]
    shared_pythonpath: list[str]
    manifest: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER_RE.match(text.strip() + ("\n" if not text.endswith("\n") else ""))
    # Retry without forcing trailing newline quirks
    match = _FRONTMATTER_RE.match(text if text.endswith("\n") else text + "\n")
    if not match:
        # Allow body-only SKILL.md
        return {}, text.strip()
    raw_yaml, body = match.group(1), match.group(2)
    data = yaml.safe_load(raw_yaml) or {}
    if not isinstance(data, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")
    return data, body.strip()


def _normalize_permissions(raw: Any, warnings: list[str]) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("permissions must be a list of strings")
    out: list[str] = []
    for item in raw:
        perm = str(item).strip()
        if not perm:
            continue
        if perm == "script.shell" or perm.startswith("script.shell"):
            raise ValueError(
                "script.shell is not supported in nous-pack/2 (Python tools only)"
            )
        if perm in ALLOWED_PERMISSIONS or perm.startswith(ENV_PERM_PREFIX):
            if perm not in out:
                out.append(perm)
        else:
            warnings.append(f"Unknown permission ignored: {perm}")
    # Packs with tools implicitly need fs.read.pack
    if "fs.read.pack" not in out:
        out.append("fs.read.pack")
    return out


def _load_tool_json(
    *,
    path: Path,
    pack_root: Path,
    pack_id: str,
    skill_key: str,
) -> ParsedTool:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: tool descriptor must be an object")
    name = validate_tool_name(str(data.get("name") or path.stem.replace(".tool", "")))
    runner = data.get("runner") or {}
    if not isinstance(runner, dict):
        raise ValueError(f"{name}: runner must be an object")
    kind = str(runner.get("kind") or "python").lower()
    if kind in REJECTED_RUNNER_KINDS:
        raise ValueError(
            f"{name}: runner.kind={kind!r} is not supported (Python only in v2.0)"
        )
    if kind != "python":
        raise ValueError(f"{name}: unsupported runner.kind={kind!r}")
    entry = str(runner.get("entry") or "").strip()
    if not entry:
        raise ValueError(f"{name}: runner.entry is required")
    # Path confinement checked later against skill dir
    parameters = data.get("parameters") or {
        "type": "object",
        "properties": {},
    }
    if not isinstance(parameters, dict):
        raise ValueError(f"{name}: parameters must be an object")
    runner_norm = {
        "kind": "python",
        "entry": entry.replace("\\", "/"),
        "timeout_sec": int(runner.get("timeout_sec") or 60),
        "memory_mb": int(runner.get("memory_mb") or 512),
        "network": bool(runner.get("network") or False),
        "env_allow": [str(x) for x in (runner.get("env_allow") or [])],
        "pythonpath": [str(x).replace("\\", "/") for x in (runner.get("pythonpath") or [])],
    }
    rel = path.relative_to(pack_root).as_posix()
    return ParsedTool(
        name=name,
        exposed_name=exposed_tool_name(pack_id, name),
        description=str(data.get("description") or f"Pack tool {name}"),
        parameters=parameters,
        runner=runner_norm,
        skill_key=skill_key,
        source_path=rel,
    )


def _auto_wrap_scripts(
    *,
    skill_dir: Path,
    pack_root: Path,
    pack_id: str,
    skill_key: str,
    existing: set[str],
) -> list[ParsedTool]:
    """Cursor-style shorthand: scripts/*.py without a .tool.json."""
    tools: list[ParsedTool] = []
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        # Also look under tools/scripts (explicit layout)
        scripts_dir = skill_dir / "tools" / "scripts"
    if not scripts_dir.is_dir():
        return tools
    for py in sorted(scripts_dir.glob("*.py")):
        try:
            name = validate_tool_name(py.stem)
        except ValueError:
            continue
        if name in existing:
            continue
        entry = py.relative_to(skill_dir).as_posix()
        tools.append(
            ParsedTool(
                name=name,
                exposed_name=exposed_tool_name(pack_id, name),
                description=f"Pack script {py.name}",
                parameters={
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "Free-form input for the script.",
                        }
                    },
                    "required": ["input"],
                },
                runner={
                    "kind": "python",
                    "entry": entry,
                    "timeout_sec": 60,
                    "memory_mb": 512,
                    "network": False,
                    "env_allow": [],
                    "pythonpath": [],
                },
                skill_key=skill_key,
                source_path=py.relative_to(pack_root).as_posix(),
            )
        )
    return tools


def _parse_skill_dir(
    *,
    skill_dir: Path,
    pack_root: Path,
    pack_id: str,
    warnings: list[str],
) -> ParsedSkill:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise ValueError(f"Missing SKILL.md in {skill_dir.relative_to(pack_root)}")
    front, body = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    key = skill_dir.name
    name = str(front.get("name") or key).strip()
    if not name:
        raise ValueError(f"{key}: name is required")

    tools_builtin: list[str] = []
    tools_local: list[str] = []
    raw_tools = front.get("tools") or []
    if isinstance(raw_tools, list):
        for item in raw_tools:
            if isinstance(item, str):
                tools_builtin.append(item)
            elif isinstance(item, dict):
                if "builtin" in item:
                    tools_builtin.append(str(item["builtin"]))
                if "local" in item:
                    tools_local.append(str(item["local"]))
            else:
                warnings.append(f"{key}: ignored tools entry {item!r}")

    examples: list[dict[str, Any]] = []
    examples_path = skill_dir / "examples.json"
    if examples_path.is_file():
        loaded = json.loads(examples_path.read_text(encoding="utf-8"))
        if isinstance(loaded, list):
            examples = [x for x in loaded if isinstance(x, dict)]

    workflow = front.get("workflow") or []
    if not isinstance(workflow, list):
        workflow = []

    parsed = ParsedSkill(
        key=key,
        name=name[:200],
        description=str(front.get("description") or ""),
        instruction=body or str(front.get("instruction") or ""),
        trigger_keywords=[str(x) for x in (front.get("trigger_keywords") or [])],
        trigger_intent=(
            str(front["trigger_intent"])
            if front.get("trigger_intent") is not None
            else None
        ),
        workflow=[x for x in workflow if isinstance(x, dict)],
        examples=examples,
        tools_builtin=tools_builtin,
        tools_local=tools_local,
        confidence=float(front.get("confidence") or 0.9),
        rel_dir=skill_dir.relative_to(pack_root).as_posix(),
    )

    tool_objs: list[ParsedTool] = []
    tools_dir = skill_dir / "tools"
    if tools_dir.is_dir():
        for tool_path in sorted(tools_dir.glob("*.tool.json")):
            tool_objs.append(
                _load_tool_json(
                    path=tool_path,
                    pack_root=pack_root,
                    pack_id=pack_id,
                    skill_key=parsed.rel_dir,
                )
            )
    existing = {t.name for t in tool_objs}
    tool_objs.extend(
        _auto_wrap_scripts(
            skill_dir=skill_dir,
            pack_root=pack_root,
            pack_id=pack_id,
            skill_key=parsed.rel_dir,
            existing=existing,
        )
    )

    # Validate entry paths stay inside skill dir
    for tool in tool_objs:
        entry = tool.runner["entry"]
        resolved = (skill_dir / entry).resolve()
        try:
            resolved.relative_to(skill_dir.resolve())
        except ValueError as exc:
            raise ValueError(
                f"{tool.name}: runner.entry escapes skill directory"
            ) from exc
        if not resolved.is_file():
            raise ValueError(f"{tool.name}: entry not found: {entry}")

    # Ensure frontmatter local tools exist (or warn)
    local_names = {t.name for t in tool_objs}
    for local in tools_local:
        if local not in local_names:
            warnings.append(
                f"{key}: tools.local {local!r} has no matching tool descriptor/script"
            )

    # Store exposed names in tools list for Skill.tools column
    parsed.tools = tool_objs
    return parsed


def parse_pack_directory(pack_root: Path) -> ParsedPack:
    """Parse an extracted pack directory into a structured model."""
    warnings: list[str] = []
    errors: list[str] = []
    pack_root = pack_root.resolve()

    pack_json_path = pack_root / "pack.json"
    skill_md_root = pack_root / "SKILL.md"

    if pack_json_path.is_file():
        manifest = json.loads(pack_json_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("pack.json must be an object")
        fmt = str(manifest.get("format") or "")
        if fmt != FORMAT_ID:
            raise ValueError(f"Unsupported format {fmt!r}; expected {FORMAT_ID}")
        pack_id = validate_pack_id(str(manifest.get("id") or ""))
        name = str(manifest.get("name") or pack_id)
        version = str(manifest.get("version") or "").strip()
        if not version:
            raise ValueError("pack.json version is required (SemVer)")
        skill_refs = manifest.get("skills") or []
        if not isinstance(skill_refs, list) or not skill_refs:
            raise ValueError("pack.json skills must be a non-empty list")
        permissions = _normalize_permissions(manifest.get("permissions"), warnings)
        shared = manifest.get("shared") or {}
        shared_pythonpath = []
        if isinstance(shared, dict):
            shared_pythonpath = [
                str(x).replace("\\", "/") for x in (shared.get("pythonpath") or [])
            ]
        skills: list[ParsedSkill] = []
        for ref in skill_refs:
            rel = str(ref).replace("\\", "/").strip().lstrip("./")
            skill_dir = (pack_root / rel).resolve()
            try:
                skill_dir.relative_to(pack_root)
            except ValueError as exc:
                raise ValueError(f"Skill path escapes pack: {rel}") from exc
            if not skill_dir.is_dir():
                raise ValueError(f"Skill directory not found: {rel}")
            skills.append(
                _parse_skill_dir(
                    skill_dir=skill_dir,
                    pack_root=pack_root,
                    pack_id=pack_id,
                    warnings=warnings,
                )
            )
        parsed = ParsedPack(
            pack_id=pack_id,
            name=name[:200],
            version=version[:32],
            description=str(manifest.get("description") or ""),
            author=(str(manifest["author"]) if manifest.get("author") else None),
            license=(str(manifest["license"]) if manifest.get("license") else None),
            min_nous=(str(manifest["min_nous"]) if manifest.get("min_nous") else None),
            tags=[str(t) for t in (manifest.get("tags") or [])],
            permissions_requested=permissions,
            skills=skills,
            shared_pythonpath=shared_pythonpath,
            manifest=manifest,
            warnings=warnings,
            errors=errors,
        )
    elif skill_md_root.is_file():
        # Single-skill Cursor-style zip
        pack_id = validate_pack_id(pack_root.name.lower().replace(" ", "-")[:80] or "imported.skill")
        skill = _parse_skill_dir(
            skill_dir=pack_root,
            pack_root=pack_root,
            pack_id=pack_id,
            warnings=warnings,
        )
        skill.key = skill.key or "main"
        skill.rel_dir = "."
        perms = ["fs.read.pack"]
        if skill.tools:
            perms.append("script.python")
            if any(t.runner.get("network") for t in skill.tools):
                perms.append("network")
            perms.append("fs.write.exports")
        parsed = ParsedPack(
            pack_id=pack_id,
            name=skill.name,
            version="0.0.0",
            description=skill.description,
            author=None,
            license=None,
            min_nous=None,
            tags=[],
            permissions_requested=perms,
            skills=[skill],
            shared_pythonpath=[],
            manifest={
                "format": FORMAT_ID,
                "id": pack_id,
                "name": skill.name,
                "version": "0.0.0",
                "skills": ["."],
                "permissions": perms,
                "synthesized": True,
            },
            warnings=warnings + ["Synthesized pack.json from single-skill zip"],
            errors=errors,
        )
    else:
        raise ValueError("Archive must contain pack.json or a root SKILL.md")

    # Cross-pack tool name uniqueness
    seen_exposed: set[str] = set()
    for skill in parsed.skills:
        for tool in skill.tools:
            if tool.exposed_name in seen_exposed:
                errors.append(f"Duplicate tool exposed name: {tool.exposed_name}")
            seen_exposed.add(tool.exposed_name)
        if skill.tools and "script.python" not in parsed.permissions_requested:
            errors.append(
                "Pack declares local tools but missing permission script.python"
            )
            break

    parsed.errors = errors
    return parsed


def preview_dict(parsed: ParsedPack) -> dict[str, Any]:
    return {
        "format": FORMAT_ID,
        "pack_id": parsed.pack_id,
        "version": parsed.version,
        "name": parsed.name,
        "description": parsed.description,
        "permissions_requested": parsed.permissions_requested,
        "tags": parsed.tags,
        "skills": [
            {
                "key": s.key,
                "name": s.name,
                "description": s.description,
                "tools_local": [t.name for t in s.tools],
                "tools_local_exposed": [t.exposed_name for t in s.tools],
                "tools_builtin": s.tools_builtin,
            }
            for s in parsed.skills
        ],
        "warnings": parsed.warnings,
        "errors": parsed.errors,
    }
