"""知识 <-> 关键词 的关联表。

需求文档里写的是 `Knowledge 1 --- N Keyword`，但第 4 节又要求
「关键词绑定多个笔记 / 一个笔记多个关键词」，本质上是多对多。
这里采用带附加列的关联表，既满足检索需求，又能记录关键词的来源和权重。
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Table

from app.nexusmind.db.base import Base, utcnow

knowledge_keyword = Table(
    "knowledge_keyword",
    Base.metadata,
    Column(
        "knowledge_id",
        String(32),
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "keyword_id",
        String(32),
        ForeignKey("keyword.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    # 关键词权重（TF-IDF / TextRank 得分，或 LLM 给出的置信度），用于搜索排序
    Column("weight", Float, nullable=False, default=1.0),
    # 来源：ai / local / manual，便于区分自动生成与人工标注
    Column("source", String(16), nullable=False, default="local"),
    Column("created_time", DateTime(timezone=True), nullable=False, default=utcnow),
)
