"""Skill Memory - keeps the vector index in sync with the skill table.

The embedded text is deliberately composed from the fields a user would phrase
their problem with (name, description, intent, keywords, workflow actions)
rather than the whole record: instruction text is guidance for the model, not
retrieval signal, and including it dilutes the vector.
"""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database.models import Skill
from app.llm.embeddings import content_hash, embed_text, embed_texts
from app.memory.vector_store import SearchHit, get_vector_store
from app.repositories.skill_repo import SkillRepository

logger = get_logger(__name__)


def build_embedding_text(skill: Skill) -> str:
    """Compose the text that represents a skill in vector space."""
    parts: list[str] = [skill.name, skill.description or ""]
    if skill.trigger_intent:
        parts.append(skill.trigger_intent)
    if skill.trigger_keywords:
        parts.append(" ".join(skill.trigger_keywords))
    for step in skill.workflow or []:
        if isinstance(step, dict):
            action = step.get("action")
            if action:
                parts.append(str(action))
    for example in (skill.examples or [])[:2]:
        if isinstance(example, dict):
            question = example.get("question")
            if question:
                parts.append(str(question))
    return "\n".join(part for part in parts if part).strip()


def _metadata(skill: Skill) -> dict[str, Any]:
    return {
        "user_id": skill.user_id,
        "status": skill.status,
        "name": skill.name,
        "version": skill.version,
    }


async def index_skill(session: AsyncSession, skill: Skill) -> bool:
    """Embed and upsert one skill. Returns False when the call failed."""
    text = build_embedding_text(skill)
    if not text:
        return False

    try:
        vector = await embed_text(text)
        get_vector_store().upsert(
            skill_id=skill.id, embedding=vector, metadata=_metadata(skill)
        )
    except Exception as exc:
        # Indexing must never break the caller's transaction (chat, extraction).
        logger.warning("skill_index_failed", skill_id=skill.id, error=str(exc))
        return False

    skill.embedding_hash = content_hash(text)
    await session.flush()
    logger.debug("skill_indexed", skill_id=skill.id, name=skill.name)
    return True


def remove_skill(skill_id: str) -> None:
    """Drop a skill from the vector index."""
    try:
        get_vector_store().delete(skill_id)
    except Exception as exc:
        logger.warning("skill_unindex_failed", skill_id=skill_id, error=str(exc))


async def search_similar(
    *,
    user_id: str,
    query: str,
    top_k: int,
    status: str | None = "active",
) -> list[SearchHit]:
    """Vector search restricted to one user (and optionally one status)."""
    try:
        vector = await embed_text(query)
    except Exception as exc:
        logger.warning("query_embedding_failed", error=str(exc))
        return []

    where: dict[str, Any] = {"user_id": user_id}
    if status:
        where["status"] = status

    try:
        return get_vector_store().query(
            embedding=vector, top_k=top_k, where=where
        )
    except Exception as exc:
        logger.warning("vector_query_failed", error=str(exc))
        return []


async def reindex_user(
    session: AsyncSession, user_id: str, *, force: bool = False
) -> dict[str, int]:
    """Rebuild vectors for every skill of one user.

    Skips rows whose ``embedding_hash`` still matches unless ``force`` is set,
    which keeps repeated calls cheap on a large library.
    """
    repo = SkillRepository(session)
    skills, _ = await repo.list_for_user(user_id, limit=1000, offset=0)

    pending: list[Skill] = []
    texts: list[str] = []
    skipped = 0

    for skill in skills:
        text = build_embedding_text(skill)
        if not text:
            skipped += 1
            continue
        if not force and skill.embedding_hash == content_hash(text):
            skipped += 1
            continue
        pending.append(skill)
        texts.append(text)

    indexed = 0
    failed = 0
    if pending:
        try:
            vectors = await embed_texts(texts)
        except Exception as exc:
            logger.warning("reindex_embedding_failed", error=str(exc))
            vectors = []

        if len(vectors) == len(pending):
            store = get_vector_store()
            for skill, vector, text in zip(pending, vectors, texts):
                try:
                    store.upsert(
                        skill_id=skill.id,
                        embedding=vector,
                        metadata=_metadata(skill),
                    )
                    skill.embedding_hash = content_hash(text)
                    indexed += 1
                except Exception as exc:
                    logger.warning(
                        "reindex_upsert_failed", skill_id=skill.id, error=str(exc)
                    )
                    failed += 1
            await session.flush()
            await session.commit()
        else:
            failed = len(pending)

    logger.info(
        "reindex_complete",
        user_id=user_id,
        indexed=indexed,
        skipped=skipped,
        failed=failed,
    )
    return {
        "indexed": indexed,
        "skipped": skipped,
        "failed": failed,
        "total": len(skills),
    }
