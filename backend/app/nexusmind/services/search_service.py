"""知识检索服务。

Phase 5：关键词索引优先 + 标题/摘要/正文补充（hybrid）。
Phase 7：mode=vector 走本地语义向量检索。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.nexusmind.config.features import FEATURES
from app.nexusmind.models import Keyword, Knowledge, normalize_keyword
from app.nexusmind.models.associations import knowledge_keyword
from app.nexusmind.services.knowledge_service import searchable_clause
from app.nexusmind.utils.errors import ValidationError


@dataclass
class ScoredHit:
    knowledge: Knowledge
    score: float = 0.0
    match_fields: set[str] = field(default_factory=set)
    matched_keywords: list[str] = field(default_factory=list)
    snippet: str | None = None


def search_knowledge(
    db: Session,
    *,
    q: str,
    mode: str = "hybrid",
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    include_archived: bool = False,
) -> tuple[list[ScoredHit], int, str | None]:
    query = (q or "").strip()
    if not query:
        raise ValidationError("请输入搜索关键词")
    if len(query) > 200:
        raise ValidationError("搜索词过长")

    if mode == "vector":
        if not FEATURES.get("vector_search"):
            raise ValidationError("语义检索尚未启用（vector_search）")
        from app.nexusmind.services import embedding_service

        vhits, total, note = embedding_service.search_similar(
            db,
            q=query,
            page=page,
            page_size=page_size,
            category=category,
            include_archived=include_archived,
        )
        scored = [
            ScoredHit(
                knowledge=h.knowledge,
                score=h.score,
                match_fields={"vector"},
                matched_keywords=[],
                snippet=h.snippet,
            )
            for h in vhits
        ]
        return scored, total, note

    if mode not in {"keyword", "fulltext", "hybrid"}:
        raise ValidationError(f"不支持的检索模式: {mode}")

    note: str | None = None
    if mode == "fulltext":
        note = "当前 fulltext 基于 SQLite LIKE；后续可接入 FTS5。"
    elif mode == "hybrid":
        note = "hybrid = 关键词索引加权 + 标题/摘要/正文匹配。"

    # 候选集：先按宽松条件拉出可能相关的知识，再在内存中精细打分
    # （个人知识库体量通常有限；百万级时再改成纯 SQL 排序）
    pattern = f"%{query}%"
    slug = normalize_keyword(query)

    filters = [searchable_clause()]
    if not include_archived:
        filters.append(Knowledge.is_archived.is_(False))
    if category:
        filters.append(Knowledge.category == category.strip())

    content_match = or_(
        Knowledge.title.ilike(pattern),
        Knowledge.summary.ilike(pattern),
        Knowledge.category.ilike(pattern),
        Knowledge.plain_text.ilike(pattern),
        Knowledge.markdown_content.ilike(pattern),
    )

    # 通过关键词表命中的 knowledge_id
    keyword_ids_subq = (
        select(knowledge_keyword.c.knowledge_id)
        .select_from(knowledge_keyword.join(Keyword, Keyword.id == knowledge_keyword.c.keyword_id))
        .where(
            or_(
                Keyword.slug == slug,
                Keyword.slug.ilike(pattern),
                Keyword.name.ilike(pattern),
            )
        )
    )

    if mode == "keyword":
        stmt = (
            select(Knowledge)
            .options(selectinload(Knowledge.keywords), selectinload(Knowledge.attachments))
            .where(Knowledge.id.in_(keyword_ids_subq), *filters)
        )
    elif mode == "fulltext":
        stmt = (
            select(Knowledge)
            .options(selectinload(Knowledge.keywords), selectinload(Knowledge.attachments))
            .where(content_match, *filters)
        )
    else:  # hybrid
        stmt = (
            select(Knowledge)
            .options(selectinload(Knowledge.keywords), selectinload(Knowledge.attachments))
            .where(or_(Knowledge.id.in_(keyword_ids_subq), content_match), *filters)
        )

    candidates = list(db.scalars(stmt).all())
    scored = [_score(item, query=query, slug=slug, mode=mode) for item in candidates]
    scored = [h for h in scored if h.score > 0]
    scored.sort(
        key=lambda h: (
            -h.score,
            -(h.knowledge.updated_time.timestamp() if h.knowledge.updated_time else 0),
        )
    )

    total = len(scored)
    start = (page - 1) * page_size
    end = start + page_size
    return scored[start:end], total, note


def _score(item: Knowledge, *, query: str, slug: str, mode: str) -> ScoredHit:
    hit = ScoredHit(knowledge=item)
    q_lower = query.lower()

    # ---- 关键词索引 ----
    if mode in {"keyword", "hybrid"}:
        for kw in item.keywords or []:
            kw_slug = kw.slug or normalize_keyword(kw.name)
            kw_name = (kw.name or "").lower()
            if kw_slug == slug or kw_name == q_lower:
                hit.score += 100
                hit.match_fields.add("keyword_exact")
                hit.matched_keywords.append(kw.name)
            elif slug in kw_slug or q_lower in kw_name or kw_slug in slug:
                hit.score += 60
                hit.match_fields.add("keyword")
                hit.matched_keywords.append(kw.name)

    # ---- 正文/元数据 ----
    if mode in {"fulltext", "hybrid"}:
        title = item.title or ""
        summary = item.summary or ""
        category = item.category or ""
        plain = item.plain_text or ""

        if query.lower() in title.lower():
            # 标题全等更高
            hit.score += 80 if title.lower() == q_lower else 45
            hit.match_fields.add("title")
        if summary and q_lower in summary.lower():
            hit.score += 25
            hit.match_fields.add("summary")
        if category and q_lower in category.lower():
            hit.score += 20
            hit.match_fields.add("category")
        if plain and q_lower in plain.lower():
            hit.score += 15
            hit.match_fields.add("content")
            hit.snippet = _make_snippet(plain, query)

    # 收藏/重要轻微加权，便于个人复用
    if item.is_important:
        hit.score += 3
    if item.is_favorite:
        hit.score += 2

    # 去重 matched keywords
    seen: set[str] = set()
    uniq: list[str] = []
    for name in hit.matched_keywords:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(name)
    hit.matched_keywords = uniq

    if not hit.snippet and "title" in hit.match_fields:
        hit.snippet = (item.summary or item.plain_text or "")[:160]

    return hit


def _make_snippet(text: str, query: str, *, radius: int = 60) -> str:
    lowered = text.lower()
    q = query.lower()
    idx = lowered.find(q)
    if idx < 0:
        return text[:160] + ("…" if len(text) > 160 else "")
    start = max(0, idx - radius)
    end = min(len(text), idx + len(query) + radius)
    snippet = text[start:end].replace("\n", " ")
    snippet = re.sub(r"\s+", " ", snippet).strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


def list_hot_keywords(db: Session, *, limit: int = 20) -> list[tuple[Keyword, str | None]]:
    """按 usage_count 返回热门关键词，附带一篇样例标题。"""
    keywords = list(
        db.scalars(
            select(Keyword)
            .where(Keyword.usage_count > 0)
            .order_by(Keyword.usage_count.desc(), Keyword.updated_time.desc())
            .limit(limit)
        ).all()
    )
    result: list[tuple[Keyword, str | None]] = []
    for kw in keywords:
        title = db.scalar(
            select(Knowledge.title)
            .select_from(knowledge_keyword.join(Knowledge, Knowledge.id == knowledge_keyword.c.knowledge_id))
            .where(
                knowledge_keyword.c.keyword_id == kw.id,
                Knowledge.is_archived.is_(False),
                searchable_clause(),
            )
            .order_by(Knowledge.updated_time.desc())
            .limit(1)
        )
        result.append((kw, title))
    return result


def suggest_keywords(db: Session, *, q: str, limit: int = 12) -> list[Keyword]:
    query = (q or "").strip()
    if not query:
        return [
            k
            for k, _ in list_hot_keywords(db, limit=limit)
        ]
    pattern = f"%{query}%"
    return list(
        db.scalars(
            select(Keyword)
            .where(or_(Keyword.name.ilike(pattern), Keyword.slug.ilike(pattern)))
            .order_by(Keyword.usage_count.desc(), Keyword.name.asc())
            .limit(limit)
        ).all()
    )


def knowledge_ids_by_keyword(db: Session, keyword_id: str) -> list[str]:
    rows = db.scalars(
        select(knowledge_keyword.c.knowledge_id).where(
            knowledge_keyword.c.keyword_id == keyword_id
        )
    ).all()
    return list(rows)
