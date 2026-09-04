"""Adapt DeepSeek Harness (Cordis) plugin packages into a Nous ParsedPack.

Harness plugins are TypeScript modules with ``apply(ctx)``. Nous does not run
Cordis. We import the stable *description* (README / SKILL.md) and any Python
tools that happen to ship in the tree, then warn that ``apply()`` is not executed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.plugin.ids import npm_name_to_pack_id
from app.skill.pack_format import (
    FORMAT_DSH,
    ParsedPack,
    ParsedSkill,
    _parse_skill_dir,
    discover_skill_refs,
)

_README_NAMES = ("README.md", "README.zh.md", "README.en.md", "readme.md")


def is_dsh_package(root: Path) -> bool:
    pkg = root / "package.json"
    if not pkg.is_file():
        return False
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and data.get("dsh") is not None


def _read_readme(root: Path) -> str:
    for name in _README_NAMES:
        path = root / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                return text[:12_000]
    return ""


def synthesize_dsh_pack(root: Path) -> ParsedPack:
    pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
    npm_name = str(pkg.get("name") or root.name)
    pack_id = npm_name_to_pack_id(npm_name)
    version = str(pkg.get("version") or "0.0.0").strip() or "0.0.0"
    description = str(pkg.get("description") or "").strip()
    dsh = pkg.get("dsh") if isinstance(pkg.get("dsh"), dict) else {}
    warnings = [
        "DeepSeek Harness Cordis runtime is not executed. "
        "Nous imported this as a plugin (skills + Python tools if present).",
    ]
    if dsh.get("bundle"):
        warnings.append("dsh.bundle / cordis.patch.yml is recorded, not mounted.")
    errors: list[str] = []

    skill_refs = discover_skill_refs(root)
    skills: list[ParsedSkill] = []
    if skill_refs:
        for ref in skill_refs:
            rel = "." if ref == "." else ref
            skill_dir = root if rel == "." else (root / rel)
            skills.append(
                _parse_skill_dir(
                    skill_dir=skill_dir,
                    pack_root=root,
                    pack_id=pack_id,
                    warnings=warnings,
                )
            )
    else:
        readme = _read_readme(root)
        if not readme:
            readme = (
                f"Imported DeepSeek Harness plugin `{npm_name}`.\n\n"
                "This package registers Cordis services in dsh. Nous stored it "
                "as a Skill so you can recall what it does; TypeScript `apply()` "
                "is not run here."
            )
        display = str(pkg.get("name") or pack_id)
        skills.append(
            ParsedSkill(
                key="main",
                name=display[:200],
                description=description or display,
                instruction=readme,
                trigger_keywords=_keywords_from_name(display),
                trigger_intent=description or None,
                workflow=[],
                examples=[],
                tools_builtin=[],
                tools_local=[],
                confidence=0.7,
                tools=[],
                rel_dir=".",
            )
        )
        warnings.append("No SKILL.md found; synthesized a Skill from package README.")

    perms = ["fs.read.pack"]
    if any(s.tools for s in skills):
        perms.append("script.python")
        if any(t.runner.get("network") for s in skills for t in s.tools):
            perms.append("network")
        perms.append("fs.write.exports")

    manifest: dict[str, Any] = {
        "format": FORMAT_DSH,
        "id": pack_id,
        "name": str(pkg.get("name") or pack_id),
        "version": version[:32],
        "description": description,
        "skills": [s.rel_dir or "." for s in skills],
        "permissions": perms,
        "dsh": dsh,
        "npm_name": npm_name,
        "synthesized": True,
    }
    return ParsedPack(
        pack_id=pack_id,
        name=str(pkg.get("name") or pack_id)[:200],
        version=version[:32],
        description=description,
        author=_author(pkg),
        license=(str(pkg["license"]) if pkg.get("license") else None),
        min_nous=None,
        tags=_tags(pkg, dsh),
        permissions_requested=perms,
        skills=skills,
        shared_pythonpath=[],
        manifest=manifest,
        warnings=warnings,
        errors=errors,
    )


def _author(pkg: dict[str, Any]) -> str | None:
    author = pkg.get("author")
    if isinstance(author, str) and author.strip():
        return author.strip()[:200]
    if isinstance(author, dict) and author.get("name"):
        return str(author["name"])[:200]
    return None


def _tags(pkg: dict[str, Any], dsh: dict[str, Any]) -> list[str]:
    tags = ["dsh-plugin"]
    keywords = pkg.get("keywords")
    if isinstance(keywords, list):
        for item in keywords[:8]:
            text = str(item).strip()
            if text and text not in tags:
                tags.append(text[:40])
    if dsh.get("bundle"):
        tags.append("bundle")
    return tags


def _keywords_from_name(name: str) -> list[str]:
    parts = [p for p in re.split(r"[@/_.\s-]+", name.lower()) if p]
    out: list[str] = []
    for part in parts:
        if len(part) >= 2 and part not in out:
            out.append(part)
    if name not in out:
        out.insert(0, name[:80])
    return out[:8]
