"""Web search backends used by the ``web_search`` tool.

Order when ``WEB_SEARCH_PROVIDER=auto``:
1. Brave / Tavily / Serper if the matching API key is set
2. DuckDuckGo HTML scrape (fast free path)
3. ``ddgs`` with pinned backends (bing → duckduckgo → brave)
"""

from __future__ import annotations

import asyncio
import re
from html import unescape
from typing import Any
from urllib.parse import quote_plus, unquote, urlparse

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def _normalize(item: dict[str, Any]) -> dict[str, str] | None:
    title = str(item.get("title") or "").strip()
    url = str(item.get("url") or item.get("href") or item.get("link") or "").strip()
    snippet = str(
        item.get("snippet")
        or item.get("body")
        or item.get("description")
        or item.get("content")
        or ""
    ).strip()
    if not url.startswith("http"):
        return None
    if not title:
        title = url
    return {"title": title[:200], "snippet": snippet[:500], "url": url}


def _dedupe(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        key = row["url"].split("#", 1)[0].rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) >= limit:
            break
    return out


async def _search_brave(query: str, limit: int) -> list[dict[str, str]]:
    key = (settings.brave_search_api_key or "").strip()
    if not key:
        return []
    async with httpx.AsyncClient(timeout=settings.web_search_timeout_seconds) as client:
        r = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": limit},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": key,
            },
        )
        r.raise_for_status()
        data = r.json()
    rows = []
    for item in (data.get("web") or {}).get("results") or []:
        norm = _normalize(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("description"),
            }
        )
        if norm:
            rows.append(norm)
    return rows


async def _search_tavily(query: str, limit: int) -> list[dict[str, str]]:
    key = (settings.tavily_api_key or "").strip()
    if not key:
        return []
    async with httpx.AsyncClient(timeout=settings.web_search_timeout_seconds) as client:
        r = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "max_results": limit,
                "include_answer": False,
                "search_depth": "basic",
            },
        )
        r.raise_for_status()
        data = r.json()
    rows = []
    for item in data.get("results") or []:
        norm = _normalize(item)
        if norm:
            rows.append(norm)
    return rows


async def _search_serper(query: str, limit: int) -> list[dict[str, str]]:
    key = (settings.serper_api_key or "").strip()
    if not key:
        return []
    async with httpx.AsyncClient(timeout=settings.web_search_timeout_seconds) as client:
        r = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query, "num": limit},
        )
        r.raise_for_status()
        data = r.json()
    rows = []
    for item in data.get("organic") or []:
        norm = _normalize(
            {
                "title": item.get("title"),
                "url": item.get("link"),
                "snippet": item.get("snippet"),
            }
        )
        if norm:
            rows.append(norm)
    return rows


