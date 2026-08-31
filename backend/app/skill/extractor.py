"""Skill Extractor - the core of the long-term memory pipeline.

Chain:
  1. load messages from DB
  2. judge reusability  (structured LLM call → ReusabilityResult)
  3. if reusable: draft skill  (structured LLM call → SkillDraft)
  4. dedupe against existing skills
  5. persist (create or merge into existing)
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.database.models.enums import (
    ExtractionStatus,
    SkillSource,
    SkillStatus,
)
from app.llm.client import Message, structured_complete
from app.llm.prompts.extraction import (
    REUSABILITY_JUDGE_SYSTEM,
    REUSABILITY_JUDGE_USER,
    SKILL_DRAFT_SYSTEM,
    SKILL_DRAFT_USER,
    format_conversation,
)
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.skill_repo import SkillRepository

logger = get_logger(__name__)


# ── LLM output schemas ────────────────────────────────────────────────────

class ReusabilityResult(BaseModel):
    reusable: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class WorkflowStepDraft(BaseModel):
    step: int = 1
    action: str = ""
    command: str | None = None
    expect: str | None = None


class ExampleDraft(BaseModel):
    question: str = ""
    solution: str = ""


class SkillDraft(BaseModel):
    name: str = ""
    description: str = ""
    instruction: str = ""
    trigger_keywords: list[str] = Field(default_factory=list)
    trigger_intent: str = ""
    workflow: list[dict[str, Any]] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


# ── Result dataclass ────────────────────────────────────────────────────

class ExtractionResult(BaseModel):
    conversation_id: str
    extraction_status: str
    skill_id: str | None = None
    merged_into: str | None = None
    skipped: bool = False
    reason: str | None = None


# ── Main extractor ───────────────────────────────────────────────────────

class SkillExtractor:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conv_repo = ConversationRepository(session)
        self.skill_repo = SkillRepository(session)

    async def extract(
        self,
        conversation_id: str,
        *,
        user_id: str,
        force: bool = False,
    ) -> ExtractionResult:
        """Run the full extraction chain for one conversation."""

        # ── guard: fetch conversation ────────────────────────────────────
        conv = await self.conv_repo.get(conversation_id)
        if conv is None:
            return ExtractionResult(
                conversation_id=conversation_id,
                extraction_status=ExtractionStatus.FAILED,
                skipped=True,
                reason="Conversation not found.",
            )

        if not force and conv.extraction_status == ExtractionStatus.DONE:
            return ExtractionResult(
                conversation_id=conversation_id,
                extraction_status=ExtractionStatus.DONE,
                skipped=True,
                reason="Already extracted.",
            )

        # mark running
        await self.conv_repo.set_extraction_status(
            conv, ExtractionStatus.RUNNING
        )
        await self.session.commit()

        try:
            result = await self._run_chain(conv, user_id=user_id)
        except Exception as exc:
            logger.exception(
                "extraction_failed", conversation_id=conversation_id, error=str(exc)
            )
            await self.conv_repo.set_extraction_status(
                conv, ExtractionStatus.FAILED, error=str(exc)[:500]
            )
            await self.session.commit()
            return ExtractionResult(
                conversation_id=conversation_id,
                extraction_status=ExtractionStatus.FAILED,
                reason=str(exc),
            )

        await self.session.commit()
        return result

    # ── private chain ────────────────────────────────────────────────────

    async def _run_chain(self, conv: Any, *, user_id: str) -> ExtractionResult:
        cid = conv.id

        # 1. load messages
        messages = await self.conv_repo.list_messages(cid)
        user_assistant = [
            m for m in messages if m.role in {"user", "assistant"}
        ]

        if len(user_assistant) < settings.extraction_min_messages:
            await self.conv_repo.set_extraction_status(
                conv, ExtractionStatus.SKIPPED
            )
            return ExtractionResult(
                conversation_id=cid,
                extraction_status=ExtractionStatus.SKIPPED,
                skipped=True,
                reason=f"Too few messages ({len(user_assistant)} < {settings.extraction_min_messages}).",
            )

        conv_text = format_conversation(
            [{"role": m.role, "content": m.content} for m in user_assistant]
        )

        from app.llm.usage import PURPOSE_SKILL, usage_scope

        skill_scope = dict(
            purpose=PURPOSE_SKILL,
            user_id=user_id,
            conversation_id=cid,
            session=self.session,
        )

        # 2. judge reusability
        judge_msgs: list[Message] = [
            {"role": "system", "content": REUSABILITY_JUDGE_SYSTEM},
            {
                "role": "user",
                "content": REUSABILITY_JUDGE_USER.format(
                    conversation_text=conv_text,
                    message_count=len(user_assistant),
                ),
            },
        ]
        with usage_scope(**skill_scope):
            judgment: ReusabilityResult = await structured_complete(
                judge_msgs, ReusabilityResult
            )
        logger.info(
            "reusability_judged",
            conversation_id=cid,
            reusable=judgment.reusable,
            confidence=judgment.confidence,
            reason=judgment.reason,
        )

        if not judgment.reusable or judgment.confidence < settings.extraction_min_confidence:
            await self.conv_repo.set_extraction_status(
                conv, ExtractionStatus.SKIPPED
            )
            return ExtractionResult(
                conversation_id=cid,
                extraction_status=ExtractionStatus.SKIPPED,
                skipped=True,
                reason=f"Not reusable: {judgment.reason} (confidence={judgment.confidence:.2f})",
            )

        # 3. draft skill
        draft_msgs: list[Message] = [
            {"role": "system", "content": SKILL_DRAFT_SYSTEM},
            {
                "role": "user",
                "content": SKILL_DRAFT_USER.format(conversation_text=conv_text),
            },
        ]
        with usage_scope(**skill_scope):
            draft: SkillDraft = await structured_complete(draft_msgs, SkillDraft)
        logger.info("skill_drafted", conversation_id=cid, name=draft.name)

        # 4. deduplicate
        similar = await self.skill_repo.find_similar_by_name(
            user_id, draft.name, threshold=settings.extraction_dedupe_threshold
        )
        if similar is not None:
            # Merge: add the conversation as a new example on the existing skill.
            existing_examples = list(similar.examples or [])
            for ex in draft.examples:
                ex["conversation_id"] = cid
                existing_examples.append(ex)
            changes: dict[str, Any] = {"examples": existing_examples}
            # Optionally raise confidence if new draft is higher.
            if draft.trigger_keywords:
                kw_set = set(similar.trigger_keywords or []) | set(
                    draft.trigger_keywords
                )
                changes["trigger_keywords"] = list(kw_set)
            await self.skill_repo.update_fields(
                similar, changes, change_reason=f"merged from conversation {cid}"
            )
            await self.conv_repo.set_extraction_status(
                conv, ExtractionStatus.DONE
            )
            logger.info(
                "skill_merged", skill_id=similar.id, conversation_id=cid
            )
            return ExtractionResult(
                conversation_id=cid,
                extraction_status=ExtractionStatus.DONE,
                merged_into=similar.id,
                reason=f"Merged into existing skill '{similar.name}'.",
            )

        # 5. create new skill
        status = (
            SkillStatus.ACTIVE
            if settings.extraction_auto_activate
            else SkillStatus.DRAFT
        )
        examples_with_cid = []
        for ex in draft.examples:
            ex_copy = dict(ex)
            ex_copy["conversation_id"] = cid
            examples_with_cid.append(ex_copy)

        skill = await self.skill_repo.create(
            user_id=user_id,
            name=draft.name,
            description=draft.description,
            instruction=draft.instruction,
            trigger_keywords=draft.trigger_keywords,
            trigger_intent=draft.trigger_intent,
            workflow=draft.workflow,
            examples=examples_with_cid,
            tools=draft.tools,
            confidence=judgment.confidence,
            source=SkillSource.AUTO,
            status=status,
            created_from_conversation_id=cid,
        )
        await self.conv_repo.set_extraction_status(
            conv, ExtractionStatus.DONE
        )
        logger.info(
            "skill_created",
            skill_id=skill.id,
            name=skill.name,
            status=skill.status,
            conversation_id=cid,
        )
        return ExtractionResult(
            conversation_id=cid,
            extraction_status=ExtractionStatus.DONE,
            skill_id=skill.id,
        )
