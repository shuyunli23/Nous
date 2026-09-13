"""Mode-free conversation settle: propose kinds, then run the ones the user picked."""

from __future__ import annotations

import re
import time
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat_modes.catalog import COMPANION, TUTOR, WORKBENCH
from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.llm.client import structured_complete
from app.llm.prompts.extraction import format_conversation
from app.llm.prompts.settle import SETTLE_SYSTEM, SETTLE_USER
from app.memory.facts import LANE_PERSONA
from app.repositories.conversation_repo import ConversationRepository
from app.schemas.conversation import (
    NoteRef,
    SettleKind,
    SettleKindResult,
    SettleProposal,
    SettleProposalItem,
    SettleRunResult,
)
from app.services.conversation_service import ConversationService

logger = get_logger(__name__)

SETTLE_KINDS: tuple[SettleKind, ...] = ("skill", "knowledge", "persona", "pack")

_CONFIDENCE_TAIL = re.compile(r"\s*\(confidence=\d+(?:\.\d+)?\)\s*$", re.I)


def display_skill_reason(reason: str | None) -> str:
    """Turn extractor English skip lines into a short reason for the UI."""
    text = (reason or "").strip()
    if text.lower().startswith("not reusable:"):
        text = text.split(":", 1)[1].strip()
    text = _CONFIDENCE_TAIL.sub("", text).strip()
    if text.lower().startswith("too few messages"):
        return "对话还太短，不够抽成 Skill。"
    return text


def step_status(row: SettleKindResult) -> str:
    if row.error or (not row.ok and not row.skipped):
        return "error"
    if row.skipped:
        return "info"
    return "ok"


def step_title(base: str, row: SettleKindResult) -> str:
    status = step_status(row)
    if status == "error":
        return f"失败 · {base}"
    if status == "info":
        return f"未写入 · {base}"
    return f"已写入 · {base}"


class _SettleLLMItem(BaseModel):
    kind: Literal["skill", "knowledge", "persona", "pack"]
    recommended: bool = False
    confidence: float = 0.0
    reason: str = ""


class _SettleLLMResult(BaseModel):
    summary: str = ""
    items: list[_SettleLLMItem] = Field(default_factory=list)


def normalize_items(raw: list[_SettleLLMItem] | list[dict[str, Any]]) -> list[SettleProposalItem]:
    """Keep one row per kind, in a stable order."""
    by_kind: dict[str, SettleProposalItem] = {}
    for item in raw:
        data = item if isinstance(item, dict) else item.model_dump()
        kind = str(data.get("kind") or "").strip()
        if kind not in SETTLE_KINDS:
            continue
        try:
            confidence = max(0.0, min(1.0, float(data.get("confidence") or 0)))
        except (TypeError, ValueError):
            confidence = 0.0
        by_kind[kind] = SettleProposalItem(
            kind=kind,  # type: ignore[arg-type]
            recommended=bool(data.get("recommended")),
            confidence=confidence,
            reason=str(data.get("reason") or "").strip() or "无说明",
        )
    return [
        by_kind.get(
            kind,
            SettleProposalItem(
                kind=kind, recommended=False, confidence=0.0, reason="模型未评估这一项"
            ),
        )
        for kind in SETTLE_KINDS
    ]


def fallback_items(mode_key: str | None) -> list[SettleProposalItem]:
    """If analysis fails, use the conversation mode only as a weak hint."""
    key = (mode_key or "").strip()
    return [
        SettleProposalItem(
            kind="skill",
            recommended=key in {"", WORKBENCH},
            confidence=0.35 if key in {"", WORKBENCH} else 0.15,
            reason="分析失败，按工作台习惯提示 Skill。仍可改选。",
        ),
        SettleProposalItem(
            kind="knowledge",
            recommended=key == TUTOR,
            confidence=0.35 if key == TUTOR else 0.15,
            reason="分析失败，按学习习惯提示知识沉淀。仍可改选。",
        ),
        SettleProposalItem(
            kind="persona",
            recommended=key == COMPANION,
            confidence=0.35 if key == COMPANION else 0.15,
            reason="分析失败，按陪伴习惯提示偏好。仍可改选。",
        ),
        SettleProposalItem(
            kind="pack",
            recommended=False,
            confidence=0.1,
            reason="分析失败，默认不固化为工具。若对话产出了可运行代码可自行勾选。",
        ),
    ]


