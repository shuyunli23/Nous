"""Markdown 解析服务。

Phase 2：抽取标题、目录树、纯文本、统计信息，写入 Knowledge.outline。
Phase 3 的前端渲染不依赖这里；这里只服务索引与元数据。
"""

from __future__ import annotations

import re
from typing import Any

from markdown_it import MarkdownIt
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

# 中文按字计、英文按词计的粗略阅读速度（字/分钟）
_READING_SPEED = 350

_md = (
    # linkify 需要额外依赖 linkify-it；解析大纲时不需要自动识别裸链接
    MarkdownIt("gfm-like", {"breaks": True, "linkify": False})
    .use(front_matter_plugin)
    .use(tasklists_plugin)
    .enable("table")
    .enable("strikethrough")
)


def parse_markdown(content: str, *, fallback_title: str = "未命名笔记") -> dict[str, Any]:
    """解析 Markdown，返回可用于落库的结构化结果。"""
    text = (content or "").lstrip("\ufeff")
    tokens = _md.parse(text)

    toc: list[dict[str, Any]] = []
    code_languages: list[str] = []
    counts = {
        "headings": 0,
        "code_blocks": 0,
        "images": 0,
        "links": 0,
        "tables": 0,
        "lists": 0,
        "task_items": 0,
        "blockquotes": 0,
    }

    title: str | None = None
    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token.type == "heading_open":
            level = int(token.tag[1]) if token.tag and token.tag.startswith("h") else 1
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            heading_text = inline.content.strip() if inline and inline.type == "inline" else ""
            counts["headings"] += 1
            toc.append({"level": level, "text": heading_text})
            if level == 1 and not title and heading_text:
                title = heading_text
            i += 1
            continue

        if token.type == "fence":
            counts["code_blocks"] += 1
            lang = (token.info or "").strip().split()[0] if token.info else ""
            if lang:
                code_languages.append(lang)
        elif token.type == "code_block":
            counts["code_blocks"] += 1
        elif token.type == "blockquote_open":
            counts["blockquotes"] += 1
        elif token.type in {"bullet_list_open", "ordered_list_open"}:
            counts["lists"] += 1
        elif token.type == "html_block" and "task-list-item" in (token.content or ""):
            counts["task_items"] += 1
        elif token.type == "table_open":
            counts["tables"] += 1

        if token.type == "inline" and token.children:
            for child in token.children:
                if child.type == "image":
                    counts["images"] += 1
                elif child.type == "link_open":
                    counts["links"] += 1

        # GFM task list: list item class 标记在 token.attrs
        if token.type == "list_item_open":
            classes = ""
            if token.attrs:
                classes = str(token.attrs.get("class", ""))
            if "task-list-item" in classes:
                counts["task_items"] += 1

        i += 1

    plain = extract_plain_text(text)
    word_count = count_words(plain)
    reading_minutes = max(1, round(word_count / _READING_SPEED)) if word_count else 0

    # 去重保序
    seen: set[str] = set()
    unique_langs: list[str] = []
    for lang in code_languages:
        key = lang.lower()
        if key not in seen:
            seen.add(key)
            unique_langs.append(lang)

    resolved_title = (title or fallback_title).strip() or fallback_title

    return {
        "title": resolved_title,
        "plain_text": plain,
        "word_count": word_count,
        "reading_minutes": reading_minutes,
        "outline": {
            "toc": toc,
            "code_languages": unique_langs,
            "counts": counts,
        },
    }


def extract_plain_text(markdown: str) -> str:
    """去掉常见 Markdown 语法，得到可用于检索的纯文本。"""
    text = markdown or ""
    # fenced code → 保留内容
    text = re.sub(r"```[\w+-]*\n([\s\S]*?)```", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # images / links
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # headings / quotes / lists / hr
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\-\*\+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # emphasis
    text = re.sub(r"[*_~]{1,3}", "", text)
    # html tags
    text = re.sub(r"<[^>]+>", "", text)
    # compress whitespace
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def count_words(plain: str) -> int:
    """中英混合字数：CJK 按字，其余按空白分词。"""
    if not plain:
        return 0
    cjk = re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", plain)
    latin = re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", plain)
    return len(cjk) + len(latin)


def guess_title_from_filename(filename: str | None) -> str:
    """从文件名推导默认标题。"""
    if not filename:
        return "未命名笔记"
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if name.lower().endswith(".md"):
        name = name[:-3]
    name = name.strip() or "未命名笔记"
    return name[:255]
