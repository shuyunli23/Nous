"""本地向量索引与语义检索。

实现策略（个人知识库友好、零额外重依赖）：
1. jieba 分词 + 特征哈希（Feature Hashing）得到固定维度单位向量
2. 向量存 SQLite（`knowledge_embedding`），余弦相似度 = 点积
3. 接口预留 remote embedding；当前默认 local_hash 始终可用

说明：规格中的 Milvus / Chroma 可作为后续后端适配器接入；
本阶段用 SQLite 向量表完成「语义检索」闭环。
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass

import jieba
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.nexusmind.config import settings
from app.nexusmind.models import Knowledge
from app.nexusmind.models.embedding import KnowledgeEmbedding
from app.nexusmind.services.knowledge_service import searchable_clause

logger = logging.getLogger(__name__)

# 变更分词/哈希策略时递增，迫使索引失效重建
EMBEDDING_VERSION = "local_hash_v2"

_STOP = {
    "的",
    "了",
    "和",
    "是",
    "在",
    "我",
    "有",
    "就",
    "不",
    "人",
    "都",
    "一",
    "一个",
    "上",
    "也",
    "很",
    "到",
    "说",
    "要",
    "去",
    "你",
    "会",
    "着",
    "没有",
    "看",
    "好",
    "自己",
    "这",
    "那",
    "与",
    "及",
    "或",
    "等",
    "并",
    "被",
    "把",
    "让",
    "从",
    "对",
    "为",
    "以",
    "而",
    "但",
    "如果",
    "因为",
    "所以",
    "可以",
    "这个",
    "那个",
    "什么",
    "怎么",
    "如何",
    "哪些",
    "一种",
    "以及",
    "进行",
    "使用",
    "通过",
    "我们",
    "他们",
    "它们",
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "is",
    "are",
    "was",
    "were",
    "be",
    "as",
    "at",
    "by",
    "with",
    "from",
    "this",
    "that",
    "it",
    "its",
}


@dataclass
class VectorHit:
    knowledge: Knowledge
    score: float
    snippet: str | None = None


def _content_fingerprint(text: str) -> str:
    payload = f"{EMBEDDING_VERSION}|{settings.EMBEDDING_DIM}|{text}"
    return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()


def _tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not cleaned:
        return []
    tokens: list[str] = []
    for tok in jieba.lcut(cleaned):
        t = tok.strip()
        if not t or t in _STOP:
            continue
        if len(t) == 1 and not t.isalnum():
            continue
        if t.isdigit():
            continue
        tokens.append(t)
        # 英文+版本号：Vue3 → 额外保留 vue，提升短查询召回
        m = re.match(r"([a-z][a-z0-9]*?[a-z])\d", t)
        if m:
            stem = m.group(1)
            if stem not in _STOP and len(stem) >= 2:
                tokens.append(stem)
    return tokens


def embed_text(text: str, *, dim: int | None = None) -> list[float]:
    """特征哈希嵌入，返回 L2 归一化向量。"""
    size = dim or settings.EMBEDDING_DIM
    vec = [0.0] * size
    tokens = _tokenize(text)
    # 极短查询被停用词滤空时，退回整句，避免语义检索永远 0 分
    if not tokens:
        raw = (text or "").strip().lower()
        if raw:
            tokens = [raw]
        else:
            return vec

    for tok in tokens:
        digest = hashlib.md5(tok.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % size
        sign = 1.0 if (int(digest[8:10], 16) % 2 == 0) else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 1e-12:
        return vec
    return [v / norm for v in vec]


def _doc_text(item: Knowledge) -> str:
    parts = [
        item.title or "",
        item.title or "",
        item.title or "",
        item.summary or "",
        item.category or "",
        " ".join(kw.name for kw in (item.keywords or [])),
        (item.plain_text or item.markdown_content or "")[:8000],
    ]
    return "\n".join(p for p in parts if p)


def cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return float(sum(a[i] * b[i] for i in range(n)))


def upsert_embedding(db: Session, knowledge_id: str) -> KnowledgeEmbedding | None:
    item = db.scalar(
        select(Knowledge)
        .options(selectinload(Knowledge.keywords))
        .where(Knowledge.id == knowledge_id)
    )
    if item is None:
        return None

    text = _doc_text(item)
    digest = _content_fingerprint(text)
    existing = db.scalar(
        select(KnowledgeEmbedding).where(KnowledgeEmbedding.knowledge_id == knowledge_id)
    )
    if existing and existing.content_hash == digest and existing.dim == settings.EMBEDDING_DIM:
        return existing

    vector = embed_text(text)
    if existing is None:
        existing = KnowledgeEmbedding(knowledge_id=knowledge_id)
        db.add(existing)

    existing.vector = vector
    existing.dim = settings.EMBEDDING_DIM
    existing.method = "local_hash"
    existing.content_hash = digest
    existing.model_name = "local:feature-hash"
    db.commit()
    db.refresh(existing)
    return existing


def delete_embedding(db: Session, knowledge_id: str) -> None:
    row = db.scalar(
        select(KnowledgeEmbedding).where(KnowledgeEmbedding.knowledge_id == knowledge_id)
    )
    if row is not None:
        db.delete(row)
        db.commit()


def rebuild_all(db: Session) -> dict[str, int]:
    ids = list(db.scalars(select(Knowledge.id)).all())
    id_set = set(ids)
    ok = 0
    for kid in ids:
        if upsert_embedding(db, kid) is not None:
            ok += 1
    # 清理孤儿
    all_rows = list(db.scalars(select(KnowledgeEmbedding)).all())
    orphan = [row for row in all_rows if row.knowledge_id not in id_set]
    for row in orphan:
        db.delete(row)
    if orphan:
        db.commit()
    return {"indexed": ok, "removed": len(orphan), "total_knowledge": len(ids)}


def ensure_index(db: Session) -> int:
    """若索引为空则全量重建；返回当前向量条数。"""
    count = len(list(db.scalars(select(KnowledgeEmbedding.id)).all()))
    knowledge_count = len(list(db.scalars(select(Knowledge.id)).all()))
    if knowledge_count and count < knowledge_count:
        rebuild_all(db)
        count = len(list(db.scalars(select(KnowledgeEmbedding.id)).all()))
    return count


def search_similar(
    db: Session,
    *,
    q: str,
    page: int = 1,
    page_size: int = 20,
    category: str | None = None,
    include_archived: bool = False,
    min_score: float | None = None,
) -> tuple[list[VectorHit], int, str]:
    query = (q or "").strip()
    if not query:
        from app.nexusmind.utils.errors import ValidationError

        raise ValidationError("请输入搜索词")

    ensure_index(db)
    q_vec = embed_text(query)
    threshold = min_score if min_score is not None else settings.VECTOR_MIN_SCORE

    rows = list(
        db.scalars(
            select(KnowledgeEmbedding).options(
                # 无 relationship，后续批量拉 Knowledge
            )
        ).all()
    )
    if not rows:
        return [], 0, "尚无向量索引，请先创建笔记或调用重建接口。"

    scored: list[tuple[str, float]] = []
    for row in rows:
        score = cosine(q_vec, row.vector or [])
        if score >= threshold:
            scored.append((row.knowledge_id, score))
    scored.sort(key=lambda x: -x[1])

    id_order = [kid for kid, _ in scored]
    if not id_order:
        return [], 0, "语义检索未命中（可降低阈值或改用 hybrid）。"

    filters = [Knowledge.id.in_(id_order), searchable_clause()]
    if not include_archived:
        filters.append(Knowledge.is_archived.is_(False))
    if category:
        filters.append(Knowledge.category == category.strip())

    items = list(
        db.scalars(
            select(Knowledge)
            .options(selectinload(Knowledge.keywords), selectinload(Knowledge.attachments))
            .where(*filters)
        ).all()
    )
    by_id = {i.id: i for i in items}
    score_map = dict(scored)

    hits: list[VectorHit] = []
    for kid in id_order:
        item = by_id.get(kid)
        if item is None:
            continue
        snippet = (item.summary or item.plain_text or "")[:160]
        if snippet and len(item.summary or item.plain_text or "") > 160:
            snippet += "…"
        hits.append(VectorHit(knowledge=item, score=round(score_map[kid] * 100, 2), snippet=snippet))

    total = len(hits)
    start = (page - 1) * page_size
    end = start + page_size
    note = "vector = 本地特征哈希语义检索（SQLite 向量表；可替换为 Chroma/Milvus）。"
    return hits[start:end], total, note


def top_k_for_assistant(db: Session, q: str, *, k: int = 6) -> list[VectorHit]:
    hits, _, _ = search_similar(db, q=q, page=1, page_size=k, min_score=0.02)
    return hits