def _mode_label(conversation: Any) -> str:
    mode = getattr(conversation, "mode", None)
    if mode is None:
        return "未指定"
    name = str(getattr(mode, "name", "") or "").strip()
    key = str(getattr(mode, "key", "") or "").strip()
    if name and key:
        return f"{name}（{key}）"
    return name or key or "未指定"


async def _turns(session: AsyncSession, conversation_id: str) -> list[dict[str, str]]:
    repo = ConversationRepository(session)
    messages = await repo.list_messages(conversation_id)
    return [
        {"role": m.role, "content": m.content}
        for m in messages
        if m.role in {"user", "assistant"} and (m.content or "").strip()
    ]


async def propose_settle(
    session: AsyncSession,
    conversation_id: str,
    *,
    user_id: str,
) -> SettleProposal:
    conv_svc = ConversationService(session)
    conversation = await conv_svc.get_or_404(conversation_id, user_id=user_id)
    mode = getattr(conversation, "mode", None)
    mode_key = str(getattr(mode, "key", "") or "") or None
    mode_name = str(getattr(mode, "name", "") or "") or None
    turns = await _turns(session, conversation_id)
    if len(turns) < 2:
        return SettleProposal(
            conversation_id=conversation_id,
            title=conversation.title,
            mode_key=mode_key,
            mode_name=mode_name,
            summary="对话还太短，看不出该沉淀什么。可以先继续聊，或自己勾选后再试。",
            too_few=True,
            items=[
                SettleProposalItem(
                    kind=kind,
                    recommended=False,
                    confidence=0.0,
                    reason="消息太少，无法判断",
                )
                for kind in SETTLE_KINDS
            ],
        )

    text = format_conversation(turns)
    from app.llm.usage import PURPOSE_OTHER, usage_scope

    try:
        with usage_scope(
            purpose=PURPOSE_OTHER,
            user_id=user_id,
            conversation_id=conversation_id,
            session=session,
        ):
            parsed = await structured_complete(
                [
                    {"role": "system", "content": SETTLE_SYSTEM},
                    {
                        "role": "user",
                        "content": SETTLE_USER.format(
                            title=conversation.title or "未命名会话",
                            mode_label=_mode_label(conversation),
                            conversation_text=text,
                        ),
                    },
                ],
                _SettleLLMResult,
            )
        assert isinstance(parsed, _SettleLLMResult)
        items = normalize_items(parsed.items)
        summary = (parsed.summary or "").strip() or "已根据会话内容给出建议，请确认后开始沉淀。"
    except Exception as exc:  # noqa: BLE001
        logger.warning("settle_propose_failed", error=str(exc)[:200])
        items = fallback_items(mode_key)
        summary = "自动分析没有成功，下面按会话模式给了弱提示。请你自己勾选。"

    return SettleProposal(
        conversation_id=conversation_id,
        title=conversation.title,
        mode_key=mode_key,
        mode_name=mode_name,
        summary=summary,
        items=items,
    )


def _skill_detail(result: Any) -> str:
    if result.skill_id:
        return "已写入新 Skill。"
    if result.merged_into:
        return result.reason or "已合并到已有 Skill。"
    if result.skipped:
        return display_skill_reason(result.reason) or "这次没有可复用的 Skill，没有写入。"
    return display_skill_reason(result.reason) or "没有写入 Skill。"


def _knowledge_detail(notes: Any) -> str:
    parts: list[str] = []
    if notes.notes:
        parts.append(f"写入 {len(notes.notes)} 条待导入笔记。")
    if notes.memory_updated:
        parts.append("已更新知识基础。")
    if notes.skipped and not parts:
        return notes.reason or "没有可沉淀的知识。"
    if notes.reason and notes.skipped:
        parts.append(notes.reason)
    return " ".join(parts) or "知识沉淀完成。"


def _pack_detail(result: Any) -> str:
    if not result.reusable:
        return result.reason or "这次没有可固化成工具的可运行代码。"
    if result.activated:
        return f"已固化为工具并激活（{result.tool_count} 个工具），下一轮对话即可调用。"
    if result.created:
        return result.reason or "已装成待审（工具未启用）。"
    return result.reason or "没有生成工具。"


