"""本地关键词兜底：jieba TF-IDF + Text，无需外部模型。"""

from __future__ import annotations

import re
from collections import Counter

import jieba
import jieba.analyse

from app.nexusmind.config import settings

# 常见技术停用词补充
_EXTRA_STOPWORDS = {
    "使用",
    "通过",
    "进行",
    "可以",
    "我们",
    "一个",
    "这个",
    "那个",
    "以及",
    "如果",
    "因为",
    "所以",
    "然后",
    "需要",
    "已经",
    "没有",
    "自己",
    "他们",
    "什么",
    "怎么",
    "如何",
    "一些",
    "或者",
    "还有",
    "不是",
    "只是",
    "就是",
    "问题",
    "方法",
    "内容",
    "文档",
    "笔记",
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "from",
    "your",
    "have",
    "will",
    "are",
    "was",
    "were",
    "been",
    "into",
    "also",
    "using",
    "use",
    "used",
}

_CATEGORY_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("Frontend", ("vue", "react", "angular", "css", "html", "typescript", "javascript", "pinia", "vite", "webpack", "前端")),
    ("Backend", ("fastapi", "django", "flask", "spring", "nestjs", "golang", "后端", "api", "sqlalchemy")),
    ("Database", ("mysql", "postgres", "sqlite", "redis", "mongodb", "数据库", "sql")),
    ("DevOps", ("docker", "kubernetes", "ci", "nginx", "linux", "部署", "运维")),
    ("AI", ("llm", "embedding", "prompt", "模型", "openai", "transformer", "机器学习", "深度学习")),
    ("Mobile", ("android", "ios", "flutter", "swift", "kotlin", "移动端")),
]


def extract_local_analysis(text: str, *, title: str = "") -> dict:
    """返回与 LLM 结果同构的结构。"""
    corpus = f"{title}\n{text}".strip()
    topk = settings.LOCAL_KEYWORD_TOPK

    if not corpus:
        return {
            "keywords": [],
            "category": "General",
            "summary": "",
            "search_keywords": [],
        }

    # jieba 首次调用会加载词典，稍慢但可接受
    tfidf = jieba.analyse.extract_tags(
        corpus, topK=topk, withWeight=True, allowPOS=("n", "nz", "vn", "eng", "x")
    )
    textrank = jieba.analyse.textrank(
        corpus, topK=topk, withWeight=True, allowPOS=("n", "nz", "vn", "eng")
    )

    scores: Counter[str] = Counter()
    display: dict[str, str] = {}

    for word, weight in tfidf:
        key = word.lower()
        if _should_skip(word):
            continue
        scores[key] += float(weight) * 1.0
        display[key] = word

    for word, weight in textrank:
        key = word.lower()
        if _should_skip(word):
            continue
        scores[key] += float(weight) * 1.15
        display.setdefault(key, word)

    # 英文技术词加权（连续大写/驼峰/带数字）
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{1,31}", corpus):
        if _should_skip(token):
            continue
        key = token.lower()
        scores[key] += 0.35
        display.setdefault(key, token)

    ranked = scores.most_common(topk)
    keywords = [display[k] for k, _ in ranked]
    weights = [(display[k], float(w)) for k, w in ranked]

    category = _guess_category(keywords, corpus)
    summary = _make_summary(text, title)

    return {
        "keywords": keywords,
        "keyword_weights": weights,
        "category": category,
        "summary": summary,
        "search_keywords": keywords[:],
    }


def _should_skip(word: str) -> bool:
    w = word.strip()
    if len(w) < 2:
        return True
    if w.lower() in _EXTRA_STOPWORDS:
        return True
    if re.fullmatch(r"[\d\W_]+", w):
        return True
    return False


def _guess_category(keywords: list[str], corpus: str) -> str:
    blob = " ".join(keywords + [corpus[:2000]]).lower()
    best = "General"
    best_score = 0
    for cat, hints in _CATEGORY_HINTS:
        score = sum(1 for h in hints if h.lower() in blob)
        if score > best_score:
            best_score = score
            best = cat
    return best


def _make_summary(text: str, title: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return title[:80] if title else ""
    # 取第一句或前 80 字
    for sep in ("。", "！", "？", ".", "!", "?"):
        if sep in cleaned[:160]:
            sentence = cleaned.split(sep, 1)[0].strip() + sep
            if len(sentence) >= 8:
                return sentence[:120]
    return cleaned[:80] + ("…" if len(cleaned) > 80 else "")
