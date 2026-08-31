"""Skill management use cases."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.database.models.enums import SkillSource, SkillStatus
from app.memory.skill_memory import index_skill, reindex_user, remove_skill
from app.repositories.skill_repo import SkillRepository
from app.schemas.common import Page
from app.schemas.skill import (
    SkillCreate,
    SkillDetail,
    SkillImportItem,
    SkillImportResult,
    SkillPackImport,
    SkillSummary,
    SkillUpdate,
)
from app.skill.extractor import ExtractionResult, SkillExtractor
from app.skill.packs import get_builtin_pack
from app.skill.retriever import SkillRetriever

logger = get_logger(__name__)


class SkillService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SkillRepository(session)

    # ── CRUD ──────────────────────────────────────────────────────────────

    async def create(
        self, *, user_id: str, payload: SkillCreate
    ) -> SkillDetail:
        skill = await self.repo.create(
            user_id=user_id,
            name=payload.name,
            description=payload.description,
            instruction=payload.instruction,
            trigger_keywords=payload.trigger_keywords,
            trigger_intent=payload.trigger_intent,
            workflow=payload.workflow,
            examples=payload.examples,
            tools=payload.tools,
            confidence=payload.confidence,
            source=SkillSource.MANUAL,
            status=SkillStatus.ACTIVE,
        )
        await index_skill(self.session, skill)
        await self.session.commit()
        await self.session.refresh(skill)
        logger.info("skill_created_manual", skill_id=skill.id, name=skill.name)
        return SkillDetail.model_validate(skill)

    async def get_or_404(
        self, skill_id: str, *, user_id: str | None = None
    ) -> SkillDetail:
        skill = await self.repo.get(skill_id)
        if skill is None or (user_id is not None and skill.user_id != user_id):
            raise NotFoundError(
                f"Skill {skill_id} not found.",
                details={"skill_id": skill_id},
            )
        return SkillDetail.model_validate(skill)

    async def list_page(
        self,
        *,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        status: SkillStatus | None = None,
        search: str | None = None,
    ) -> Page[SkillSummary]:
        skills, total = await self.repo.list_for_user(
            user_id, limit=limit, offset=offset, status=status, search=search
        )
        items = [SkillSummary.model_validate(s) for s in skills]
        return Page[SkillSummary](
            items=items, total=total, limit=limit, offset=offset
        )

    async def update(
        self,
        skill_id: str,
        payload: SkillUpdate,
        *,
        user_id: str | None = None,
    ) -> SkillDetail:
        skill = await self.repo.get(skill_id)
        if skill is None or (user_id is not None and skill.user_id != user_id):
            raise NotFoundError(f"Skill {skill_id} not found.")

        changes: dict[str, Any] = {}
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                changes[field] = value

        if changes:
            await self.repo.update_fields(
                skill, changes, change_reason="manual edit"
            )
            await index_skill(self.session, skill)
            await self.session.commit()
            await self.session.refresh(skill)

        return SkillDetail.model_validate(skill)

    async def set_status(
        self,
        skill_id: str,
        status: SkillStatus,
        *,
        user_id: str | None = None,
    ) -> SkillDetail:
        skill = await self.repo.get(skill_id)
        if skill is None or (user_id is not None and skill.user_id != user_id):
            raise NotFoundError(f"Skill {skill_id} not found.")

        await self.repo.set_status(skill, status)
        # Keep vector index metadata in sync so status filter works at query time.
        await index_skill(self.session, skill)
        await self.session.commit()
        await self.session.refresh(skill)
        return SkillDetail.model_validate(skill)

    async def delete(
        self, skill_id: str, *, user_id: str | None = None
    ) -> None:
        skill = await self.repo.get(skill_id)
        if skill is None or (user_id is not None and skill.user_id != user_id):
            raise NotFoundError(f"Skill {skill_id} not found.")
        remove_skill(skill_id)   # drop from vector store before DB delete
        await self.repo.delete(skill)
        await self.session.commit()
        logger.info("skill_deleted", skill_id=skill_id)

    # ── Extraction ────────────────────────────────────────────────────────

    async def generate_from_conversation(
        self,
        conversation_id: str,
        *,
        user_id: str,
        force: bool = False,
    ) -> ExtractionResult:
        """Trigger skill extraction for a single conversation."""
        extractor = SkillExtractor(self.session)
        result = await extractor.extract(
            conversation_id, user_id=user_id, force=force
        )

        # Index whatever the extractor produced so it is retrievable immediately.
        target_id = result.skill_id or result.merged_into
        if target_id:
            skill = await self.repo.get(target_id)
            if skill is not None:
                await index_skill(self.session, skill)
                await self.session.commit()

        return result

    # ── Retrieval ─────────────────────────────────────────────────────────

    async def search(
        self,
        *,
        user_id: str,
        query: str,
        limit: int = 5,
        status: SkillStatus | None = SkillStatus.ACTIVE,
    ) -> list[dict[str, Any]]:
        """Debug/inspection endpoint for the hybrid retriever."""
        # None means caller did not specify; default to ACTIVE so disabled
        # skills are not mixed into normal search results.
        effective_status = status if status is not None else SkillStatus.ACTIVE
        retriever = SkillRetriever(self.session)
        results = await retriever.retrieve(
            user_id=user_id, query=query, top_k=limit, status=effective_status
        )
        return [
            {
                "id": item.skill.id,
                "name": item.skill.name,
                "description": item.skill.description,
                "status": item.skill.status,
                "score": round(item.score, 4),
                "vector_similarity": round(item.vector_similarity, 4),
                "keyword_score": round(item.keyword_score, 4),
                "matched_keywords": item.matched_keywords,
                "success_rate": item.skill.success_rate,
                "usage_count": item.skill.usage_count,
            }
            for item in results
        ]

    async def reindex(
        self, *, user_id: str, force: bool = False
    ) -> dict[str, int]:
        """Rebuild the vector index for one user from the database."""
        return await reindex_user(self.session, user_id, force=force)

    # ── Import packs ──────────────────────────────────────────────────────

    async def import_pack(
        self, *, user_id: str, payload: SkillPackImport
    ) -> SkillImportResult:
        """Import skills from a built-in pack id or an inline skill list."""
        pack_meta: dict[str, Any] | None = None
        items: list[SkillImportItem] = list(payload.skills)

        if payload.pack_id:
            pack_meta = get_builtin_pack(payload.pack_id)
            if pack_meta is None:
                raise NotFoundError(
                    f"Built-in pack '{payload.pack_id}' not found.",
                    details={"pack_id": payload.pack_id},
                )
            items = [SkillImportItem.model_validate(s) for s in pack_meta["skills"]]
        elif not items:
            raise ValidationError(
                "Provide pack_id or a non-empty skills list.",
                details={"hint": "GET /skills/packs for built-in packs"},
            )

        status = SkillStatus.ACTIVE if payload.activate else SkillStatus.DRAFT
        created: list[SkillSummary] = []
        skipped: list[str] = []

        for item in items:
            if payload.skip_duplicates:
                existing = await self.repo.find_similar_by_name(
                    user_id, item.name, threshold=0.95
                )
                if existing is not None:
                    skipped.append(item.name)
                    continue

            skill = await self.repo.create(
                user_id=user_id,
                name=item.name,
                description=item.description,
                instruction=item.instruction,
                trigger_keywords=item.trigger_keywords,
                trigger_intent=item.trigger_intent,
                workflow=item.workflow,
                examples=item.examples,
                tools=item.tools,
                confidence=item.confidence,
                source=SkillSource.IMPORTED,
                status=status,
            )
            await index_skill(self.session, skill)
            created.append(SkillSummary.model_validate(skill))

        await self.session.commit()
        pack_name = (
            (pack_meta or {}).get("name")
            or payload.name
            or (payload.pack_id if payload.pack_id else "custom")
        )
        logger.info(
            "skill_pack_imported",
            pack_id=payload.pack_id,
            created=len(created),
            skipped=len(skipped),
        )
        return SkillImportResult(
            pack_id=payload.pack_id,
            pack_name=pack_name,
            created=created,
            skipped=skipped,
            total_created=len(created),
            total_skipped=len(skipped),
        )

    # ── Feedback ──────────────────────────────────────────────────────────

    async def record_feedback(
        self,
        skill_id: str,
        *,
        user_id: str,
        positive: bool,
        message_id: str | None = None,
    ) -> None:
        """Record usage feedback. Auto-disable after repeated failures."""
        from app.core.config import settings
        await self.repo.increment_usage(skill_id, success=positive)
        if not positive:
            disabled = await self.repo.check_auto_disable(
                skill_id, threshold=settings.skill_auto_disable_failures
            )
            if disabled:
                logger.warning(
                    "skill_auto_disabled",
                    skill_id=skill_id,
                    reason="repeated_failures",
                )
        await self.session.commit()