def _search_ddgs_sync(query: str, limit: int) -> list[dict[str, str]]:
    """Query ddgs with a short backend list (avoid auto's multi-engine timeouts)."""
    try:
        from ddgs import DDGS
        from ddgs.exceptions import DDGSException
    except ImportError:
        logger.warning("web_search_ddgs_missing", hint="pip install ddgs")
        return []

    # Prefer engines that work from restricted networks; skip wikipedia/yandex/etc.
    backends = [
        b.strip()
        for b in (settings.web_search_ddgs_backends or "bing,duckduckgo,brave").split(",")
        if b.strip()
    ]
    timeout = max(3, min(int(settings.web_search_timeout_seconds or 15), 20))

    for backend in backends:
        try:
            with DDGS(timeout=timeout) as ddgs:
                items = ddgs.text(query, max_results=limit, backend=backend)
            rows: list[dict[str, str]] = []
            for item in items or []:
                norm = _normalize(
                    {
                        "title": item.get("title"),
                        "url": item.get("href") or item.get("link"),
                        "snippet": item.get("body"),
                    }
                )
                if norm:
                    rows.append(norm)
            if rows:
                return rows
        except DDGSException as exc:
            logger.info("web_search_ddgs_backend_empty", backend=backend, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.warning("web_search_ddgs_backend_failed", backend=backend, error=str(exc))
    return []


async def _search_ddgs(query: str, limit: int) -> list[dict[str, str]]:
    return await asyncio.to_thread(_search_ddgs_sync, query, limit)


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _unwrap_ddg_href(url: str) -> str:
    """DuckDuckGo HTML often wraps destinations as /l/?uddg=<encoded>."""
    if "uddg=" in url:
        try:
            from urllib.parse import parse_qs

            qs = parse_qs(urlparse(url).query)
            if "uddg" in qs and qs["uddg"]:
                return unquote(qs["uddg"][0])
        except Exception:  # noqa: BLE001
            pass
    return url


async def _search_ddg_html(query: str, limit: int) -> list[dict[str, str]]:
    async with httpx.AsyncClient(
        timeout=settings.web_search_timeout_seconds,
        headers={"User-Agent": _BROWSER_UA},
        follow_redirects=True,
    ) as client:
        r = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
        )
        r.raise_for_status()
        html = r.text

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
        out.append({"title": title[:200], "snippet": snippet[:500], "url": url})
    return out


async def run_web_search(*, query: str, max_results: int = 5) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"ok": False, "error": "query is required"}
    limit = max(1, min(int(max_results or 5), 10))

    provider = (settings.web_search_provider or "auto").strip().lower()
    backends: list[tuple[str, Any]] = []

    def _paid_configured() -> list[tuple[str, Any]]:
        ordered: list[tuple[str, Any]] = []
        if settings.brave_search_api_key.strip():
            ordered.append(("brave", _search_brave))
        if settings.tavily_api_key.strip():
            ordered.append(("tavily", _search_tavily))
        if settings.serper_api_key.strip():
            ordered.append(("serper", _search_serper))
        return ordered

    if provider == "brave":
        backends = [("brave", _search_brave)]
    elif provider == "tavily":
        backends = [("tavily", _search_tavily)]
    elif provider == "serper":
        backends = [("serper", _search_serper)]
    elif provider == "ddgs":
        # HTML scrape first: faster + more reliable when metasearch engines time out.
        backends = [("ddg_html", _search_ddg_html), ("ddgs", _search_ddgs)]
    elif provider == "ddg_html":
        backends = [("ddg_html", _search_ddg_html)]
    else:
        # auto
        backends = _paid_configured()
        backends.extend([("ddg_html", _search_ddg_html), ("ddgs", _search_ddgs)])

    errors: list[str] = []
    used = ""
    results: list[dict[str, str]] = []

    for name, fn in backends:
        try:
            batch = await asyncio.wait_for(
                fn(q, limit),
                timeout=max(5.0, float(settings.web_search_timeout_seconds) + 5.0),
            )
            batch = _dedupe(batch, limit)
            if batch:
                results = batch
                used = name
                break
            errors.append(f"{name}: empty")
        except TimeoutError:
            logger.warning("web_search_backend_timeout", backend=name)
            errors.append(f"{name}: timeout")
        except Exception as exc:  # noqa: BLE001
            logger.warning("web_search_backend_failed", backend=name, error=str(exc))
            errors.append(f"{name}: {exc}")

    if not results:
        return {
            "ok": False,
            "query": q,
            "count": 0,
            "results": [],
            "error": (
                "No web search results. Try a more specific query "
                "(e.g. add 'github' / official site), or set BRAVE_SEARCH_API_KEY / "
                "TAVILY_API_KEY / SERPER_API_KEY."
            ),
            "tried": errors,
        }

    return {
        "ok": True,
        "query": q,
        "count": len(results),
        "results": results,
        "provider": used,
        "note": (
            f"Results via {used}. Call fetch_url on the top 1–3 links for full text. "
            "Cite sources when answering. If results look weak, retry with an "
            "English / more specific query."
        ),
    }
