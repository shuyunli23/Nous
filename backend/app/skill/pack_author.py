"""Promote a conversation's reusable code into an executable nous-pack/2 pack.

This is the fourth sedimentation path (alongside skill / knowledge / persona).
Where the advice-skill extractor distils *prose* steps, this one distils a
*runnable* Python tool: it asks the model to emit a script obeying the
stdin-JSON -> stdout-JSON contract, materialises a real pack tree
(``pack.json`` + ``skills/main/SKILL.md`` + ``tools/main.tool.json`` +
``scripts/main.py``), smoke-tests the script in the same sandbox that will run
it in production, and only then installs it -- ACTIVE if the smoke test passed
and ``script.python`` was granted, otherwise PENDING_REVIEW with the failure
surfaced back to the user.
"""

from __future__ import annotations

import json
import re
import secrets
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.client import Message, structured_complete
from app.llm.prompts.extraction import format_conversation_keep_code
from app.llm.prompts.pack_author import PACK_AUTHOR_SYSTEM, PACK_AUTHOR_USER
from app.repositories.conversation_repo import ConversationRepository
from app.services.pack_service import PackService
from app.skill.pack_archive import zip_directory
from app.skill.pack_names import validate_tool_name

logger = get_logger(__name__)


# ── LLM output schema ─────────────────────────────────────────────────────

class PackDraft(BaseModel):
    reusable: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    name: str = ""
    description: str = ""
    instruction: str = ""
    trigger_keywords: list[str] = Field(default_factory=list)
    trigger_intent: str = ""
    tool_name: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    python_source: str = ""
    needs_network: bool = False
    smoke_input: dict[str, Any] = Field(default_factory=dict)
    examples: list[dict[str, Any]] = Field(default_factory=list)


# ── Result dataclass ──────────────────────────────────────────────────────

@dataclass
class PackSettleResult:
    """Outcome of authoring a pack from a conversation."""

    created: bool = False
    reusable: bool = True
    pack_id: str | None = None
    pack_row_id: str | None = None
    status: str | None = None  # active | pending_review
    tool_count: int = 0
    validated: bool = False  # smoke test passed
    activated: bool = False
    reason: str = ""  # why skipped / why pending review
    skill_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────

def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:40] or "tool"


def _coerce_tool_name(raw: str) -> str:
    candidate = re.sub(r"[^a-z0-9_]", "_", (raw or "").lower()).strip("_")
    if candidate and candidate[0].isdigit():
        candidate = f"t_{candidate}"
    candidate = candidate[:64] or "run"
    try:
        return validate_tool_name(candidate)
    except ValueError:
        return "run"


