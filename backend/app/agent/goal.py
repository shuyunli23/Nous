"""Infer this turn's goal and success criteria (Codex-style, no extra LLM call).

Nous is not a coding CLI. We only adapt Codex's habit of naming *what done
looks like* before the model is allowed to stop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote

from app.agent.artifacts import (
    code_requested,
    delivery_gaps,
    format_inspect_for_prompt,
    inspects_from_trace,
)
from app.agent.todo import unfinished_todos
from app.agent.tools.export_urls import EXPORT_URL_RE

ATTACH_START = "<!--nous-attachments-->"

_WEBPAGE_HINTS = (
    "demo",
    "网页",
    "h5",
    "汇报页",
    "在线演示",
    "briefing",
    "landing page",
    "webpage",
    "web page",
    "投屏",
    "给领导",
    "html页",
    "html 页",
)
_PPT_HINTS = ("ppt", "pptx", "幻灯片", "演示文稿", "powerpoint")
_PDF_GEN_HINTS = (
    "讲义",
    "生成pdf",
    "生成 pdf",
    "create pdf",
    "make a pdf",
    "make pdf",
    "pdf讲义",
    "教程文档",
    "学习资料",
    "export pdf",
    "写成pdf",
    "写成 pdf",
)
_IMAGE_HINTS = (
    "生成图片",
    "生成一张",
    "生成个图",
    "生成图像",
    "画一张",
    "画一个",
    "画个",
    "文生图",
    "generate image",
    "dall-e",
    "来一张图",
    "出一张图",
)
_PHOTO_ADD = ("加", "加上", "放", "截", "裁", "贴", "换", "补")
_PHOTO_NOUN = (
    "照片",
    "图像",
    "头像",
    "一寸",
    "证件照",
    "portrait",
    "headshot",
    "photo",
)
_CROP_HINTS = ("截", "裁剪", "裁下", "crop", "截取", "抠")


_SOURCE_HINTS = (
    "源码",
    "源代码",
    "source code",
    "html代码",
    "html 代码",
    "查看源码",
    "给我源码",
)


def wants_existing_source(goal: str) -> bool:
    text = (goal or "").lower()
    return any(key in text for key in _SOURCE_HINTS)


def wants_document_photo(goal: str) -> bool:
    """User wants a real photo already in an attachment, not a generated face."""
    text = (goal or "").lower()
    if not text.strip():
        return False
    if any(key in text for key in ("一寸", "证件照", "头像")):
        return True
    if ("求职者" in text or "简历里" in text) and any(
        key in text for key in _PHOTO_NOUN
    ):
        return True
    has_noun = any(key in text for key in _PHOTO_NOUN)
    has_add = any(key in text for key in _PHOTO_ADD)
    return has_noun and has_add


def wants_crop(goal: str) -> bool:
    text = (goal or "").lower()
    return wants_document_photo(text) and any(key in text for key in _CROP_HINTS)


def infer_required_tools(goal: str) -> list[str]:
    """Conservative artifact routing. Do not force search/weather on chit-chat."""
    text = (goal or "").lower()
    if not text.strip():
        return []

    required: list[str] = []
    if wants_existing_source(text):
        return []
    wants_ppt = any(key in text for key in _PPT_HINTS)
    wants_web = any(key in text for key in _WEBPAGE_HINTS)
    if wants_web:
        required.append("create_webpage")
    elif wants_ppt:
        required.append("create_presentation")
    if any(key in text for key in _PDF_GEN_HINTS):
        required.append("create_pdf")

    photo = wants_document_photo(text)
    if photo:
        if wants_crop(text):
            required.append("crop_image")
        if "create_webpage" not in required:
            required.append("create_webpage")
    elif any(key in text for key in _IMAGE_HINTS):
        required.append("generate_image")
    if code_requested(text) and "create_webpage" not in required:
        required.append("create_webpage")
    preferred = [
        "crop_image",
        "create_webpage",
        "create_presentation",
        "create_pdf",
        "generate_image",
    ]
    return [name for name in preferred if name in required] + [
        name for name in required if name not in preferred
    ]


def format_success_criteria(goal: str, required_tools: list[str]) -> str:
    if (
        not required_tools
        and not wants_document_photo(goal)
        and not code_requested(goal)
    ):
        return ""
    tools = ", ".join(required_tools) if required_tools else "(see photo rules)"
    clipped = (goal or "").strip().replace("\n", " ")
    if len(clipped) > 400:
        clipped = clipped[:399] + "…"
    lines = [
        "## This turn's success criteria",
        f"User goal: {clipped}",
        f"You MUST successfully call: {tools}",
        "Do not write a final answer until those tools return ok=true JSON.",
        "Paste download_url from the tool result verbatim. "
        "Never invent /api/v1/files/exports/ filenames.",
        "After create_webpage / create_presentation / create_pdf, read inspect in the tool JSON "
        "(image_count, hero_has_photo, has_code, empty_headings, headings, pages). That is what the file actually contains. "
        "You may only claim facts inspect confirms. If inspect contradicts the user goal, call the tool again.",
    ]
    if wants_document_photo(goal):
        lines += [
            "The webpage MUST actually contain the person's photo as an <img> "
            "(hero.image from PAPER FIGURES portrait or crop_image download_url).",
            "Forbidden: generate_image to invent a face. Forbidden: claiming the "
            "photo was added if inspect.image_count is 0.",
        ]
    if code_requested(goal):
        lines += [
            "The webpage MUST contain a real <pre> code block "
            "(layout=code with a multiline `code` string, indentation preserved).",
            "A heading 伪代码 with an empty body is NOT done. "
            "Forbidden: claiming pseudocode was added if inspect.has_code=false.",
        ]
    return "\n".join(lines)


def extract_goal_text(query: str, title_source: str | None = None) -> str:
    """User intent only — drop the attachment dump used for RAG/context."""
    raw = (title_source or query or "").strip()
    if ATTACH_START in raw:
        raw = raw.split(ATTACH_START, 1)[0].strip()
    if raw:
        return raw
    fallback = (query or "").strip()
    if ATTACH_START in fallback:
        fallback = fallback.split(ATTACH_START, 1)[0].strip()
    return fallback


def resolve_goal_text(
    query: str,
    *,
    history: list[dict[str, Any]] | None = None,
    title_source: str | None = None,
) -> str:
    """Use the current query, or the last actionable user turn on retry."""
    goal = extract_goal_text(query, title_source)
    if infer_required_tools(goal):
        return goal
    from app.agent.skill_gate import is_retry_or_continue

    if not is_retry_or_continue(query):
        return goal
    for msg in reversed(history or []):
        if msg.get("role") != "user":
            continue
        prev = extract_goal_text(str(msg.get("content") or ""))
        if infer_required_tools(prev):
            return prev
    return goal


def describe_plan(goal: str, required_tools: list[str]) -> str:
    clipped = (goal or "").strip().replace("\n", " ")
    if len(clipped) > 120:
        clipped = clipped[:119] + "…"
    tools = " → ".join(required_tools) if required_tools else "直接回答"
    return f"{clipped} · {tools}"


def successful_tools(trace: list[dict[str, Any]] | None) -> set[str]:
    names: set[str] = set()
    for step in trace or []:
        if step.get("kind") != "tool" or step.get("status") == "error":
            continue
        name = str(step.get("tool") or step.get("title") or "").strip()
        if name:
            names.add(name)
    return names


def failed_tools(trace: list[dict[str, Any]] | None) -> list[str]:
    ok = successful_tools(trace)
    seen: list[str] = []
    for step in trace or []:
        if step.get("kind") != "tool" or step.get("status") != "error":
            continue
        name = str(step.get("tool") or step.get("title") or "").strip()
        if name and name not in ok and name not in seen:
            seen.append(name)
    return seen


def successful_export_urls(trace: list[dict[str, Any]] | None) -> set[str]:
    urls: set[str] = set()
    for step in trace or []:
        if step.get("kind") != "tool" or step.get("status") == "error":
            continue
        urls.update(EXPORT_URL_RE.findall(str(step.get("detail") or "")))
    return urls


def invented_export_urls(
    response: str,
    trace: list[dict[str, Any]] | None,
    *,
    exports_dir,
) -> list[str]:
    """Export paths in the reply that this turn did not produce and are not on disk."""
    real = successful_export_urls(trace)
    found: list[str] = []
    for url in EXPORT_URL_RE.findall(response or ""):
        if url in real or url in found:
            continue
        name = unquote(url.rsplit("/", 1)[-1].split("?", 1)[0])
        if name and (exports_dir / name).is_file():
            continue
        found.append(url)
    return found


def webpage_has_embedded_image(trace: list[dict[str, Any]] | None, exports_dir) -> bool:
    urls = [
        url
        for step in (trace or [])
        if step.get("kind") == "tool"
        and step.get("tool") == "create_webpage"
        and step.get("status") != "error"
        for url in EXPORT_URL_RE.findall(str(step.get("detail") or ""))
        if url.lower().endswith(".html")
    ]
    if not urls:
        return False
    name = unquote(urls[-1].rsplit("/", 1)[-1].split("?", 1)[0])
    path = exports_dir / name
    if not path.is_file():
        return False
    html = path.read_text(encoding="utf-8", errors="ignore").lower()
    if "<img" not in html:
        return False
    return "data:image" in html or "/uploads/" in html or "src=" in html


def settle_todos(
    todos: list[dict[str, Any]] | None,
    trace: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Tick off checklist items an artifact already proves are done.

    A model that builds the deck and then forgets the closing ``todo_write``
    would otherwise leave the list forever open, and the turn could never
    verify. Real execution results outrank the model's self-report, so settle
    from the trace instead of trusting it to remember.
    """
    ok = successful_tools(trace)
    if not ok:
        return list(todos or [])
    settled: list[dict[str, Any]] = []
    for item in todos or []:
        entry = dict(item)
        if entry.get("status") != "completed":
            needs = infer_required_tools(str(entry.get("content") or ""))
            if needs and all(name in ok for name in needs):
                entry["status"] = "completed"
        settled.append(entry)
    return settled