async def _run_kind(
    session: AsyncSession,
    *,
    conversation_id: str,
    user_id: str,
    kind: SettleKind,
    grant_permissions: list[str] | None = None,
) -> SettleKindResult:
    if kind == "skill":
        from app.services.skill_service import SkillService

        result = await SkillService(session).generate_from_conversation(
            conversation_id, user_id=user_id, force=True
        )
        return SettleKindResult(
            kind="skill",
            ok=not result.skipped or bool(result.skill_id or result.merged_into),
            skipped=result.skipped,
            reason=result.reason,
            skill_id=result.skill_id,
            merged_into=result.merged_into,
            detail=_skill_detail(result),
        )

    if kind == "knowledge":
        from app.services.note_extract_service import extract_tutor_notes

        notes = await extract_tutor_notes(
            session, conversation_id, user_id=user_id, force=True
        )
        return SettleKindResult(
            kind="knowledge",
            ok=not notes.skipped or notes.memory_updated or bool(notes.notes),
            skipped=notes.skipped and not notes.memory_updated,
            reason=notes.reason,
            notes=list(notes.notes),
            notes_skipped=notes.skipped,
            memory_updated=notes.memory_updated,
            detail=_knowledge_detail(notes),
        )

    if kind == "pack":
        from app.skill.pack_author import author_pack_from_conversation

        pack = await author_pack_from_conversation(
            session,
            conversation_id,
            user_id=user_id,
            granted_permissions=grant_permissions,
        )
        return SettleKindResult(
            kind="pack",
            ok=pack.created,
            skipped=not pack.created,
            reason=pack.reason or None,
            pack_id=pack.pack_id,
            pack_row_id=pack.pack_row_id,
            pack_status=pack.status,
            tool_count=pack.tool_count,
            validated=pack.validated,
            detail=_pack_detail(pack),
        )

    from app.services.memory_service import UserMemoryService

    updated = await UserMemoryService(session).update_from_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        lane=LANE_PERSONA,
    )
    return SettleKindResult(
        kind="persona",
        ok=True,
        skipped=not updated,
        memory_updated=updated,
        reason=None if updated else "nothing_to_save",
        detail="已更新相处档案。" if updated else "这次没有新的偏好可记。",
    )


def _validate_kinds(kinds: list[str]) -> list[SettleKind]:
    seen: list[SettleKind] = []
    for raw in kinds:
        kind = str(raw or "").strip()
        if kind not in SETTLE_KINDS:
            raise ValidationError(
                f"Unknown settle kind '{kind}'.",
                details={"kind": kind, "allowed": list(SETTLE_KINDS)},
            )
        if kind not in seen:
            seen.append(kind)  # type: ignore[arg-type]
    if not seen:
        raise ValidationError("Select at least one settle kind.")
    return seen


async def run_settle_events(
    session: AsyncSession,
    conversation_id: str,
    *,
    user_id: str,
    kinds: list[str],
    grant_permissions: list[str] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    selected = _validate_kinds(kinds)
    conv_svc = ConversationService(session)
    await conv_svc.get_or_404(conversation_id, user_id=user_id)

    titles = {
        "skill": "抽取 Skill",
        "knowledge": "沉淀知识",
        "persona": "记下偏好",
        "pack": "固化为工具",
    }
    trace: list[dict[str, Any]] = []
    results: list[SettleKindResult] = []

    for kind in selected:
        title = titles[kind]
        yield {
            "type": "step_start",
            "node": kind,
            "kind": "settle",
            "title": title,
            "status": "running",
        }
        started = time.perf_counter()
        try:
            row = await _run_kind(
                session,
                conversation_id=conversation_id,
                user_id=user_id,
                kind=kind,
                grant_permissions=grant_permissions,
            )
            status = step_status(row)
            title = step_title(title, row)
            detail = row.detail or row.reason or ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("settle_kind_failed", kind=kind, error=str(exc)[:200])
            row = SettleKindResult(
                kind=kind,
                ok=False,
                skipped=False,
                error=str(exc)[:300],
                detail=str(exc)[:300],
            )
            status = "error"
            title = step_title(title, row)
            detail = row.detail or "沉淀失败。"
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        results.append(row)
        trace.append(
            {
                "kind": "settle",
                "title": title,
                "status": status,
                "detail": detail,
                "elapsed_ms": elapsed_ms,
            }
        )
        yield {
            "type": "step_end",
            "node": kind,
            "kind": "settle",
            "title": title,
            "status": status,
            "detail": detail,
            "elapsed_ms": elapsed_ms,
            "execution_trace": list(trace),
        }

    payload = SettleRunResult(
        conversation_id=conversation_id,
        results=results,
    ).model_dump(mode="json")
    payload["type"] = "done"
    payload["execution_trace"] = list(trace)
    yield payload
