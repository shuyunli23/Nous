"""Concrete tool implementations."""

from __future__ import annotations

import ast
import json
import operator
import re
import uuid
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_UA = (
    "NousAgent/0.2 (+https://localhost; research assistant; "
    "compatible; httpx)"
)


# ── web_search ────────────────────────────────────────────────────────────


async def web_search(*, query: str, max_results: int = 5) -> dict[str, Any]:
    from app.agent.tools.web_search import run_web_search

    return await run_web_search(query=query, max_results=max_results)


# Kept for tests / rare callers that still scrape DDG HTML directly.
def _parse_ddg_html(html: str, limit: int) -> list[dict[str, str]]:
    from app.agent.tools.web_search import _strip_tags, _unwrap_ddg_href

    out: list[dict[str, str]] = []
    pattern = re.compile(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.I | re.S,
    )
    snip_pattern = re.compile(
        r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)>',
        re.I | re.S,
    )
    titles = pattern.findall(html)
    snips = [_strip_tags(s) for s in snip_pattern.findall(html)]
    for i, (raw_url, title_html) in enumerate(titles):
        if len(out) >= limit:
            break
        url = _unwrap_ddg_href(raw_url)
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith("http"):
            continue
        title = _strip_tags(title_html)
        snippet = snips[i] if i < len(snips) else ""
        out.append({"title": title[:200], "snippet": snippet[:400], "url": url})
    return out


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


# ── fetch_url ─────────────────────────────────────────────────────────────


async def fetch_url(*, url: str, max_chars: int = 6000) -> dict[str, Any]:
    raw = (url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"ok": False, "error": "url must be an absolute http(s) URL"}
    limit = max(500, min(int(max_chars or 6000), 20000))

    async with httpx.AsyncClient(
        timeout=25.0,
        headers={"User-Agent": _UA},
        follow_redirects=True,
    ) as client:
        r = await client.get(raw)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        final_url = str(r.url)
        text = r.text

    if "html" in ctype or text.lstrip().lower().startswith("<!doctype") or "<html" in text[:200].lower():
        text = _html_to_text(text)
    text = text.strip()
    truncated = len(text) > limit
    return {
        "ok": True,
        "url": final_url,
        "content_type": ctype,
        "truncated": truncated,
        "text": text[:limit],
    }


