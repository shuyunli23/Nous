"""Hybrid skill retrieval: vector similarity + keyword matching.

Pure vector search is unreliable on short queries like "GitLab SSH again",
which is exactly how people phrase a recurring problem. Keyword/intent hits
therefore contribute an additive boost, and the fused score is what gets
thresholded. Ranking then prefers skills with a proven success rate so a
validated skill wins over an untested one at similar relevance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.database.models import Skill
from app.database.models.enums import SkillStatus
from app.llm.embeddings import _tokenize  # noqa: PLC2701 - shared tokeniser
from app.memory.skill_memory import search_similar
from app.repositories.skill_repo import SkillRepository

logger = get_logger(__name__)


@dataclass
class RetrievedSkill:
    """A skill plus the scoring detail that got it selected."""

    skill: Skill
    score: float
    vector_similarity: float = 0.0
    keyword_score: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)

    def to_prompt_dict(self) -> dict[str, Any]:
        """Shape consumed by the prompt builder."""
        return {
            "id": self.skill.id,
            "name": self.skill.name,
            "description": self.skill.description,
            "instruction": self.skill.instruction,
            "trigger_intent": self.skill.trigger_intent,
            "workflow": self.skill.workflow or [],
            "examples": self.skill.examples or [],
            "tools": self.skill.tools or [],
            "similarity": round(self.score, 4),
        }


class SkillRetriever:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SkillRepository(session)

    async def retrieve(
        self,
        *,
        user_id: str,
        query: str,
        top_k: int | None = None,
        min_similarity: float | None = None,
        status: SkillStatus | None = SkillStatus.ACTIVE,
    ) -> list[RetrievedSkill]:
        """Return the best skills for a query, highest score first."""
        _top_k = top_k or settings.skill_top_k
        _min_sim = (
            min_similarity
            if min_similarity is not None
            else settings.skill_min_similarity
        )

        candidates = await self._candidate_skills(user_id, status)
        if not candidates:
            return []

        by_id = {skill.id: skill for skill in candidates}

        # ── vector leg ────────────────────────────────────────────────────
        hits = await search_similar(
            user_id=user_id,
            query=query,
            top_k=settings.skill_candidate_pool,
            status=status.value if status else None,
        )
        vector_scores = {
            hit.skill_id: hit.similarity for hit in hits if hit.skill_id in by_id
        }

        # ── keyword leg ───────────────────────────────────────────────────
        query_tokens = set(_tokenize(query))
        query_lower = query.lower()

        scored: list[RetrievedSkill] = []
        for skill in candidates:
            keyword_score, matched = _keyword_match(
                skill, query_lower, query_tokens
            )
            vector_similarity = vector_scores.get(skill.id, 0.0)

            # Fuse: vector similarity carries the base signal, keyword hits add
            # a bounded boost so a strong lexical match can clear the threshold
            # even when the embedding is weak (e.g. hash fallback provider).
            score = vector_similarity + keyword_score * settings.skill_keyword_boost
            if score <= 0.0:
                continue

            scored.append(
                RetrievedSkill(
                    skill=skill,
                    score=score,
                    vector_similarity=vector_similarity,
                    keyword_score=keyword_score,
                    matched_keywords=matched,
                )
            )

        selected = [item for item in scored if item.score >= _min_sim]
        selected.sort(key=_rank_key, reverse=True)
        selected = selected[:_top_k]

        logger.debug(
            "skills_retrieved",
            user_id=user_id,
            candidates=len(candidates),
            scored=len(scored),
            selected=len(selected),
            top=[
                (item.skill.name, round(item.score, 3)) for item in selected
            ],
        )
        return selected

    async def _candidate_skills(
        self, user_id: str, status: SkillStatus | None
    ) -> Sequence[Skill]:
        if status is SkillStatus.ACTIVE:
            return await self.repo.get_active_for_user(user_id)
        skills, _ = await self.repo.list_for_user(
            user_id, limit=500, offset=0, status=status
        )
        return skills


# ── scoring helpers ───────────────────────────────────────────────────────


def _keyword_match(
    skill: Skill, query_lower: str, query_tokens: set[str]
) -> tuple[float, list[str]]:
    """Score 0..1 from trigger keyword / intent / name overlap."""
    keywords = [kw for kw in (skill.trigger_keywords or []) if kw]
    matched: list[str] = []

    for keyword in keywords:
        keyword_lower = keyword.lower().strip()
        if not keyword_lower:
            continue
        # Substring hit covers multi-word keywords ("port 22", "ssh timeout").
        if keyword_lower in query_lower:
            matched.append(keyword)
            continue
        # Token overlap covers reordered or partially typed keywords.
        keyword_tokens = set(_tokenize(keyword_lower))
        if keyword_tokens and keyword_tokens <= query_tokens:
            matched.append(keyword)

    score = 0.0
    if keywords:
        score += len(matched) / len(keywords)

    # Name and intent overlap add a smaller, capped contribution.
    name_tokens = set(_tokenize(skill.name))
    if name_tokens:
        overlap = len(name_tokens & query_tokens) / len(name_tokens)
        score += overlap * 0.5

    if skill.trigger_intent:
        intent_tokens = set(_tokenize(skill.trigger_intent))
        if intent_tokens:
            overlap = len(intent_tokens & query_tokens) / len(intent_tokens)
            score += overlap * 0.3

    return min(score, 1.0), matched


def _rank_key(item: RetrievedSkill) -> tuple[float, float, int]:
    """Sort by fused score, then proven success, then usage volume.

    ``success_rate`` is None for unrated skills; 0.5 keeps them between proven
    failures and proven successes instead of pushing them to either extreme.
    """
    success_rate = item.skill.success_rate
    return (
        round(item.score, 6),
        success_rate if success_rate is not None else 0.5,
        item.skill.usage_count,
    )
