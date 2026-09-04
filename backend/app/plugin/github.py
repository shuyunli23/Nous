"""Fetch a plugin archive from GitHub (or an allow-listed zip URL)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.exceptions import ValidationError

ALLOWED_HOSTS = frozenset(
    {
        "github.com",
        "www.github.com",
        "codeload.github.com",
        "gitlab.com",
        "www.gitlab.com",
    }
)

_GITHUB_RE = re.compile(
    r"""
    ^https?://(?:www\.)?github\.com/
    (?P<owner>[A-Za-z0-9_.-]+)/
    (?P<repo>[A-Za-z0-9_.-]+?)
    (?:\.git)?
    (?:/
        (?:tree|blob)/(?P<tree>[^/]+)
        |
        releases/tag/(?P<tag>[^/]+)
        |
        archive/(?:refs/(?:heads|tags)/)?(?P<archive>[^/]+?)(?:\.zip)?
    )?
    /?
    $
    """,
    re.VERBOSE,
)

_SHORT_RE = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)$"
)


@dataclass(frozen=True)
class PluginSource:
    kind: str  # github | zip
    url: str
    owner: str | None = None
    repo: str | None = None
    ref: str | None = None


def parse_plugin_source(raw: str) -> PluginSource:
    text = (raw or "").strip()
    if not text:
        raise ValidationError("Plugin URL is required.")

    short = _SHORT_RE.match(text)
    if short:
        return PluginSource(
            kind="github",
            url=f"https://github.com/{short.group('owner')}/{short.group('repo')}",
            owner=short.group("owner"),
            repo=short.group("repo"),
        )

    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ValidationError(
            "Only GitHub / GitLab URLs (or their zip archives) can be imported.",
            details={"host": host or None},
        )
    if parsed.scheme not in {"http", "https"}:
        raise ValidationError("Plugin URL must be http or https.")

    path = parsed.path or ""
    if path.lower().endswith(".zip"):
        return PluginSource(kind="zip", url=text)

    match = _GITHUB_RE.match(text.rstrip("/"))
    if not match:
        raise ValidationError(
            "Unrecognized GitHub URL. Use https://github.com/owner/repo "
            "or owner/repo."
        )
    ref = match.group("tree") or match.group("tag") or match.group("archive")
    return PluginSource(
        kind="github",
        url=text,
        owner=match.group("owner"),
        repo=match.group("repo"),
        ref=ref,
    )


def _github_zip_urls(source: PluginSource) -> list[str]:
    owner, repo = source.owner, source.repo
    if not owner or not repo:
        return [source.url]
    refs = [source.ref] if source.ref else ["main", "master"]
    urls: list[str] = []
    for ref in refs:
        if not ref:
            continue
        urls.append(f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{ref}")
        urls.append(f"https://codeload.github.com/{owner}/{repo}/zip/refs/tags/{ref}")
        urls.append(f"https://github.com/{owner}/{repo}/archive/refs/heads/{ref}.zip")
        urls.append(f"https://github.com/{owner}/{repo}/archive/refs/tags/{ref}.zip")
    # Unique while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


async def fetch_plugin_archive(raw_url: str) -> tuple[bytes, PluginSource]:
    """Download zip bytes. Returns (data, source)."""
    source = parse_plugin_source(raw_url)
    candidates = [source.url] if source.kind == "zip" else _github_zip_urls(source)
    last_error = "Could not download plugin archive."
    timeout = httpx.Timeout(45.0, connect=10.0)
    headers = {"User-Agent": "Nous-plugin-importer/1"}
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers=headers,
    ) as client:
        for url in candidates:
            host = (urlparse(url).hostname or "").lower()
            if host not in ALLOWED_HOSTS:
                continue
            try:
                response = await client.get(url)
            except httpx.HTTPError as exc:
                last_error = str(exc)
                continue
            if response.status_code >= 400:
                last_error = f"HTTP {response.status_code} from {host}"
                continue
            data = response.content
            if not data:
                last_error = "Empty archive."
                continue
            if len(data) > settings.skill_pack_max_zip_bytes:
                raise ValidationError(
                    "Downloaded archive exceeds size limit.",
                    details={"max_zip_bytes": settings.skill_pack_max_zip_bytes},
                )
            if data[:2] != b"PK":
                last_error = "Response was not a zip archive."
                continue
            return data, source
    raise ValidationError(last_error, details={"url": source.url})