def _html_to_text(html: str) -> str:
    cleaned = re.sub(
        r"(?is)<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>",
        " ",
        html,
    )
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</p>", "\n\n", cleaned)
    cleaned = re.sub(r"(?i)</h[1-6]>", "\n\n", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# ── get_weather ───────────────────────────────────────────────────────────


async def get_weather(*, location: str) -> dict[str, Any]:
    loc = (location or "").strip()
    if not loc:
        return {"ok": False, "error": "location is required"}

    # wttr.in — no API key. Format j1 = JSON.
    url = f"https://wttr.in/{quote_plus(loc)}?format=j1"
    async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": _UA}) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()

    current = (data.get("current_condition") or [{}])[0]
    area = (data.get("nearest_area") or [{}])[0]
    area_name = ""
    if area.get("areaName"):
        area_name = area["areaName"][0].get("value", loc)
    country = ""
    if area.get("country"):
        country = area["country"][0].get("value", "")

    forecast = []
    for day in (data.get("weather") or [])[:3]:
        forecast.append(
            {
                "date": day.get("date"),
                "avg_c": day.get("avgtempC"),
                "max_c": day.get("maxtempC"),
                "min_c": day.get("mintempC"),
                "desc": ((day.get("hourly") or [{}])[0].get("weatherDesc") or [{}])[0].get(
                    "value"
                ),
            }
        )

    return {
        "ok": True,
        "location": f"{area_name}, {country}".strip(", "),
        "current": {
            "temp_c": current.get("temp_C"),
            "feels_like_c": current.get("FeelsLikeC"),
            "humidity": current.get("humidity"),
            "weather": ((current.get("weatherDesc") or [{}])[0]).get("value"),
            "wind_kmph": current.get("windspeedKmph"),
            "observation_time": current.get("observation_time"),
        },
        "forecast": forecast,
        "source": "wttr.in",
    }


# ── create_presentation ───────────────────────────────────────────────────


async def create_presentation(
    *,
    title: str | None = None,
    slides: list[dict[str, Any]] | str | None = None,
    subtitle: str | None = None,
    theme: str = "nous",
    **extra: Any,
) -> dict[str, Any]:
    """Build a designed deck. Tolerates alias keys / JSON-string slides from LLMs."""
    # Models often omit `slides` or nest it under aliases when the payload is large.
    if slides is None:
        for key in ("pages", "deck", "content", "slides_json", "presentation"):
            if key in extra and extra[key] is not None:
                slides = extra[key]
                break
    if isinstance(slides, str):
        raw = slides.strip()
        if raw:
            try:
                slides = json.loads(raw)
            except json.JSONDecodeError as exc:
                return {
                    "ok": False,
                    "error": (
                        "slides must be a JSON array of slide objects "
                        f"(failed to parse string: {exc}). "
                        "Retry ONE tool call with both title and slides."
                    ),
                }
    if isinstance(slides, dict):
        # Sometimes the model wraps as {"slides":[...]} again.
        inner = slides.get("slides") or slides.get("pages")
        slides = inner if isinstance(inner, list) else [slides]

    title_val = (title or extra.get("name") or "Untitled")
    title_val = str(title_val).strip() or "Untitled"
    if not isinstance(slides, list) or not slides:
        return {
            "ok": False,
            "error": (
                "Missing required argument `slides` (non-empty array). "
                "Call create_presentation once with BOTH title and slides. "
                "For code samples use layout='code' with a multiline `code` string "
                "so indentation is preserved. Do not send title-only calls."
            ),
            "hint": {
                "required": ["title", "slides"],
                "layouts": [
                    "title",
                    "section",
                    "bullets",
                    "two_column",
                    "cards",
                    "code",
                    "quote",
                    "closing",
                ],
            },
        }

    from app.agent.tools.export_urls import (
        ascii_export_stem,
        export_download_url,
        export_user_message,
    )

    try:
        from app.agent.tools.pptx_builder import available_themes, build_presentation

        prs = build_presentation(
            title=title_val,
            slides=slides,
            subtitle=subtitle or extra.get("subtitle"),
            theme_id=theme or extra.get("theme") or "nous",
            brand="Nous",
        )
    except ImportError:
        return {
            "ok": False,
            "error": (
                "python-pptx is not installed. "
                "Run: pip install -r requirements-tools.txt"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("pptx_build_failed")
        return {"ok": False, "error": f"Failed to build presentation: {exc}"}

    export_dir = settings.resolve_path("./data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex[:12]
    safe_title = ascii_export_stem(title_val, fallback="deck")
    filename = f"{safe_title}_{file_id}.pptx"
    path = export_dir / filename
    prs.save(str(path))

    theme_ids = [t["id"] for t in available_themes()]
    resolved_theme = (
        (theme or "nous").lower()
        if (theme or "").lower() in theme_ids
        else "nous"
    )
    download_url = export_download_url(filename)
    payload = {
        "ok": True,
        "title": title_val,
        "theme": resolved_theme,
        "themes_available": theme_ids,
        "slide_count": len(prs.slides),
        "filename": filename,
        "path": str(path),
        "download_url": download_url,
        "download_hint": (
            "Paste download_url as a markdown relative link in the chat reply. "
            "Never convert it to http://127.0.0.1 or http://localhost."
        ),
        "message": export_user_message(
            kind="Presentation",
            title=title_val,
            download_url=download_url,
            extra=f"slides={len(prs.slides)} theme={resolved_theme}.",
        ),
    }
    from app.agent.artifacts import attach_inspect

    payload = attach_inspect(payload)
    inspect = payload.get("inspect") or {}
    payload["message"] = export_user_message(
        kind="Presentation",
        title=title_val,
        download_url=download_url,
        extra=(
            f"slides={len(prs.slides)} theme={resolved_theme}. inspect={inspect}. "
            "Only claim what inspect confirms."
        ),
    )
    return payload


# ── create_pdf ────────────────────────────────────────────────────────────


async def create_pdf(
    *,
    title: str | None = None,
    sections: list[dict[str, Any]] | str | None = None,
    subtitle: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build an A4 PDF handout/tutorial. Not a slide deck."""
    if sections is None:
        for key in ("pages", "chapters", "content", "sections_json", "document"):
            if key in extra and extra[key] is not None:
                sections = extra[key]
                break
    if isinstance(sections, str):
        raw = sections.strip()
        if raw:
            try:
                sections = json.loads(raw)
            except json.JSONDecodeError as exc:
                return {
                    "ok": False,
                    "error": (
                        "sections must be a JSON array of section objects "
                        f"(failed to parse string: {exc})."
                    ),
                }
    if isinstance(sections, dict):
        inner = (
            sections.get("sections")
            or sections.get("pages")
            or sections.get("chapters")
        )
        sections = inner if isinstance(inner, list) else [sections]

    title_val = str(title or extra.get("name") or "Untitled").strip() or "Untitled"
    if not isinstance(sections, list) or not sections:
        return {
            "ok": False,
            "error": (
                "Missing required argument `sections` (non-empty array). "
                "Call create_pdf once with BOTH title and sections. "
                "Do not use create_presentation when the user asked for a PDF."
            ),
            "hint": {
                "required": ["title", "sections"],
                "section_fields": [
                    "heading",
                    "body",
                    "bullets",
                    "code",
                    "language",
                    "level",
                ],
            },
        }

    from app.agent.tools.export_urls import (
        ascii_export_stem,
        export_download_url,
        export_user_message,
    )

    export_dir = settings.resolve_path("./data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex[:12]
    safe_title = ascii_export_stem(title_val, fallback="document")
    filename = f"{safe_title}_{file_id}.pdf"
    path = export_dir / filename

    try:
        from app.agent.tools.pdf_builder import build_pdf

        page_count = build_pdf(
            path=path,
            title=title_val,
            sections=sections,
            subtitle=subtitle or extra.get("subtitle"),
            brand="Nous",
        )
    except ImportError:
        return {
            "ok": False,
            "error": (
                "reportlab is not installed. "
                "Run: pip install -r requirements-tools.txt"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("pdf_build_failed")
        if path.exists():
            path.unlink(missing_ok=True)
        return {"ok": False, "error": f"Failed to build PDF: {exc}"}

    download_url = export_download_url(filename)
    payload = {
        "ok": True,
        "title": title_val,
        "page_count": page_count,
        "filename": filename,
        "path": str(path),
        "download_url": download_url,
        "download_hint": (
            "Paste download_url as a markdown relative link in the chat reply. "
            "Never convert it to http://127.0.0.1 or http://localhost."
        ),
        "message": export_user_message(
            kind="PDF",
            title=title_val,
            download_url=download_url,
            extra=f"pages={page_count}.",
        ),
    }
    from app.agent.artifacts import attach_inspect

    payload = attach_inspect(payload)
    inspect = payload.get("inspect") or {}
    payload["message"] = export_user_message(
        kind="PDF",
        title=title_val,
        download_url=download_url,
        extra=f"pages={page_count}. inspect={inspect}. Only claim what inspect confirms.",
    )
    return payload


# ── create_webpage ────────────────────────────────────────────────────────


async def create_webpage(
    *,
    title: str | None = None,
    sections: list[dict[str, Any]] | str | None = None,
    subtitle: str | None = None,
    presenter: str | None = None,
    audience: str | None = None,
    date: str | None = None,
    theme: str = "nous",
    **extra: Any,
) -> dict[str, Any]:
    """Build a scroll-snap HTML briefing page (not PPT / not PDF)."""
    if sections is None:
        for key in ("pages", "slides", "content", "sections_json", "deck"):
            if key in extra and extra[key] is not None:
                sections = extra[key]
                break
    if isinstance(sections, str):
        raw = sections.strip()
        if raw:
            try:
                sections = json.loads(raw)
            except json.JSONDecodeError as exc:
                return {
                    "ok": False,
                    "error": (
                        "sections must be a JSON array of section objects "
                        f"(failed to parse string: {exc})."
                    ),
                }
    if isinstance(sections, dict):
        inner = (
            sections.get("sections")
            or sections.get("pages")
            or sections.get("slides")
        )
        sections = inner if isinstance(inner, list) else [sections]

    title_val = str(title or extra.get("name") or "Untitled").strip() or "Untitled"
    if not isinstance(sections, list) or not sections:
        return {
            "ok": False,
            "error": (
                "Missing required argument `sections` (non-empty array). "
                "Call create_webpage once with BOTH title and sections. "
                "Do not use create_presentation when the user asked for a webpage / demo."
            ),
            "hint": {
                "required": ["title", "sections"],
                "layouts": [
                    "hero",
                    "kpis",
                    "narrative",
                    "split",
                    "timeline",
                    "cards",
                    "architecture",
                    "figure",
                    "code",
                    "quote",
                    "closing",
                ],
            },
        }

    from app.agent.tools.export_urls import (
        ascii_export_stem,
        export_download_url,
        export_user_message,
    )

    export_dir = settings.resolve_path("./data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex[:12]
    safe_title = ascii_export_stem(title_val, fallback="briefing")
    filename = f"{safe_title}_{file_id}.html"
    path = export_dir / filename

    try:
        from app.agent.tools.html_builder import build_webpage

        page_count = build_webpage(
            path=path,
            title=title_val,
            sections=sections,
            subtitle=subtitle or extra.get("subtitle"),
            presenter=presenter or extra.get("presenter"),
            audience=audience or extra.get("audience"),
            date_label=date or extra.get("date"),
            theme_id=theme or extra.get("theme") or "nous",
            brand="Nous",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("webpage_build_failed")
        if path.exists():
            path.unlink(missing_ok=True)
        return {"ok": False, "error": f"Failed to build webpage: {exc}"}

    open_url = export_download_url(filename)
    payload = {
        "ok": True,
        "title": title_val,
        "page_count": page_count,
        "filename": filename,
        "path": str(path),
        "download_url": open_url,
        "open_url": open_url,
        "download_hint": (
            f"Paste this EXACT markdown link in the reply: "
            f"[打开汇报网页]({open_url}). "
            "Do not invent another filename."
        ),
    }
    from app.agent.artifacts import attach_inspect

    payload = attach_inspect(payload)
    inspect = payload.get("inspect") or {}
    extra = (
        f"pages={page_count}. inspect={inspect}. "
        "Open in the browser (fullscreen + arrow keys). "
        "You may only claim what inspect confirms. "
        "Do not offer a PPT unless the user asked for one."
    )
    if int(inspect.get("image_count") or 0) <= 0:
        extra += (
            " WARNING: inspect.image_count=0. If the user wanted a photo/figure, "
            "pass hero.image and call create_webpage again. Do not claim it was added."
        )
    if inspect.get("has_code") is False:
        extra += (
            " WARNING: inspect.has_code=false. If the user wanted 伪代码/algorithm, "
            "use layout=code with a multiline `code` field. "
            "A heading 伪代码 with an empty body does not count. Do not claim it was added."
        )
    empty = inspect.get("empty_headings") or []
    if empty:
        extra += (
            " WARNING: empty sections (title only): "
            + " | ".join(str(h) for h in empty[:6])
            + ". Fill body or `code` and call create_webpage again."
        )
    payload["has_embedded_image"] = bool(inspect.get("hero_has_photo") or inspect.get("image_count"))
    payload["message"] = export_user_message(
        kind="Webpage briefing",
        title=title_val,
        download_url=open_url,
        extra=extra,
    )
    return payload


# ── generate_image ─────────────────────────────────────────────────────────


async def generate_image(
    *,
    prompt: str,
    size: str = "1024x1024",
    filename_hint: str | None = None,
) -> dict[str, Any]:
    """Text-to-image → PNG under exports. See ``app.agent.tools.image_gen``."""
    from app.agent.tools.image_gen import generate_image as _gen

    return await _gen(prompt=prompt, size=size, filename_hint=filename_hint)


# ── crop_image ─────────────────────────────────────────────────────────────


async def crop_image(
    *,
    src: str,
    left: float | None = None,
    top: float | None = None,
    width: float | None = None,
    height: float | None = None,
    unit: str = "ratio",
    preset: str | None = "portrait",
    filename_hint: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    from app.agent.tools.image_crop import crop_image as _crop

    return await _crop(
        src=src or extra.get("url") or extra.get("image") or "",
        left=left if left is not None else extra.get("x"),
        top=top if top is not None else extra.get("y"),
        width=width if width is not None else extra.get("w"),
        height=height if height is not None else extra.get("h"),
        unit=unit or extra.get("unit") or "ratio",
        preset=preset or extra.get("preset") or "portrait",
        filename_hint=filename_hint,
    )


# ── calculator ────────────────────────────────────────────────────────────


_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


async def calculator(*, expression: str) -> dict[str, Any]:
    expr = (expression or "").strip()
    if not expr or len(expr) > 200:
        return {"ok": False, "error": "expression must be 1..200 characters"}
    try:
        tree = ast.parse(expr, mode="eval")
        value = _eval_ast(tree.body)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Cannot evaluate: {exc}"}
    return {"ok": True, "expression": expr, "result": value}


def _eval_ast(node: ast.AST) -> float | int:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_ast(node.left), _eval_ast(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_ast(node.operand))
    if isinstance(node, ast.Expr):
        return _eval_ast(node.value)
    raise ValueError(f"unsupported syntax: {type(node).__name__}")


# ── current_datetime ──────────────────────────────────────────────────────


async def current_datetime(*, timezone: str | None = None) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    result: dict[str, Any] = {
        "ok": True,
        "utc": now_utc.isoformat(),
        "unix": int(now_utc.timestamp()),
    }
    if timezone:
        try:
            from zoneinfo import ZoneInfo

            local = now_utc.astimezone(ZoneInfo(timezone))
            result["timezone"] = timezone
            result["local"] = local.isoformat()
        except Exception as exc:  # noqa: BLE001
            result["timezone_error"] = str(exc)
            result["local"] = datetime.now().isoformat()
    else:
        result["local"] = datetime.now().astimezone().isoformat()
    return result