def split_todos_by_evidence(
    todos: list[dict[str, Any]] | None,
    ok_tools: set[str],
) -> tuple[list[str], list[str]]:
    """Unfinished items, split into blocking and advisory.

    Blocking means the item names an artifact tool that has not succeeded --
    a gap the harness can actually see. Prose items like "整理提纲" name no
    tool, so nothing here can prove them either way; holding the turn hostage
    to those just burns retries, so they only earn a critique line.
    """
    blocking: list[str] = []
    advisory: list[str] = []
    for content in unfinished_todos(todos):
        needs = infer_required_tools(content)
        if needs and any(name not in ok_tools for name in needs):
            blocking.append(content)
        else:
            advisory.append(content)
    return blocking, advisory


@dataclass
class TurnVerdict:
    complete: bool
    missing_tools: list[str] = field(default_factory=list)
    failed_tools: list[str] = field(default_factory=list)
    invented_urls: list[str] = field(default_factory=list)
    missing_embedded_image: bool = False
    delivery_gaps: list[str] = field(default_factory=list)
    inspect_summary: str = ""
    open_todos: list[str] = field(default_factory=list)
    unverifiable_todos: list[str] = field(default_factory=list)
    truncated: bool = False

    def critique(self) -> str:
        lines = [
            "[internal verify — not a new user message]",
            "This turn is incomplete. Do not give a final answer yet.",
            "Do not claim the task is done.",
        ]
        if self.truncated:
            lines.append(
                "Your previous reply was cut off mid-stream by a network fault, "
                "not by you. Continue from exactly where it stops -- do not "
                "restart and do not repeat what you already wrote."
            )
        if self.inspect_summary:
            lines.append(self.inspect_summary)
        if self.open_todos:
            lines.append(
                "The standing todo list is not finished. Do the next item; "
                "do not write a final answer. Still open: "
                + "; ".join(self.open_todos[:8])
            )
        if self.unverifiable_todos:
            lines.append(
                "Also still unchecked (no artifact proves these, so mark them "
                "completed with todo_write once done): "
                + "; ".join(self.unverifiable_todos[:8])
            )
        if self.missing_tools:
            lines.append(
                "You MUST call these tools now: " + ", ".join(self.missing_tools)
            )
        if self.failed_tools:
            lines.append(
                "These tools failed; fix the arguments and retry: "
                + ", ".join(self.failed_tools)
            )
        if self.invented_urls:
            lines.append(
                "These download URLs were invented and do not exist: "
                + ", ".join(self.invented_urls)
                + ". Call the producing tool and paste its download_url verbatim."
            )
        for gap in self.delivery_gaps:
            lines.append(gap)
        if self.missing_embedded_image and not self.delivery_gaps:
            lines.append(
                "The webpage has no real photo <img>. Do NOT call generate_image "
                "to invent a face. Use a PAPER FIGURES portrait URL (kind=portrait) "
                "or crop_image, then create_webpage with hero.image set to that URL."
            )
        lines.append(
            "After tools return ok=true, write the user-facing reply. "
            "Never invent /api/v1/files/exports/ paths. "
            "Never claim inspect did not confirm."
        )
        return "\n".join(lines)


