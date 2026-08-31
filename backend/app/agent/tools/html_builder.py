"""Self-contained HTML briefing page for Nous ``create_webpage``.

A scroll-snap, full-viewport web report meant to be opened in a browser and
presented to leadership (keyboard paging + fullscreen) — not a PowerPoint.
"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path
from typing import Any

THEMES: dict[str, dict[str, str]] = {
    "nous": {
        "bg": "#e8eef3",
        "bg2": "#f4f8f7",
        "surface": "#ffffff",
        "ink": "#102033",
        "muted": "#5b6b7c",
        "faint": "#8a97a8",
        "accent": "#0f8f86",
        "accent2": "#0b6f68",
        "line": "rgba(15,35,55,0.12)",
        "hero": "linear-gradient(145deg,#07111f 0%,#0f3d3a 55%,#0f8f86 140%)",
        "hero_ink": "#f4fbfa",
        "hero_muted": "rgba(244,251,250,0.72)",
    },
    "slate": {
        "bg": "#eef0f5",
        "bg2": "#f7f8fb",
        "surface": "#ffffff",
        "ink": "#1a1f2e",
        "muted": "#6b7385",
        "faint": "#939aab",
        "accent": "#2f5be0",
        "accent2": "#1e3fb0",
        "line": "rgba(26,31,46,0.12)",
        "hero": "linear-gradient(145deg,#12162a 0%,#24356a 60%,#2f5be0 140%)",
        "hero_ink": "#f5f7ff",
        "hero_muted": "rgba(245,247,255,0.72)",
    },
    "ink": {
        "bg": "#101620",
        "bg2": "#16202c",
        "surface": "#1b2634",
        "ink": "#e8eef3",
        "muted": "#9aa8b5",
        "faint": "#6d7c8a",
        "accent": "#2dd4bf",
        "accent2": "#14b8a6",
        "line": "rgba(232,238,243,0.12)",
        "hero": "linear-gradient(145deg,#070b10 0%,#102033 55%,#0f766e 140%)",
        "hero_ink": "#f4fbfa",
        "hero_muted": "rgba(244,251,250,0.7)",
    },
    "dawn": {
        "bg": "#f6efe6",
        "bg2": "#fbf6ef",
        "surface": "#fffdf9",
        "ink": "#2a1c12",
        "muted": "#7a6556",
        "faint": "#a8907e",
        "accent": "#c45c26",
        "accent2": "#9a3f14",
        "line": "rgba(42,28,18,0.12)",
        "hero": "linear-gradient(145deg,#2a1c12 0%,#6b3218 55%,#c45c26 140%)",
        "hero_ink": "#fff7ef",
        "hero_muted": "rgba(255,247,239,0.72)",
    },
}


def build_webpage(
    *,
    path: Path,
    title: str,
    sections: list[dict[str, Any]],
    subtitle: str | None = None,
    presenter: str | None = None,
    audience: str | None = None,
    date_label: str | None = None,
    theme_id: str = "nous",
    brand: str = "Nous",
) -> int:
    theme = THEMES.get((theme_id or "nous").lower()) or THEMES["nous"]
    when = (date_label or "").strip() or date.today().strftime("%Y.%m.%d")
    pages = _normalize_sections(title, subtitle, sections)
    nav = []
    body = []
    for i, sec in enumerate(pages):
        sid = f"s{i}"
        nav.append(
            f'<a href="#{sid}" data-nav="{sid}">{_esc(sec["nav"])}</a>'
        )
        body.append(_render_section(sid, sec, i, len(pages), brand, when))
    html_doc = _DOCUMENT.format(
        title=_esc(title),
        brand=_esc(brand),
        theme_css=_theme_css(theme),
        nav="\n".join(nav),
        body="\n".join(body),
        presenter=_esc(presenter or ""),
        audience=_esc(audience or "内部汇报"),
        date=_esc(when),
    )
    path.write_text(html_doc, encoding="utf-8")
    return len(pages)


def _normalize_sections(
    title: str,
    subtitle: str | None,
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for raw in sections:
        if not isinstance(raw, dict):
            continue
        layout = str(raw.get("layout") or "narrative").lower().strip()
        if layout in {"title", "cover"}:
            layout = "hero"
        if layout in {"bullets", "content"}:
            layout = "narrative"
        if layout in {"two_column"}:
            layout = "split"
        if layout in {"image", "fig", "photo", "diagram"}:
            layout = "figure"
        if layout in {"code", "snippet", "pseudocode", "algo", "algorithm"}:
            layout = "code"
        heading = str(raw.get("heading") or raw.get("title") or "").strip()
        nav = str(raw.get("nav") or heading or layout).strip()[:12]
        if layout == "narrative" and (raw.get("image") or raw.get("images")):
            layout = "figure"
        heading_l = heading.lower()
        if any(raw.get(key) for key in ("code", "source", "snippet", "pseudocode")):
            layout = "code"
        elif any(key in heading for key in ("伪代码", "伪码")) or "pseudocode" in heading_l:
            layout = "code"
        pages.append({**raw, "layout": layout, "heading": heading, "nav": nav})
    if not pages or pages[0].get("layout") != "hero":
        pages.insert(
            0,
            {
                "layout": "hero",
                "heading": title,
                "subtitle": subtitle or "",
                "nav": "开场",
                "kicker": "领导汇报 · Demo",
            },
        )
    else:
        pages[0].setdefault("heading", title)
        if subtitle and not pages[0].get("subtitle"):
            pages[0]["subtitle"] = subtitle
    if pages[-1].get("layout") != "closing" and len(pages) > 1:
        # Keep model-provided last section; only auto-close if it's still narrative-less.
        pass
    return pages


def _render_section(
    sid: str,
    sec: dict[str, Any],
    index: int,
    total: int,
    brand: str,
    when: str,
) -> str:
    layout = sec.get("layout") or "narrative"
    if layout == "hero":
        return _hero(sid, sec, brand, when, index, total)
    if layout == "kpis":
        return _kpis(sid, sec, index, total)
    if layout == "split":
        return _split(sid, sec, index, total)
    if layout == "timeline":
        return _timeline(sid, sec, index, total)
    if layout == "cards":
        return _cards(sid, sec, index, total)
    if layout == "quote":
        return _quote(sid, sec, index, total)
    if layout == "architecture":
        return _architecture(sid, sec, index, total)
    if layout == "figure":
        return _figure(sid, sec, index, total)
    if layout == "code":
        return _code(sid, sec, index, total)
    if layout == "closing":
        return _closing(sid, sec, index, total)
    return _narrative(sid, sec, index, total)


def _shell(sid: str, index: int, total: int, inner: str, *, hero: bool = False) -> str:
    cls = "sec sec--hero" if hero else "sec"
    return (
        f'<section class="{cls}" id="{sid}">'
        f'<div class="sec__index">{index + 1:02d} / {total:02d}</div>'
        f"{inner}</section>"
    )


def _kicker(sec: dict[str, Any]) -> str:
    text = str(sec.get("kicker") or "").strip()
    return f'<p class="kicker">{_esc(text)}</p>' if text else ""


def _heading(sec: dict[str, Any]) -> str:
    h = str(sec.get("heading") or "").strip()
    return f"<h2>{_esc(h)}</h2>" if h else ""


def _body(sec: dict[str, Any]) -> str:
    raw = str(sec.get("body") or "").strip()
    if not raw:
        return ""
    paras = [p.strip() for p in raw.split("\n\n") if p.strip()]
    return "".join(f"<p>{_esc(p).replace(chr(10), '<br>')}</p>" for p in paras)


def _bullets(sec: dict[str, Any], key: str = "bullets") -> str:
    items = _str_list(sec.get(key))
    if not items:
        return ""
    lis = "".join(f"<li>{_esc(item)}</li>" for item in items[:8])
    return f'<ul class="bullets">{lis}</ul>'


def _hero(
    sid: str, sec: dict[str, Any], brand: str, when: str, index: int, total: int
) -> str:
    sub = str(sec.get("subtitle") or "").strip()
    presenter = str(sec.get("presenter") or "").strip()
    audience = str(sec.get("audience") or "").strip()
    meta = " · ".join(x for x in (presenter, audience, when) if x)
    photo = ""
    images = _collect_images(sec)
    if images:
        src = _embed_src(str(images[0].get("src") or ""))
        if src:
            alt = _esc(
                images[0].get("caption")
                or sec.get("caption")
                or sec.get("heading")
                or "portrait"
            )
            photo = (
                f'<div class="hero__photo"><img src="{src}" alt="{alt}" /></div>'
            )
    inner = f"""
      <div class="hero">
        <div class="hero__copy">
          <div class="hero__brand">{_esc(brand)}</div>
          {_kicker(sec)}
          <h1>{_esc(sec.get("heading") or "")}</h1>
          {f'<p class="lede">{_esc(sub)}</p>' if sub else ""}
          {_bullets(sec)}
          <div class="hero__meta">{_esc(meta)}</div>
          <p class="hint">方向键 / 空格翻页 · F 全屏 · 适合投屏汇报</p>
        </div>
        {photo}
      </div>
    """
    return _shell(sid, index, total, inner, hero=True)


def _kpis(sid: str, sec: dict[str, Any], index: int, total: int) -> str:
    cards = []
    for item in _dict_list(sec.get("metrics") or sec.get("cards"))[:4]:
        cards.append(
            "<article class='kpi'>"
            f"<span class='kpi__label'>{_esc(item.get('label'))}</span>"
            f"<strong>{_esc(item.get('value'))}</strong>"
            f"<span class='kpi__hint'>{_esc(item.get('hint'))}</span>"
            "</article>"
        )
    inner = f"""
      <div class="wrap">
        {_kicker(sec)}{_heading(sec)}{_body(sec)}
        <div class="kpi-grid">{"".join(cards)}</div>
      </div>
    """
    return _shell(sid, index, total, inner)


def _narrative(sid: str, sec: dict[str, Any], index: int, total: int) -> str:
    inner = f"""
      <div class="wrap wrap--narrow">
        {_kicker(sec)}{_heading(sec)}{_body(sec)}{_bullets(sec)}
      </div>
    """
    return _shell(sid, index, total, inner)


def _split(sid: str, sec: dict[str, Any], index: int, total: int) -> str:
    left_h = str(sec.get("left_heading") or "现状").strip()
    right_h = str(sec.get("right_heading") or "能力").strip()
    inner = f"""
      <div class="wrap">
        {_kicker(sec)}{_heading(sec)}{_body(sec)}
        <div class="split">
          <article>
            <h3>{_esc(left_h)}</h3>
            {_bullets(sec, "left_bullets")}
          </article>
          <article>
            <h3>{_esc(right_h)}</h3>
            {_bullets(sec, "right_bullets")}
          </article>
        </div>
      </div>
    """
    return _shell(sid, index, total, inner)


def _timeline(sid: str, sec: dict[str, Any], index: int, total: int) -> str:
    steps = []
    for item in _dict_list(sec.get("steps") or sec.get("items"))[:8]:
        when = item.get("when") or item.get("label") or item.get("tag") or ""
        title = item.get("title") or item.get("heading") or ""
        body = item.get("body") or item.get("hint") or ""
        steps.append(
            "<li>"
            f"<span class='tl__when'>{_esc(when)}</span>"
            f"<strong>{_esc(title)}</strong>"
            f"<p>{_esc(body)}</p>"
            "</li>"
        )
    inner = f"""
      <div class="wrap wrap--narrow">
        {_kicker(sec)}{_heading(sec)}{_body(sec)}
        <ol class="tl">{"".join(steps)}</ol>
      </div>
    """
    return _shell(sid, index, total, inner)


def _cards(sid: str, sec: dict[str, Any], index: int, total: int) -> str:
    cards = []
    for item in _dict_list(sec.get("cards") or sec.get("items"))[:6]:
        tag = item.get("tag") or item.get("label") or ""
        cards.append(
            "<article class='card'>"
            f"<span class='card__tag'>{_esc(tag)}</span>"
            f"<h3>{_esc(item.get('title') or item.get('heading') or item.get('value'))}</h3>"
            f"<p>{_esc(item.get('body') or item.get('hint'))}</p>"
            "</article>"
        )
    inner = f"""
      <div class="wrap">
        {_kicker(sec)}{_heading(sec)}{_body(sec)}
        <div class="card-grid">{"".join(cards)}</div>
      </div>
    """
    return _shell(sid, index, total, inner)


def _quote(sid: str, sec: dict[str, Any], index: int, total: int) -> str:
    q = str(sec.get("quote") or sec.get("body") or "").strip()
    who = str(sec.get("attribution") or "").strip()
    inner = f"""
      <div class="wrap wrap--narrow quote">
        {_kicker(sec)}{_heading(sec)}
        <blockquote>{_esc(q)}</blockquote>
        {f'<cite>{_esc(who)}</cite>' if who else ""}
      </div>
    """
    return _shell(sid, index, total, inner)


def _code_text(sec: dict[str, Any]) -> str:
    for key in ("code", "source", "snippet", "pseudocode"):
        raw = sec.get(key)
        if isinstance(raw, list):
            text = "\n".join(str(item) for item in raw)
        else:
            text = str(raw or "")
        if text.strip():
            return text.replace("\t", "    ")
    bullets = _str_list(sec.get("explain") or sec.get("bullets"))
    if bullets and any(
        line.startswith(("    ", "\t", "#", "def ", "for ", "if ", "class ", "return "))
        for line in bullets
    ):
        return "\n".join(bullets)
    body = str(sec.get("body") or "").strip()
    if body and ("\n" in body or any(tok in body for tok in ("def ", "for ", "←", "<-"))):
        return body
    return ""


def _code(sid: str, sec: dict[str, Any], index: int, total: int) -> str:
    code = _code_text(sec)
    lang = str(sec.get("language") or sec.get("lang") or "").strip()
    lang_attr = f' data-lang="{_esc(lang)}"' if lang else ""
    block = (
        f'<pre class="code"{lang_attr}><code>{_esc(code) if code else " "}</code></pre>'
    )
    used_bullets_as_code = bool(code) and code == "\n".join(
        _str_list(sec.get("explain") or sec.get("bullets"))
    )
    explain = "" if used_bullets_as_code else (_bullets(sec, "explain") or "")
    inner = f"""
      <div class="wrap">
        {_kicker(sec)}{_heading(sec)}
        {block}
        {explain}
      </div>
    """
    return _shell(sid, index, total, inner)


def _figure(sid: str, sec: dict[str, Any], index: int, total: int) -> str:
    frames = []
    images = _collect_images(sec)
    for item in images[:4]:
        src = _embed_src(str(item.get("src") or ""))
        if not src:
            continue
        cap = str(item.get("caption") or "").strip()
        alt = _esc(cap or sec.get("heading") or "figure")
        caption_html = (
            f'<figcaption class="fig-cap">{_esc(cap)}</figcaption>' if cap else ""
        )
        frames.append(
            "<figure class='fig-frame'>"
            f'<img src="{src}" alt="{alt}" />'
            f"{caption_html}"
            "</figure>"
        )
    gallery = (
        f"<div class='fig-grid'>{''.join(frames)}</div>"
        if len(frames) > 1
        else (frames[0] if frames else "<p class='fig-missing'>未提供图片 URL</p>")
    )
    inner = f"""
      <div class="wrap fig-stage">
        <div class="fig-visual">{gallery}</div>
        <div class="fig-copy">
          {_kicker(sec)}{_heading(sec)}{_body(sec)}{_bullets(sec)}
        </div>
      </div>
    """
    return _shell(sid, index, total, inner)


def _collect_images(sec: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    raw = sec.get("images")
    if raw is None:
        raw = []
    if isinstance(raw, str):
        raw = [raw]
    if isinstance(raw, dict):
        raw = [raw]
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append({"src": item.strip(), "caption": ""})
            elif isinstance(item, dict):
                src = (
                    item.get("src")
                    or item.get("url")
                    or item.get("image")
                    or item.get("href")
                    or ""
                )
                if str(src).strip():
                    out.append(
                        {
                            "src": str(src).strip(),
                            "caption": str(
                                item.get("caption") or item.get("label") or ""
                            ),
                        }
                    )
    single = sec.get("image") or sec.get("src") or sec.get("url")
    if isinstance(single, str) and single.strip():
        out.insert(0, {"src": single.strip(), "caption": str(sec.get("caption") or "")})
    # de-dupe
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in out:
        src = item["src"]
        if src in seen:
            continue
        seen.add(src)
        unique.append(item)
    return unique


def _embed_src(src: str) -> str:
    """Turn local upload/export paths into data URIs so the HTML is portable."""
    from urllib.parse import unquote, urlparse

    if not src:
        return ""
    if src.startswith("data:"):
        return src
    parsed = urlparse(src)
    path = unquote(parsed.path or src)
    local: Path | None = None
    if "/api/v1/files/uploads/" in path:
        name = path.rsplit("/", 1)[-1]
        candidate = settings_resolve_upload(name)
        local = candidate if candidate and candidate.is_file() else None
    elif "/api/v1/files/exports/" in path:
        name = path.rsplit("/", 1)[-1]
        candidate = settings_resolve_export(name)
        local = candidate if candidate and candidate.is_file() else None
    if local is None:
        if path.startswith("/api/v1/files/"):
            return html.escape(path, quote=True)
        return ""
    try:
        import base64
        from io import BytesIO

        from PIL import Image

        image = Image.open(local)
        image.load()
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        elif image.mode == "L":
            image = image.convert("RGB")
        max_side = 1400
        w, h = image.size
        if max(w, h) > max_side:
            scale = max_side / float(max(w, h))
            image = image.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=82, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        rel = path if path.startswith("/api/v1/files/") else src
        return html.escape(rel, quote=True)


def settings_resolve_upload(name: str) -> Path | None:
    from app.core.config import settings

    if ".." in name or "/" in name or "\\" in name:
        return None
    return settings.resolve_path("./data/uploads") / name


def settings_resolve_export(name: str) -> Path | None:
    from app.core.config import settings

    if ".." in name or "/" in name or "\\" in name:
        return None
    return settings.resolve_path("./data/exports") / name


def _architecture(sid: str, sec: dict[str, Any], index: int, total: int) -> str:
    tiers = []
    layers = _dict_list(sec.get("layers") or sec.get("architecture") or sec.get("items"))
    for i, layer in enumerate(layers[:6]):
        name = layer.get("name") or layer.get("tier") or layer.get("title") or f"L{i+1}"
        pills = _str_list(layer.get("items") or layer.get("nodes"))
        pills_html = "".join(f"<span>{_esc(p)}</span>" for p in pills[:8])
        arrow = '<div class="arch__arrow">↓</div>' if i < len(layers[:6]) - 1 else ""
        tiers.append(
            f"<div class='arch__tier'><em>{_esc(name)}</em>"
            f"<div class='arch__pills'>{pills_html}</div></div>{arrow}"
        )
    inner = f"""
      <div class="wrap wrap--narrow">
        {_kicker(sec)}{_heading(sec)}{_body(sec)}
        <div class="arch">{"".join(tiers)}</div>
      </div>
    """
    return _shell(sid, index, total, inner)


def _closing(sid: str, sec: dict[str, Any], index: int, total: int) -> str:
    points = _str_list(sec.get("talking_points") or sec.get("bullets"))
    lis = "".join(
        f"<li><span>{i:02d}</span><p>{_esc(p)}</p></li>"
        for i, p in enumerate(points[:6], 1)
    )
    inner = f"""
      <div class="wrap wrap--narrow">
        {_kicker(sec) or '<p class="kicker">汇报口径</p>'}
        {_heading(sec) or "<h2>建议今天拍板的三件事</h2>"}
        {_body(sec)}
        <ol class="talk">{lis}</ol>
      </div>
    """
    return _shell(sid, index, total, inner)


def _str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            import json

            try:
                parsed = json.loads(text)
                value = parsed
            except json.JSONDecodeError:
                return [line.strip(" •-") for line in text.splitlines() if line.strip()]
        else:
            return [line.strip(" •-") for line in text.splitlines() if line.strip()]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, dict):
            text = item.get("text") or item.get("title") or item.get("value") or ""
        else:
            text = item
        s = str(text).strip()
        if s:
            out.append(s)
    return out


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        import json

        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _theme_css(theme: dict[str, str]) -> str:
    return "\n".join(f"    --{k}: {v};" for k, v in theme.items())


_DOCUMENT = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
{theme_css}
      --font: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; height: 100%; }}
    body {{
      font-family: var(--font);
      color: var(--ink);
      background: var(--bg);
    }}
    .progress {{
      position: fixed; top: 0; left: 0; height: 3px; width: 0;
      background: var(--accent); z-index: 40; transition: width .2s ease;
    }}
    .top {{
      position: fixed; top: 12px; left: 18px; right: 18px; z-index: 30;
      display: flex; justify-content: space-between; align-items: center;
      pointer-events: none;
    }}
    .top span, .top button {{
      pointer-events: auto;
      background: color-mix(in srgb, var(--surface) 86%, transparent);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 12px;
      font-size: 12px;
      color: var(--muted);
    }}
    .top button {{
      cursor: pointer; font-weight: 700; color: var(--ink);
    }}
    .dots {{
      position: fixed; right: 18px; top: 50%; transform: translateY(-50%);
      z-index: 30; display: flex; flex-direction: column; gap: 8px;
    }}
    .dots a {{
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--faint); opacity: .45; text-indent: -999px; overflow: hidden;
    }}
    .dots a.active {{ opacity: 1; background: var(--accent); transform: scale(1.25); }}
    main {{
      height: 100vh;
      overflow: auto;
      scroll-snap-type: y mandatory;
      scroll-behavior: smooth;
    }}
    .sec {{
      min-height: 100vh;
      scroll-snap-align: start;
      padding: 88px 64px 64px;
      display: flex;
      align-items: center;
      position: relative;
      background:
        radial-gradient(900px 420px at 12% -10%, color-mix(in srgb, var(--accent) 18%, transparent), transparent 55%),
        var(--bg2);
    }}
    .sec--hero {{
      background: var(--hero);
      color: var(--hero_ink);
    }}
    .sec__index {{
      position: absolute; top: 88px; right: 64px;
      font-size: 12px; letter-spacing: .12em; color: var(--faint);
    }}
    .sec--hero .sec__index {{ color: var(--hero_muted); }}
    .wrap {{ width: min(1080px, 100%); margin: 0 auto; }}
    .wrap--narrow {{ width: min(860px, 100%); }}
    h1, h2, h3 {{ margin: 0 0 12px; letter-spacing: -.03em; }}
    h1 {{ font-size: clamp(40px, 6vw, 72px); line-height: 1.08; }}
    h2 {{ font-size: clamp(28px, 4vw, 44px); line-height: 1.15; }}
    h3 {{ font-size: 20px; }}
    p {{ color: var(--muted); line-height: 1.7; font-size: 17px; }}
    .sec--hero p {{ color: var(--hero_muted); }}
    .kicker {{
      font-size: 12px; letter-spacing: .18em; text-transform: uppercase;
      color: var(--accent); font-weight: 700; margin-bottom: 10px;
    }}
    .sec--hero .kicker {{ color: var(--accent); }}
    .lede {{ font-size: 22px; max-width: 42ch; }}
    .hero {{
      display: flex; align-items: center; justify-content: space-between;
      gap: 48px; width: min(1100px, 100%);
    }}
    .hero__copy {{ flex: 1; min-width: 0; }}
    .hero__photo {{
      flex: 0 0 auto; width: min(280px, 32vw);
    }}
    .hero__photo img {{
      display: block; width: 100%; aspect-ratio: 3 / 4;
      object-fit: cover; object-position: top;
      border-radius: 18px; background: #fff;
      border: 3px solid rgba(255,255,255,.35);
      box-shadow: 0 18px 40px rgba(0,0,0,.28);
    }}
    .hero__brand {{
      font-weight: 800; letter-spacing: .2em; text-transform: uppercase;
      font-size: 12px; margin-bottom: 24px; color: var(--accent);
    }}
    .hero__meta {{ margin-top: 28px; font-size: 14px; color: var(--hero_muted); }}
    .hint {{ margin-top: 10px; font-size: 12px !important; opacity: .8; }}
    .bullets {{ padding-left: 18px; }}
    .bullets li {{ margin: 8px 0; color: var(--ink); }}
    .sec--hero .bullets li {{ color: var(--hero_ink); }}
    .code {{
      margin-top: 18px;
      font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
      font-size: 13.5px;
      line-height: 1.5;
      background: #0f1720;
      color: #e7eef5;
      padding: 18px 20px;
      border-radius: 14px;
      overflow: auto;
      max-height: 62vh;
      white-space: pre;
      box-shadow: 0 12px 32px rgba(15, 23, 32, 0.18);
    }}
    .code code {{ font: inherit; }}
    .kpi-grid, .card-grid {{
      display: grid; gap: 16px; margin-top: 28px;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    }}
    .kpi, .card, .split article, .arch__tier {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 22px;
    }}
    .kpi strong {{ display: block; font-size: 36px; margin: 8px 0; }}
    .kpi__label, .kpi__hint, .card__tag {{
      font-size: 12px; color: var(--faint); letter-spacing: .06em;
    }}
    .split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 24px; }}
    .tl {{ list-style: none; padding: 0; border-left: 2px solid var(--accent); margin: 24px 0 0 8px; }}
    .tl li {{ padding: 0 0 22px 22px; position: relative; }}
    .tl li::before {{
      content: ""; position: absolute; left: -7px; top: 6px;
      width: 12px; height: 12px; border-radius: 50%; background: var(--accent);
    }}
    .tl__when {{ font-size: 12px; color: var(--accent); font-weight: 700; }}
    .quote blockquote {{
      font-size: clamp(26px, 4vw, 40px); line-height: 1.3; color: var(--ink);
      margin: 0; font-weight: 650;
    }}
    .quote cite {{ display: block; margin-top: 16px; color: var(--muted); }}
    .arch {{ margin-top: 24px; }}
    .arch__pills {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
    .arch__pills span {{
      background: color-mix(in srgb, var(--accent) 12%, var(--surface));
      color: var(--accent2); border-radius: 999px; padding: 4px 10px; font-size: 13px;
    }}
    .arch__arrow {{ text-align: center; color: var(--accent); margin: 8px 0; font-size: 18px; }}
    .talk {{ list-style: none; padding: 0; margin: 28px 0 0; }}
    .talk li {{
      display: flex; gap: 16px; align-items: flex-start;
      padding: 16px 0; border-top: 1px solid var(--line);
    }}
    .talk span {{
      font-weight: 800; color: var(--accent); font-size: 20px; min-width: 36px;
    }}
    .talk p {{ margin: 0; color: var(--ink); font-size: 18px; }}
    .fig-stage {{
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(240px, 0.7fr);
      gap: 28px;
      align-items: center;
      width: min(1180px, 100%);
    }}
    .fig-frame {{
      margin: 0;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px;
    }}
    .fig-frame img {{
      display: block;
      width: 100%;
      max-height: 68vh;
      object-fit: contain;
      background: #fff;
    }}
    .fig-cap {{
      margin-top: 8px;
      font-size: 13px;
      color: var(--muted);
    }}
    .fig-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }}
    .fig-missing {{ color: var(--faint); }}
    @media (max-width: 800px) {{
      .sec {{ padding: 72px 22px 40px; }}
      .split, .fig-stage {{ grid-template-columns: 1fr; }}
      .hero {{ flex-direction: column-reverse; gap: 24px; }}
      .hero__photo {{ width: min(200px, 52vw); }}
      .dots {{ display: none; }}
    }}
  </style>
</head>
<body>
  <div class="progress" id="bar"></div>
  <div class="top">
    <span>{brand} · 网页汇报</span>
    <button type="button" id="fs">全屏演示</button>
  </div>
  <nav class="dots" id="dots">{nav}</nav>
  <main id="deck">
    {body}
  </main>
  <script>
    const main = document.getElementById("deck");
    const sections = [...main.querySelectorAll("section")];
    const dots = [...document.querySelectorAll("#dots a")];
    const bar = document.getElementById("bar");
    const go = (i) => sections[Math.max(0, Math.min(sections.length - 1, i))]?.scrollIntoView({{behavior:"smooth"}});
    const current = () => {{
      const top = main.scrollTop;
      let idx = 0;
      sections.forEach((s, i) => {{ if (s.offsetTop <= top + 80) idx = i; }});
      return idx;
    }};
    const sync = () => {{
      const i = current();
      dots.forEach((d, n) => d.classList.toggle("active", n === i));
      bar.style.width = ((i + 1) / sections.length * 100) + "%";
    }};
    main.addEventListener("scroll", sync, {{passive:true}});
    dots.forEach((d, i) => d.addEventListener("click", (e) => {{ e.preventDefault(); go(i); }}));
    document.addEventListener("keydown", (e) => {{
      if (["ArrowDown","PageDown"," "].includes(e.key)) {{ e.preventDefault(); go(current()+1); }}
      if (["ArrowUp","PageUp"].includes(e.key)) {{ e.preventDefault(); go(current()-1); }}
      if (e.key === "Home") {{ e.preventDefault(); go(0); }}
      if (e.key === "End") {{ e.preventDefault(); go(sections.length-1); }}
      if (e.key === "f" || e.key === "F") document.documentElement.requestFullscreen?.();
    }});
    document.getElementById("fs").onclick = () => document.documentElement.requestFullscreen?.();
    sync();
  </script>
</body>
</html>
"""
