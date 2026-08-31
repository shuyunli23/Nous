"""关键词实体与知识绑定。"""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.nexusmind.models import Keyword, normalize_keyword
from app.nexusmind.models.associations import knowledge_keyword


def get_or_create_keyword(db: Session, name: str) -> Keyword:
    display = " ".join(name.strip().split())
    if not display:
        raise ValueError("关键词不能为空")
    slug = normalize_keyword(display)[:64]
    existing = db.scalar(select(Keyword).where(Keyword.slug == slug))
    if existing:
        return existing
    item = Keyword(name=display[:64], slug=slug, usage_count=0)
    db.add(item)
    db.flush()
    return item


def replace_knowledge_keywords(
    db: Session,
    knowledge_id: str,
    keywords: list[tuple[str, float]],
    *,
    source: str,
) -> list[Keyword]:
    """用新关键词集替换该知识上 source 为 ai/local 的自动标签。

    `keywords`: (name, weight)
    保留 source=manual 的人工标注（Phase 后续可用）。
    """
    # 查出旧的自动关联
    old_rows = db.execute(
        select(knowledge_keyword.c.keyword_id, knowledge_keyword.c.source).where(
            knowledge_keyword.c.knowledge_id == knowledge_id,
            knowledge_keyword.c.source.in_(("ai", "local")),
        )
    ).all()
    old_ids = [row.keyword_id for row in old_rows]

    if old_ids:
        db.execute(
            delete(knowledge_keyword).where(
                knowledge_keyword.c.knowledge_id == knowledge_id,
                knowledge_keyword.c.source.in_(("ai", "local")),
            )
        )
        # 引用计数回退
        for kid in old_ids:
            db.execute(
                update(Keyword)
                .where(Keyword.id == kid, Keyword.usage_count > 0)
                .values(usage_count=Keyword.usage_count - 1)
            )

    bound: list[Keyword] = []
    seen: set[str] = set()
    for raw_name, weight in keywords:
        name = (raw_name or "").strip()
        if not name:
            continue
        slug = normalize_keyword(name)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        kw = get_or_create_keyword(db, name)
        db.execute(
            knowledge_keyword.insert().values(
                knowledge_id=knowledge_id,
                keyword_id=kw.id,
                weight=float(weight),
                source=source,
            )
        )
        kw.usage_count = int(kw.usage_count or 0) + 1
        bound.append(kw)

    db.flush()
    return bound