def evaluate_turn(
    *,
    required_tools: list[str],
    response: str,
    trace: list[dict[str, Any]] | None,
    exports_dir,
    must_embed_image: bool = False,
    goal_text: str = "",
    todos: list[dict[str, Any]] | None = None,
    pending_tool_names: list[str] | None = None,
    finish_reason: str = "",
) -> TurnVerdict:
    ok = successful_tools(trace)
    missing = [name for name in required_tools if name not in ok]
    failed = [name for name in failed_tools(trace) if name in required_tools]
    invented = invented_export_urls(response, trace, exports_dir=exports_dir)
    inspects = inspects_from_trace(trace)
    gaps = delivery_gaps(
        goal=goal_text,
        response=response or "",
        inspects=inspects,
    )
    if must_embed_image and not any("image_count=0" in g for g in gaps):
        from app.agent.artifacts import latest_inspect

        web = latest_inspect(inspects, "webpage")
        if not web or int(web.get("image_count") or 0) <= 0:
            gaps.append(
                "inspect.image_count=0 — the file has no <img>/picture. "
                "Do not say the photo was added. Put a real upload/crop URL on "
                "hero.image and rebuild."
            )
    missing_photo = any("image_count=0" in g or "hero_has_photo=false" in g for g in gaps)
    open_todos, unverifiable = split_todos_by_evidence(todos, ok)
    pending = [name for name in (pending_tool_names or []) if name]
    if pending:
        extra = [name for name in pending if name not in missing]
        missing.extend(extra)
    # A salvaged half-reply reads fluently, so nothing else here would catch it --
    # without this the turn would stop mid-sentence and call itself done.
    truncated = finish_reason == "interrupted"
    complete = (
        not missing
        and not failed
        and not invented
        and not gaps
        and not open_todos
        and not truncated
    )
    return TurnVerdict(
        complete=complete,
        truncated=truncated,
        missing_tools=missing,
        failed_tools=failed,
        invented_urls=invented,
        missing_embedded_image=missing_photo,
        delivery_gaps=gaps,
        inspect_summary=format_inspect_for_prompt(inspects),
        open_todos=open_todos,
        unverifiable_todos=unverifiable,
    )
