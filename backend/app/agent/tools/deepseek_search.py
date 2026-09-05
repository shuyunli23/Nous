"""DeepSeek official server-side search (Harness ``web_search_20250305``).

This is a dedicated Messages call, not the chat completion used for replies.
The wire format matches DeepSeek Harness ``web-search-deepseek``.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.agent.search_config import DEFAULT_DEEPSEEK_API_VERSION, ResolvedSearch
from app.core.logging import get_logger

logger = get_logger(__name__)

_USER_AGENT = "nous/web-search-deepseek"


def citation_snippets(blocks: list[dict[str, Any]]) -> dict[str, str]:
    """Map ``url → cited_text`` from Anthropic text-block citations."""
    out: dict[str, str] = {}
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        for cite in block.get("citations") or []:
            if not isinstance(cite, dict):
                continue
            url = str(cite.get("url") or "").strip()
            text = str(cite.get("cited_text") or "").strip()
            if url and text and url not in out:
                out[url] = text
    return out


def map_anthropic_response(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Walk ``web_search_tool_result`` blocks into title/url/snippet rows."""
    blocks = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(blocks, list):
        return []
    result_blocks = [
        block
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "web_search_tool_result"
    ]
    if not result_blocks:
        return []

    snippets = citation_snippets(blocks)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for block in result_blocks:
        for item in block.get("content") or []:
            if not isinstance(item, dict) or item.get("type") != "web_search_result":
                continue
            url = str(item.get("url") or "").strip()
            if not url.startswith("http") or url in seen:
                continue
            seen.add(url)
            title = str(item.get("title") or "").strip() or url
            snippet = snippets.get(url, "")
            rows.append(
                {"title": title[:200], "snippet": snippet[:500], "url": url}
            )
    return rows


def _error_detail(payload: Any) -> str:
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, str) and err.strip():
            return err.strip()
        if isinstance(err, dict):
            message = str(err.get("message") or "").strip()
            if message:
                return message
        message = str(payload.get("message") or "").strip()
        if message:
            return message
    return ""


async def search_deepseek(query: str, limit: int, cfg: ResolvedSearch) -> list[dict[str, str]]:
    key = (cfg.deepseek_api_key or "").strip()
    if not key:
        return []
    base = (cfg.deepseek_base_url or "").rstrip("/")
    if not base:
        return []
    endpoint = f"{base}/messages"
    timeout = max(30.0, float(cfg.deepseek_timeout_seconds or 90.0))
    body = {
        "model": cfg.deepseek_model,
        "max_tokens": int(cfg.deepseek_max_tokens or 4096),
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Perform a web search for the query: {query}",
                    }
                ],
            }
        ],
        "tools": [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": int(cfg.deepseek_max_uses or 2),
            }
        ],
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await client.post(
            endpoint,
            headers={
                "x-api-key": key,
                "authorization": f"Bearer {key}",
                "anthropic-version": cfg.deepseek_api_version or DEFAULT_DEEPSEEK_API_VERSION,
                "content-type": "application/json",
                "accept": "application/json",
                "user-agent": _USER_AGENT,
            },
            json=body,
        )
    if response.status_code >= 400:
        detail = ""
        try:
            detail = _error_detail(response.json())
        except ValueError:
            detail = (response.text or "")[:200]
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(f"DeepSeek search HTTP {response.status_code}{suffix}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("DeepSeek search returned a non-JSON body") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("DeepSeek search returned an unexpected body")
    rows = map_anthropic_response(payload)
    if not rows:
        raise RuntimeError(
            "DeepSeek returned no web_search_tool_result blocks; "
            "the request may not have triggered native web search"
        )
    return rows[: max(1, limit)]
