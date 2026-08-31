"""知识图谱构建：关键词 / 分类 / 知识条目关系。"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.nexusmind.models import Keyword, Knowledge
from app.nexusmind.models.associations import knowledge_keyword
from app.nexusmind.services.knowledge_service import searchable_clause


def build_knowledge_graph(
    db: Session,
    *,
    max_keywords: int = 48,
    max_knowledge: int = 60,
    min_keyword_usage: int = 1,
) -> dict:
    """返回前端可直接渲染的 nodes / edges。"""

    keywords = list(
        db.scalars(
            select(Keyword)
            .where(Keyword.usage_count >= min_keyword_usage)
            .order_by(Keyword.usage_count.desc(), Keyword.name.asc())
            .limit(max_keywords)
        ).all()
    )
    keyword_ids = {kw.id for kw in keywords}

    # 关联到这些关键词的知识
    links = list(
        db.execute(
            select(
                knowledge_keyword.c.knowledge_id,
                knowledge_keyword.c.keyword_id,
            ).where(knowledge_keyword.c.keyword_id.in_(keyword_ids or [""]))
        ).all()
    ) if keyword_ids else []

    knowledge_ids: list[str] = []
    seen_k: set[str] = set()
    for kid, _ in links:
        if kid in seen_k:
            continue
        seen_k.add(kid)
        knowledge_ids.append(kid)
        if len(knowledge_ids) >= max_knowledge:
            break

    items = []
    if knowledge_ids:
        items = list(
            db.scalars(
                select(Knowledge)
                .options(selectinload(Knowledge.keywords))
                .where(
                    Knowledge.id.in_(knowledge_ids),
                    Knowledge.is_archived.is_(False),
                    searchable_clause(),
                )
            ).all()
        )

    # 若关键词很少，补一批最近知识，保证图不空
    if not items:
        items = list(
            db.scalars(
                select(Knowledge)
                .options(selectinload(Knowledge.keywords))
                .where(Knowledge.is_archived.is_(False), searchable_clause())
                .order_by(Knowledge.updated_time.desc())
                .limit(max_knowledge)
            ).all()
        )
        # 从这些知识里取关键词
        kw_map: dict[str, Keyword] = {}
        for item in items:
            for kw in item.keywords or []:
                kw_map[kw.id] = kw
        keywords = sorted(kw_map.values(), key=lambda k: (-k.usage_count, k.name))[:max_keywords]
        keyword_ids = {kw.id for kw in keywords}

    item_ids = {i.id for i in items}

    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()

    def add_node(node_id: str, **payload: object) -> None:
        if node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append({"id": node_id, **payload})

    # 分类节点
    categories: dict[str, int] = defaultdict(int)
    for item in items:
        if item.category:
            categories[item.category] += 1

    for cat, count in categories.items():
        add_node(
            f"cat:{cat}",
            type="category",
            label=cat,
            weight=count,
            meta={"count": count},
        )

    for kw in keywords:
        add_node(
            f"kw:{kw.id}",
            type="keyword",
            label=kw.name,
            weight=max(1, kw.usage_count),
            meta={"usage_count": kw.usage_count, "slug": kw.slug},
        )

    for item in items:
        add_node(
            f"kn:{item.id}",
            type="knowledge",
            label=item.title,
            weight=1 + (2 if item.is_important else 0) + (1 if item.is_favorite else 0),
            meta={
                "knowledge_id": item.id,
                "category": item.category,
                "summary": (item.summary or "")[:120] or None,
            },
        )
        if item.category:
            edges.append(
                {
                    "id": f"e-cat-{item.id}",
                    "source": f"kn:{item.id}",
                    "target": f"cat:{item.category}",
                    "type": "in_category",
                    "weight": 1,
                }
            )
        for kw in item.keywords or []:
            if kw.id not in keyword_ids:
                continue
            edges.append(
                {
                    "id": f"e-kw-{item.id}-{kw.id}",
                    "source": f"kn:{item.id}",
                    "target": f"kw:{kw.id}",
                    "type": "has_keyword",
                    "weight": 1,
                }
            )

    # 关键词共现：共享同一知识的关键词连边
    cooccur: dict[tuple[str, str], int] = defaultdict(int)
    for item in items:
        ids = sorted(kw.id for kw in (item.keywords or []) if kw.id in keyword_ids)
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                cooccur[(a, b)] += 1

    for (a, b), w in sorted(cooccur.items(), key=lambda x: -x[1])[:80]:
        if w < 1:
            continue
        edges.append(
            {
                "id": f"e-co-{a}-{b}",
                "source": f"kw:{a}",
                "target": f"kw:{b}",
                "type": "co_occur",
                "weight": w,
            }
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "knowledge": len([n for n in nodes if n["type"] == "knowledge"]),
            "keyword": len([n for n in nodes if n["type"] == "keyword"]),
            "category": len([n for n in nodes if n["type"] == "category"]),
            "edges": len(edges),
            "knowledge_in_db": len(item_ids),
        },
    }
