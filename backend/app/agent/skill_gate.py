"""Cheap heuristics: skip Skill retrieval when the turn is not a task."""

from __future__ import annotations

import re

_PUNCT = re.compile(r"[\s?？!！。.~…,，、'\"“”]+")

_GREETINGS = {
    "你好",
    "您好",
    "嗨",
    "哈喽",
    "早",
    "早上好",
    "晚上好",
    "在吗",
    "在不在",
    "hi",
    "hello",
    "hey",
    "yo",
    "谢谢",
    "感谢",
    "thanks",
    "thank you",
    "好的",
    "嗯",
    "嗯嗯",
    "ok",
    "okay",
    "哈哈",
}

_META = (
    "我问过",
    "我刚才",
    "我说过",
    "我说了",
    "你还记得",
    "还记得吗",
    "问了什么",
    "说了什么",
    "聊了什么",
    "问过你什么",
    "总结一下这",
    "回顾一下",
    "之前说",
    "试试什么",
)

_RETRY = (
    "再试试",
    "在试试",
    "再试一次",
    "再试下",
    "再试一下",
    "再来一次",
    "再来一张",
    "重新生成",
    "再画",
    "换一张",
    "换一个",
    "继续",
    "再说一次",
    "再做一次",
    "再生成",
)


def _normalize(query: str) -> str:
    return _PUNCT.sub("", (query or "").strip()).lower()


def is_retry_or_continue(query: str) -> bool:
    q = (query or "").strip().lower().rstrip("?？!！。.~…")
    if q in {"试试", "再试", "继续"}:
        return True
    return any(q == key or q.startswith(key) for key in _RETRY)


def is_recall_query(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    return any(key in q for key in _META)


def should_retrieve_skills(query: str) -> bool:
    """False for greetings, recap questions, and empty retry phrases."""
    q = (query or "").strip()
    if not q:
        return False
    if is_retry_or_continue(q) and not is_recall_query(q):
        return False
    if is_recall_query(q):
        return False
    compact = _normalize(q)
    if compact in _GREETINGS or compact in {item.lower() for item in _GREETINGS}:
        return False
    if len(compact) <= 6:
        return False
    return True