def _normalize_parameters(params: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(params, dict) or not params:
        return {"type": "object", "properties": {}}
    if "type" not in params:
        params = {"type": "object", **params}
    return params


def _dump_frontmatter(front: dict[str, Any]) -> str:
    # Keep it simple and deterministic; SKILL.md frontmatter is YAML.
    import yaml

    return yaml.safe_dump(front, allow_unicode=True, sort_keys=False).strip()


def _materialize(draft: PackDraft, *, pack_id: str, tool_name: str, root: Path) -> Path:
    """Write the pack tree under ``root`` and return the skill dir."""
    permissions = ["script.python"]
    if draft.needs_network:
        permissions.append("network")

    manifest = {
        "format": "nous-pack/2",
        "id": pack_id,
        "name": draft.name or pack_id,
        "version": "1.0.0",
        "description": draft.description,
        "permissions": permissions,
        "skills": ["skills/main"],
        "_nous": {"origin": "settle"},
    }
    (root / "pack.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    skill_dir = root / "skills" / "main"
    (skill_dir / "tools").mkdir(parents=True, exist_ok=True)
    (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)

    front = {
        "name": draft.name or pack_id,
        "description": draft.description,
        "trigger_keywords": draft.trigger_keywords,
        "trigger_intent": draft.trigger_intent or None,
        "tools": [{"local": tool_name}],
    }
    skill_md = f"---\n{_dump_frontmatter(front)}\n---\n\n{draft.instruction}\n"
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    tool_json = {
        "name": tool_name,
        "description": draft.description or f"Pack tool {tool_name}",
        "parameters": _normalize_parameters(draft.parameters),
        "runner": {
            "kind": "python",
            "entry": "scripts/main.py",
            "timeout_sec": 60,
            "network": bool(draft.needs_network),
        },
    }
    (skill_dir / "tools" / f"{tool_name}.tool.json").write_text(
        json.dumps(tool_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if draft.examples:
        (skill_dir / "examples.json").write_text(
            json.dumps(draft.examples, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    (skill_dir / "scripts" / "main.py").write_text(draft.python_source, encoding="utf-8")
    return skill_dir


# ── Orchestrator ──────────────────────────────────────────────────────────

async def author_pack_from_conversation(
    session: AsyncSession,
    conversation_id: str,
    *,
    user_id: str,
    granted_permissions: list[str] | None = None,
) -> PackSettleResult:
    """Draft, validate, and install a pack from a conversation's code.

    ``granted_permissions`` carries what the user ticked in the settle dialog
    (e.g. ``["script.python", "network"]``). Activation requires the smoke test
    to pass *and* ``script.python`` to be granted; otherwise the pack lands in
    PENDING_REVIEW with tools disabled.
    """
    granted = list(granted_permissions or [])

    conv_repo = ConversationRepository(session)
    conv = await conv_repo.get(conversation_id)
    if conv is None:
        return PackSettleResult(reason="Conversation not found.")

    messages = await conv_repo.list_messages(conversation_id)
    user_assistant = [m for m in messages if m.role in {"user", "assistant"}]
    if len(user_assistant) < settings.extraction_min_messages:
        return PackSettleResult(
            reason=f"Too few messages ({len(user_assistant)}).",
        )

    conv_text = format_conversation_keep_code(
        [{"role": m.role, "content": m.content} for m in user_assistant]
    )

    from app.llm.usage import PURPOSE_SKILL, usage_scope

    author_msgs: list[Message] = [
        {"role": "system", "content": PACK_AUTHOR_SYSTEM},
        {"role": "user", "content": PACK_AUTHOR_USER.format(conversation_text=conv_text)},
    ]
    with usage_scope(
        purpose=PURPOSE_SKILL,
        user_id=user_id,
        conversation_id=conversation_id,
        session=session,
    ):
        draft: PackDraft = await structured_complete(author_msgs, PackDraft)

    logger.info(
        "pack_authored",
        conversation_id=conversation_id,
        reusable=draft.reusable,
        confidence=draft.confidence,
        tool_name=draft.tool_name,
    )

    if not draft.reusable or draft.confidence < settings.extraction_min_confidence:
        return PackSettleResult(
            reusable=False,
            reason=draft.reason or "No reusable, runnable code found.",
        )
    if not draft.python_source.strip():
        return PackSettleResult(
            reusable=False,
            reason="Model produced no script source.",
        )

    tool_name = _coerce_tool_name(draft.tool_name or draft.name)
    pack_id = f"auto-{_slug(draft.name)}-{secrets.token_hex(3)}"

    with tempfile.TemporaryDirectory(prefix="nous-pack-author-") as tmp:
        root = Path(tmp)
        skill_dir = _materialize(draft, pack_id=pack_id, tool_name=tool_name, root=root)

        # Smoke test the script exactly as it will run in production.
        from app.skill.pack_runner import smoke_run_script

        script_path = skill_dir / "scripts" / "main.py"
        smoke = await smoke_run_script(
            script_path=script_path,
            skill_dir=skill_dir,
            stdin_json=dict(draft.smoke_input or {}),
            network=bool(draft.needs_network) and "network" in granted,
        )

        smoke_ok = smoke.ok
        activate = smoke_ok and "script.python" in granted
        zip_bytes = zip_directory(root)

    result = await PackService(session).import_bytes(
        user_id=user_id,
        data=zip_bytes,
        grant_permissions=granted,
        activate=activate,
        replace_existing=True,
        origin="settle",
    )

    detail = result.pack
    reason = ""
    if not smoke_ok:
        reason = f"冒烟测试未通过：{smoke.error}" + (
            f"\n{smoke.stderr[:800]}" if smoke.stderr else ""
        )
    elif "script.python" not in granted:
        reason = "未授权 script.python，已装成待审。"

    return PackSettleResult(
        created=True,
        reusable=True,
        pack_id=detail.pack_id,
        pack_row_id=detail.id,
        status=detail.status,
        tool_count=detail.tool_count,
        validated=smoke_ok,
        activated=detail.status == "active",
        reason=reason,
        skill_ids=list(detail.skill_ids),
        warnings=list(result.warnings),
    )
