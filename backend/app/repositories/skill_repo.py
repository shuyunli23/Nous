"""Data access for skills and skill versions."""

from __future__ import annotations

import json
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import utcnow
from app.database.models import Skill, SkillVersion
from app.database.models.enums import SkillSource, SkillStatus


class SkillRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── CRUD ──────────────────────────────────────────────────────────────

    async def create(
        self,
        *,
        user_id: str,
        name: str,
        description: str = "",
        instruction: str = "",
        trigger_keywords: list[str] | None = None,
        trigger_intent: str | None = None,
        workflow: list[dict[str, Any]] | None = None,
        examples: list[dict[str, Any]] | None = None,
        tools: list[str] | None = None,
        confidence: float = 0.0,
        source: SkillSource = SkillSource.AUTO,
        status: SkillStatus = SkillStatus.DRAFT,
        created_from_conversation_id: str | None = None,
    ) -> Skill:
        skill = Skill(
            user_id=user_id,
            name=name,
            description=description,
            instruction=instruction,
            trigger_keywords=trigger_keywords or [],
            trigger_intent=trigger_intent,
            workflow=workflow or [],
            examples=examples or [],
            tools=tools or [],
            confidence=confidence,
            source=source,
            status=status,
            version=1,
            created_from_conversation_id=created_from_conversation_id,
        )
        self.session.add(skill)
        await self.session.flush()
        # Write initial version snapshot.
        await self._snapshot(skill, change_reason="initial")
        return skill

    async def get(self, skill_id: str) -> Skill | None:
        result = await self.session.execute(
            select(Skill).where(Skill.id == skill_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        status: SkillStatus | None = None,
        search: str | None = None,
    ) -> tuple[Sequence[Skill], int]:
        stmt = select(Skill).where(Skill.user_id == user_id)
        count_stmt = select(func.count(Skill.id)).where(Skill.user_id == user_id)

        if status is not None:
            stmt = stmt.where(Skill.status == status.value)
            count_stmt = count_stmt.where(Skill.status == status.value)
        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(
                func.lower(Skill.name).like(pattern)
                | func.lower(Skill.description).like(pattern)
            )
            count_stmt = count_stmt.where(
                func.lower(Skill.name).like(pattern)
                | func.lower(Skill.description).like(pattern)
            )

        stmt = stmt.order_by(Skill.updated_at.desc()).limit(limit).offset(offset)
        skills = (await self.session.execute(stmt)).scalars().all()
        total = int((await self.session.execute(count_stmt)).scalar_one())
        return skills, total

    async def get_active_for_user(self, user_id: str) -> Sequence[Skill]:
        """All active skills for keyword-based pre-filtering."""
        result = await self.session.execute(
            select(Skill).where(
                Skill.user_id == user_id,
                Skill.status == SkillStatus.ACTIVE.value,
            )
        )
        return result.scalars().all()

    async def delete(self, skill: Skill) -> None:
        await self.session.delete(skill)

    # ── Updates ───────────────────────────────────────────────────────────

    async def update_fields(
        self, skill: Skill, changes: dict[str, Any], *, change_reason: str = "edit"
    ) -> Skill:
        """Apply field changes, bump version, snapshot."""
        for field, value in changes.items():
            setattr(skill, field, value)
        skill.version += 1
        skill.updated_at = utcnow()
        await self.session.flush()
        await self._snapshot(skill, change_reason=change_reason)
        return skill

    async def set_status(self, skill: Skill, status: SkillStatus) -> Skill:
        skill.status = status.value
        skill.updated_at = utcnow()
        await self.session.flush()
        return skill

    async def increment_usage(
        self, skill_id: str, *, success: bool | None = None
    ) -> None:
        skill = await self.get(skill_id)
        if skill is None:
            return
        skill.usage_count += 1
        skill.last_used_at = utcnow()
        if success is True:
            skill.success_count += 1
        elif success is False:
            skill.failure_count += 1
        await self.session.flush()

    async def check_auto_disable(
        self, skill_id: str, threshold: int
    ) -> bool:
        """Disable skill if consecutive failures exceed threshold. Returns True if disabled."""
        from app.core.config import settings as cfg
        skill = await self.get(skill_id)
        if skill is None:
            return False
        if skill.failure_count >= threshold and skill.status == SkillStatus.ACTIVE.value:
            skill.status = SkillStatus.DISABLED.value
            skill.updated_at = utcnow()
            await self.session.flush()
            return True
        return False

    # ── Deduplication ────────────────────────────────────────────────────

    async def find_similar_by_name(
        self, user_id: str, name: str, threshold: float = 0.8
    ) -> Skill | None:
        """Simple keyword-overlap deduplication before vector search is available.

        Jaccard similarity on lowercased word sets.  Phase 4 replaces this with
        vector cosine similarity once Chroma is wired in.
        """
        candidates = await self.get_active_for_user(user_id)
        candidates_all = list(candidates)
        # also check drafts
        draft_result = await self.session.execute(
            select(Skill).where(
                Skill.user_id == user_id,
                Skill.status == SkillStatus.DRAFT.value,
            )
        )
        candidates_all += list(draft_result.scalars().all())

        words_new = set(name.lower().split())
        best: Skill | None = None
        best_sim = 0.0
        for skill in candidates_all:
            words_existing = set(skill.name.lower().split())
            union = words_new | words_existing
            if not union:
                continue
            sim = len(words_new & words_existing) / len(union)
            if sim > best_sim:
                best_sim = sim
                best = skill
        if best_sim >= threshold:
            return best
        return None

    # ── Versions ──────────────────────────────────────────────────────────

    async def _snapshot(self, skill: Skill, *, change_reason: str) -> SkillVersion:
        snapshot = {
            "name": skill.name,
            "description": skill.description,
            "instruction": skill.instruction,
            "trigger_keywords": skill.trigger_keywords,
            "trigger_intent": skill.trigger_intent,
            "workflow": skill.workflow,
            "examples": skill.examples,
            "tools": skill.tools,
            "confidence": skill.confidence,
            "status": skill.status,
        }
        version_row = SkillVersion(
            skill_id=skill.id,
            version=skill.version,
            snapshot=snapshot,
            change_reason=change_reason,
        )
        self.session.add(version_row)
        await self.session.flush()
        return version_row
