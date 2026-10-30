"""Designed PowerPoint builder for Nous ``create_presentation``.

Blank Office layouts are avoided: every slide is drawn with theme colors,
typography, accent bars, and layout-specific composition.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any
import unicodedata

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Emu, Inches, Pt


# Widescreen 16:9
_SLIDE_W = Inches(13.333)
_SLIDE_H = Inches(7.5)
_LIGHT = RGBColor(0xF5, 0xFA, 0xF9)
_LIGHT_MUTED = RGBColor(0xC8, 0xDC, 0xD8)


@dataclass(frozen=True)
class Theme:
    id: str
    label: str
    bg: RGBColor
    surface: RGBColor
    text: RGBColor
    muted: RGBColor
    accent: RGBColor
    accent_dark: RGBColor
    on_accent: RGBColor
    hairline: RGBColor
    title_font: str
    body_font: str


THEMES: dict[str, Theme] = {
    # Aligns with Nous UI (teal + deep navy), Chinese-friendly fonts.
    "nous": Theme(
        id="nous",
        label="Nous Teal",
        bg=RGBColor(0xF5, 0xF2, 0xEB),
        surface=RGBColor(0xFF, 0xFF, 0xFF),
        text=RGBColor(0x10, 0x20, 0x33),
        muted=RGBColor(0x5B, 0x6B, 0x7A),
        accent=RGBColor(0x0F, 0x8F, 0x86),
        accent_dark=RGBColor(0x0B, 0x6F, 0x68),
        on_accent=RGBColor(0xFF, 0xFF, 0xFF),
        hairline=RGBColor(0xD5, 0xDE, 0xDC),
        title_font="Microsoft YaHei",
        body_font="Microsoft YaHei",
    ),
    "slate": Theme(
        id="slate",
        label="Slate Professional",
        bg=RGBColor(0xF5, 0xF6, 0xF8),
        surface=RGBColor(0xFF, 0xFF, 0xFF),
        text=RGBColor(0x1A, 0x1F, 0x2E),
        muted=RGBColor(0x6B, 0x73, 0x85),
        accent=RGBColor(0x2F, 0x5B, 0xE0),
        accent_dark=RGBColor(0x1E, 0x3F, 0xB0),
        on_accent=RGBColor(0xFF, 0xFF, 0xFF),
        hairline=RGBColor(0xD8, 0xDC, 0xE5),
        title_font="Microsoft YaHei",
        body_font="Microsoft YaHei",
    ),
    "ink": Theme(
        id="ink",
        label="Ink Dark",
        bg=RGBColor(0x10, 0x16, 0x20),
        surface=RGBColor(0x18, 0x22, 0x30),
        text=RGBColor(0xE8, 0xEE, 0xF3),
        muted=RGBColor(0x9A, 0xA8, 0xB5),
        accent=RGBColor(0x2D, 0xD4, 0xBF),
        accent_dark=RGBColor(0x14, 0xB8, 0xA6),
        on_accent=RGBColor(0x10, 0x16, 0x20),
        hairline=RGBColor(0x2A, 0x36, 0x48),
        title_font="Microsoft YaHei",
        body_font="Microsoft YaHei",
    ),
    "dawn": Theme(
        id="dawn",
        label="Dawn Soft",
        bg=RGBColor(0xFA, 0xF8, 0xF5),
        surface=RGBColor(0xFF, 0xFF, 0xFF),
        text=RGBColor(0x2A, 0x24, 0x1F),
        muted=RGBColor(0x7A, 0x6E, 0x63),
        accent=RGBColor(0xC4, 0x5C, 0x26),
        accent_dark=RGBColor(0x9A, 0x45, 0x18),
        on_accent=RGBColor(0xFF, 0xFF, 0xFF),
        hairline=RGBColor(0xE6, 0xDF, 0xD6),
        title_font="Microsoft YaHei",
        body_font="Microsoft YaHei",
    ),
}


def resolve_theme(theme_id: str | None) -> Theme:
    key = (theme_id or "nous").strip().lower()
    return THEMES.get(key, THEMES["nous"])


# ── low-level helpers ─────────────────────────────────────────────────────


def _set_run_font(
    run,
    *,
    size: int,
    color: RGBColor,
    bold: bool = False,
    font_name: str,
) -> None:
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font_name
    # Also set East Asian font hint so Chinese renders with YaHei on Office.
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(
        "{http://schemas.openxmlformats.org/drawingml/2006/main}ea"
    )
    if ea is None:
        ea = OxmlElement("a:ea")
        rPr.append(ea)
    ea.set("typeface", font_name)
    latin = rPr.find(
        "{http://schemas.openxmlformats.org/drawingml/2006/main}latin"
    )
    if latin is None:
        latin = OxmlElement("a:latin")
        rPr.append(latin)
    latin.set("typeface", font_name)


def _fill_solid(shape, color: RGBColor) -> None:
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    # Office theme presets may add shadows even when none were requested.
    # A local empty effect list keeps generated text surfaces flat.
    sp_pr = shape._element.spPr
    if sp_pr.find("{http://schemas.openxmlformats.org/drawingml/2006/main}effectLst") is None:
        sp_pr.append(OxmlElement("a:effectLst"))
    for effect_ref in shape._element.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}effectRef"):
        effect_ref.set("idx", "0")


def _add_rect(slide, left, top, width, height, color: RGBColor):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    _fill_solid(shape, color)
    return shape


def _add_round_rect(slide, left, top, width, height, color: RGBColor):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height
    )
    _fill_solid(shape, color)
    # Slightly tighter corners
    try:
        shape.adjustments[0] = 0.08
    except Exception:  # noqa: BLE001
        pass
    return shape


def _textbox(
    slide,
    left,
    top,
    width,
    height,
    text: str,
    *,
    theme: Theme,
    size: int,
    color: RGBColor | None = None,
    bold: bool = False,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
    font: str | None = None,
):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    try:
        tf.vertical_anchor = anchor
    except Exception:  # noqa: BLE001
        pass
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text or ""
    _set_run_font(
        run,
        size=size,
        color=color or theme.text,
        bold=bold,
        font_name=font or theme.body_font,
    )
    return box


def _set_paragraph_spacing(paragraph, *, space_before: int = 0, space_after: int = 8):
    pPr = paragraph._p.get_or_add_pPr()
    for tag, val in (("spcBef", space_before), ("spcAft", space_after)):
        el = pPr.find(
            f"{{http://schemas.openxmlformats.org/drawingml/2006/main}}{tag}"
        )
        if el is not None:
            pPr.remove(el)
        node = OxmlElement(f"a:{tag}")
        spc = OxmlElement("a:spcPts")
        spc.set("val", str(val * 100))  # hundredths of a point
        node.append(spc)
        pPr.append(node)


def _add_footer(slide, theme: Theme, page: int, total: int, brand: str) -> None:
    if page <= 0:
        return
    _add_rect(
        slide,
        Inches(0.7),
        Inches(7.15),
        Inches(11.9),
        Emu(19050),  # ~0.015"
        theme.hairline,
    )
    _textbox(
        slide,
        Inches(0.7),
        Inches(7.2),
        Inches(8),
        Inches(0.28),
        brand,
        theme=theme,
        size=10,
        color=theme.muted,
        font=theme.body_font,
    )
    _textbox(
        slide,
        Inches(10.5),
        Inches(7.2),
        Inches(2.1),
        Inches(0.28),
        f"{page} / {total}",
        theme=theme,
        size=10,
        color=theme.muted,
        align=PP_ALIGN.RIGHT,
        font=theme.body_font,
    )


def _normalize_bullets(raw: Any) -> list[tuple[str, int]]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [(raw.strip(), 0)] if raw.strip() else []
    out: list[tuple[str, int]] = []
    for item in raw:
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("content") or "").strip()
            level = int(item.get("level") or 0)
        else:
            text = str(item).strip()
            level = 0
        if text:
            out.append((text, max(0, min(level, 2))))
    if len(out) > 10:
        raise ValueError("A slide contains more than 10 bullet points. Split the material into purposeful slides or move detail to speaker_notes/PDF; no points were discarded.")
    return out


def _normalize_code(raw: Any) -> list[str]:
    """Preserve indentation; accept string or list of lines."""
    if raw is None:
        return []
    if isinstance(raw, list):
        lines = [str(x).replace("\t", "    ").rstrip("\n") for x in raw]
    else:
        text = str(raw).replace("\t", "    ").replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    # Never turn a runnable example into an incomplete snippet silently.
    return [line.replace("\u00a0", " ") for line in lines]


def _display_units(text: str) -> int:
    """Conservative width estimate: full-width CJK glyphs use two units."""
    return sum(2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1 for char in text)


def _add_picture_contained(slide, source: str, left, top, width, height, *, crop: bool = False):
    from PIL import Image

    from app.agent.tools.material_assets import resolve_material_asset

    asset = resolve_material_asset(source)
    try:
        with Image.open(asset) as image:
            if image.format not in {"PNG", "JPEG", "GIF", "BMP", "TIFF"}:
                raise ValueError("PPT images must be PNG, JPEG, GIF, BMP or TIFF. Convert this asset first.")
            pixel_w, pixel_h = image.size
            image.verify()
        if not pixel_w or not pixel_h:
            raise ValueError("Material image has invalid dimensions.")
        source_ratio = pixel_w / pixel_h
        target_ratio = width / height
        if crop:
            picture = slide.shapes.add_picture(str(asset), left, top, width=width, height=height)
            if source_ratio > target_ratio:
                picture.crop_left = picture.crop_right = (1 - target_ratio / source_ratio) / 2
            else:
                picture.crop_top = picture.crop_bottom = (1 - source_ratio / target_ratio) / 2
        else:
            factor = min(width / pixel_w, height / pixel_h)
            fitted_w, fitted_h = int(pixel_w * factor), int(pixel_h * factor)
            picture = slide.shapes.add_picture(
                str(asset), left + int((width - fitted_w) / 2), top + int((height - fitted_h) / 2),
                width=fitted_w, height=fitted_h,
            )
        return picture
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Cannot load material image '{asset.name}': {exc}") from exc


def _write_speaker_notes(slide, item: dict[str, Any]) -> None:
    notes = item.get("speaker_notes") or ""
    if isinstance(notes, list):
        notes = "\n\n".join(str(part) for part in notes)
    references = item.get("references") or []
    if isinstance(references, str):
        references = [references]
    sources: list[str] = []
    for ref in references:
        if isinstance(ref, dict):
            label = str(ref.get("title") or ref.get("label") or "").strip()
            url = str(ref.get("url") or "").strip()
            sources.append(f"{label}: {url}" if label and url else label or url)
        else:
            sources.append(str(ref))
    text = str(notes).strip()
    if sources:
        text += ("\n\n" if text else "") + "参考资料\n" + "\n".join(sources)
    if text:
        slide.notes_slide.notes_text_frame.text = text


def _infer_layout(item: dict[str, Any]) -> str:
    explicit = str(item.get("layout") or item.get("type") or "").strip().lower()
    aliases = {
        "title": "title",
        "cover": "title",
        "section": "section",
        "divider": "section",
        "bullets": "bullets",
        "bullet": "bullets",
        "content": "bullets",
        "two_column": "two_column",
        "two-column": "two_column",
        "columns": "two_column",
        "cards": "cards",
        "kpi": "cards",
        "metrics": "cards",
        "quote": "quote",
        "closing": "closing",
        "end": "closing",
        "thanks": "closing",
        "code": "code",
        "code_split": "code",
        "snippet": "code",
        "example": "code",
        "table": "table",
        "comparison": "table",
        "figure": "figure",
        "image": "figure",
        "photo": "figure",
    }
    if explicit in aliases:
        return aliases[explicit]
    if item.get("rows") is not None:
        return "table"
    if item.get("image"):
        return "figure"
    if item.get("code") or item.get("source") or item.get("snippet"):
        return "code"
    if item.get("cards") or item.get("metrics"):
        return "cards"
    if item.get("quote"):
        return "quote"
    if item.get("left_bullets") or item.get("right_bullets") or item.get("columns"):
        return "two_column"
    return "bullets"


# ── slide composers ───────────────────────────────────────────────────────


_CODE_BG = RGBColor(0x1B, 0x22, 0x2C)
_CODE_FG = RGBColor(0xE6, 0xED, 0xF3)
_CODE_DIM = RGBColor(0x8B, 0x9C, 0xAB)
_CODE_ACCENT = RGBColor(0x7E, 0xE7, 0xC7)
_CODE_FONT = "Consolas"


def _paint_bg(slide, theme: Theme) -> None:
    _add_rect(slide, 0, 0, _SLIDE_W, _SLIDE_H, theme.bg)


def _accent_bar(slide, theme: Theme) -> None:
    _add_rect(slide, 0, 0, Inches(0.12), _SLIDE_H, theme.accent)


def _slide_heading(slide, theme: Theme, heading: str) -> None:
    _textbox(
        slide,
        Inches(0.7),
        Inches(0.45),
        Inches(11.9),
        Inches(0.7),
        heading,
        theme=theme,
        size=28,
        bold=True,
        color=theme.text,
        font=theme.title_font,
    )
    _add_rect(
        slide,
        Inches(0.7),
        Inches(1.15),
        Inches(0.9),
        Inches(0.06),
        theme.accent,
    )


def _write_bullets(
    text_frame,
    bullets: list[tuple[str, int]],
    theme: Theme,
    *,
    size: int = 18,
) -> None:
    text_frame.clear()
    text_frame.word_wrap = True
    if not bullets:
        p = text_frame.paragraphs[0]
        run = p.add_run()
        run.text = ""
        return
    for i, (text, level) in enumerate(bullets):
        p = text_frame.paragraphs[0] if i == 0 else text_frame.add_paragraph()
        p.level = 0
        p.alignment = PP_ALIGN.LEFT
        indent = 0.15 + level * 0.28
        p.left_indent = Inches(indent)
        p.first_line_indent = Inches(-0.18)
        _set_paragraph_spacing(p, space_before=4 if i else 0, space_after=10)
        # Accent bullet glyph
        bullet_run = p.add_run()
        bullet_run.text = ("▸ " if level == 0 else "· ")
        _set_run_font(
            bullet_run,
            size=size - (2 if level else 0),
            color=theme.accent if level == 0 else theme.muted,
            bold=level == 0,
            font_name=theme.body_font,
        )
        body_run = p.add_run()
        body_run.text = text
        _set_run_font(
            body_run,
            size=size - (1 if level else 0),
            color=theme.text,
            bold=False,
            font_name=theme.body_font,
        )


def compose_title(
    slide,
    theme: Theme,
    *,
    title: str,
    subtitle: str,
    brand: str,
    image: str | None = None,
) -> None:
    if image:
        _paint_bg(slide, theme)
        _add_picture_contained(slide, image, Inches(6.0), 0, Inches(7.333), _SLIDE_H, crop=True)
        _textbox(slide, Inches(0.7), Inches(0.8), Inches(4.9), Inches(0.4),
                 brand.upper(), theme=theme, size=12, bold=True, color=theme.accent)
        title_width = Inches(4.9)
        title_size = min(38, max(30, int((title_width.pt - 16) / max(1, _display_units(title)) / 0.56)))
        _textbox(slide, Inches(0.7), Inches(2.15), title_width, Inches(2.1),
                 title, theme=theme, size=title_size, bold=True, font=theme.title_font)
        if subtitle:
            _textbox(slide, Inches(0.7), Inches(4.65), Inches(4.9), Inches(1.2),
                     subtitle, theme=theme, size=18, color=theme.muted)
        return
    # Split cover: left accent panel + right content
    _paint_bg(slide, theme)
    panel_w = Inches(4.4)
    _add_rect(slide, 0, 0, panel_w, _SLIDE_H, theme.accent_dark)
    # Soft accent band
    _add_rect(
        slide,
        panel_w,
        Inches(0),
        Inches(0.12),
        _SLIDE_H,
        theme.accent,
    )
    _textbox(
        slide,
        Inches(0.55),
        Inches(5.9),
        Inches(3.5),
        Inches(0.4),
        brand.upper(),
        theme=theme,
        size=12,
        bold=True,
        color=theme.on_accent,
        font=theme.body_font,
    )
    _textbox(
        slide,
        Inches(5.0),
        Inches(2.3),
        Inches(7.5),
        Inches(1.8),
        title,
        theme=theme,
        size=40,
        bold=True,
        color=theme.text,
        font=theme.title_font,
        anchor=MSO_ANCHOR.BOTTOM,
    )
    if subtitle:
        _textbox(
            slide,
            Inches(5.0),
            Inches(4.3),
            Inches(7.5),
            Inches(1.0),
            subtitle,
            theme=theme,
            size=18,
            color=theme.muted,
            font=theme.body_font,
        )
    _add_rect(
        slide,
        Inches(5.0),
        Inches(4.15),
        Inches(1.1),
        Inches(0.07),
        theme.accent,
    )


def compose_section(
    slide,
    theme: Theme,
    *,
    heading: str,
    subtitle: str,
    index_label: str,
) -> None:
    _paint_bg(slide, theme)
    _add_rect(slide, 0, 0, _SLIDE_W, _SLIDE_H, theme.accent_dark)
    _textbox(
        slide,
        Inches(0.9),
        Inches(2.4),
        Inches(11.5),
        Inches(0.4),
        index_label,
        theme=theme,
        size=14,
        bold=True,
        color=theme.accent,
        font=theme.body_font,
    )
    _textbox(
        slide,
        Inches(0.9),
        Inches(2.9),
        Inches(11.5),
        Inches(1.4),
        heading,
        theme=theme,
        size=36,
        bold=True,
        color=_LIGHT,
        font=theme.title_font,
    )
    if subtitle:
        _textbox(
            slide,
            Inches(0.9),
            Inches(4.5),
            Inches(11.5),
            Inches(0.8),
            subtitle,
            theme=theme,
            size=16,
            color=_LIGHT_MUTED,
            font=theme.body_font,
        )


def compose_bullets(
    slide,
    theme: Theme,
    *,
    heading: str,
    bullets: list[tuple[str, int]],
    page: int,
    total: int,
    brand: str,
) -> None:
    _paint_bg(slide, theme)
    _accent_bar(slide, theme)
    _slide_heading(slide, theme, heading)
    box = slide.shapes.add_textbox(
        Inches(0.7), Inches(1.5), Inches(11.9), Inches(5.3)
    )
    _write_bullets(box.text_frame, bullets, theme, size=18)
    _add_footer(slide, theme, page, total, brand)


def compose_two_column(
    slide,
    theme: Theme,
    *,
    heading: str,
    left_title: str,
    left_bullets: list[tuple[str, int]],
    right_title: str,
    right_bullets: list[tuple[str, int]],
    page: int,
    total: int,
    brand: str,
) -> None:
    _paint_bg(slide, theme)
    _accent_bar(slide, theme)
    _slide_heading(slide, theme, heading)

    gap = Inches(0.35)
    col_w = Inches(5.75)
    left_x = Inches(0.7)
    right_x = Inches(0.7) + col_w + gap
    top = Inches(1.45)
    card_h = Inches(5.2)

    for x, col_title, bullets in (
        (left_x, left_title, left_bullets),
        (right_x, right_title, right_bullets),
    ):
        _add_round_rect(slide, x, top, col_w, card_h, theme.surface)
        # subtle top accent on card
        _add_rect(slide, x, top, col_w, Inches(0.08), theme.accent)
        if col_title:
            _textbox(
                slide,
                x + Inches(0.3),
                top + Inches(0.25),
                col_w - Inches(0.55),
                Inches(0.4),
                col_title,
                theme=theme,
                size=16,
                bold=True,
                color=theme.accent_dark,
                font=theme.title_font,
            )
        body_top = top + (Inches(0.75) if col_title else Inches(0.3))
        box = slide.shapes.add_textbox(
            x + Inches(0.3),
            body_top,
            col_w - Inches(0.55),
            card_h - (Inches(1.0) if col_title else Inches(0.55)),
        )
        _write_bullets(box.text_frame, bullets, theme, size=15)

    _add_footer(slide, theme, page, total, brand)


def compose_cards(
    slide,
    theme: Theme,
    *,
    heading: str,
    cards: list[dict[str, str]],
    page: int,
    total: int,
    brand: str,
) -> None:
    _paint_bg(slide, theme)
    _accent_bar(slide, theme)
    _slide_heading(slide, theme, heading)

    if len(cards) > 4:
        raise ValueError("A cards slide supports at most 4 items. Split this content; no cards were discarded.")
    cards = cards or [{"label": "指标", "value": "—", "hint": ""}]
    n = len(cards)
    margin = Inches(0.7)
    gap = Inches(0.28)
    usable = _SLIDE_W - margin * 2 - gap * (n - 1)
    card_w = int(usable) // n
    # Keep as Length-compatible via Emu
    card_w = Emu(int(usable) // n)
    top = Inches(1.7)
    height = Inches(4.4)

    for i, card in enumerate(cards):
        left = margin + Emu(int(card_w) * i) + gap * i
        _add_round_rect(slide, left, top, card_w, height, theme.surface)
        _add_rect(slide, left, top, card_w, Inches(0.1), theme.accent)
        label = str(card.get("label") or card.get("title") or f"指标 {i + 1}")
        value = str(card.get("value") or card.get("metric") or "—")
        hint = str(card.get("hint") or card.get("desc") or card.get("subtitle") or "")
        _textbox(
            slide,
            left + Inches(0.35),
            top + Inches(0.55),
            card_w - Inches(0.7),
            Inches(0.4),
            label,
            theme=theme,
            size=13,
            color=theme.muted,
            font=theme.body_font,
        )
        _textbox(
            slide,
            left + Inches(0.35),
            top + Inches(1.3),
            card_w - Inches(0.7),
            Inches(1.4),
            value,
            theme=theme,
            size=36 if len(value) < 8 else 28,
            bold=True,
            color=theme.text,
            font=theme.title_font,
        )
        if hint:
            _textbox(
                slide,
                left + Inches(0.35),
                top + Inches(3.2),
                card_w - Inches(0.7),
                Inches(0.9),
                hint,
                theme=theme,
                size=13,
                color=theme.muted,
                font=theme.body_font,
            )

    _add_footer(slide, theme, page, total, brand)


def compose_quote(
    slide,
    theme: Theme,
    *,
    quote: str,
    attribution: str,
    page: int,
    total: int,
    brand: str,
) -> None:
    _paint_bg(slide, theme)
    _accent_bar(slide, theme)
    _textbox(
        slide,
        Inches(1.2),
        Inches(1.8),
        Inches(1.0),
        Inches(0.8),
        "“",
        theme=theme,
        size=72,
        bold=True,
        color=theme.accent,
        font=theme.title_font,
    )
    _textbox(
        slide,
        Inches(1.4),
        Inches(2.6),
        Inches(10.5),
        Inches(2.4),
        quote,
        theme=theme,
        size=26,
        bold=True,
        color=theme.text,
        font=theme.title_font,
    )
    if attribution:
        _textbox(
            slide,
            Inches(1.4),
            Inches(5.2),
            Inches(10.5),
            Inches(0.5),
            f"— {attribution}",
            theme=theme,
            size=14,
            color=theme.muted,
            font=theme.body_font,
        )
    _add_footer(slide, theme, page, total, brand)


def compose_closing(
    slide,
    theme: Theme,
    *,
    heading: str,
    subtitle: str,
    brand: str,
) -> None:
    _paint_bg(slide, theme)
    _add_rect(slide, 0, 0, _SLIDE_W, _SLIDE_H, theme.accent_dark)
    _add_rect(
        slide,
        Inches(0),
        Inches(6.9),
        _SLIDE_W,
        Inches(0.6),
        theme.accent,
    )
    _textbox(
        slide,
        Inches(0.9),
        Inches(2.6),
        Inches(11.5),
        Inches(1.2),
        heading or "谢谢",
        theme=theme,
        size=40,
        bold=True,
        color=_LIGHT,
        font=theme.title_font,
        align=PP_ALIGN.CENTER,
    )
    if subtitle:
        _textbox(
            slide,
            Inches(1.5),
            Inches(4.0),
            Inches(10.3),
            Inches(0.8),
            subtitle,
            theme=theme,
            size=16,
            color=_LIGHT_MUTED,
            font=theme.body_font,
            align=PP_ALIGN.CENTER,
        )
    _textbox(
        slide,
        Inches(0.9),
        Inches(7.0),
        Inches(11.5),
        Inches(0.35),
        brand,
        theme=theme,
        size=12,
        bold=True,
        color=theme.on_accent,
        font=theme.body_font,
        align=PP_ALIGN.CENTER,
    )


def _write_code_lines(text_frame, lines: list[str], *, size: int = 13) -> None:
    text_frame.clear()
    text_frame.word_wrap = False
    text_frame.margin_left = 0
    text_frame.margin_right = 0
    text_frame.margin_top = 0
    text_frame.margin_bottom = 0
    if not lines:
        lines = [" "]
    for i, line in enumerate(lines):
        p = text_frame.paragraphs[0] if i == 0 else text_frame.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.level = 0
        # DrawingML preserves ordinary leading spaces. Keep source copyable:
        # numbers and non-breaking spaces must not enter the code text.
        _set_paragraph_spacing(p, space_before=0, space_after=0)
        p.line_spacing = Pt(size * 1.15)
        body = p.add_run()
        body.text = line.replace("\u00a0", " ")
        _set_run_font(body, size=size, color=_CODE_FG, font_name=_CODE_FONT)


def compose_code(
    slide,
    theme: Theme,
    *,
    heading: str,
    code_lines: list[str],
    language: str,
    explain: list[tuple[str, int]],
    page: int,
    total: int,
    brand: str,
) -> None:
    """Dark monospace code panel; optional right-side explanation."""
    _paint_bg(slide, theme)
    _accent_bar(slide, theme)
    _slide_heading(slide, theme, heading)

    has_explain = bool(explain)
    code_left = Inches(0.7)
    code_top = Inches(1.4)
    code_w = Inches(7.4) if has_explain else Inches(11.9)
    code_h = Inches(5.3)

    _add_round_rect(slide, code_left, code_top, code_w, code_h, _CODE_BG)
    # language chip
    lang = (language or "code").strip() or "code"
    _textbox(
        slide,
        code_left + Inches(0.25),
        code_top + Inches(0.12),
        Inches(2.5),
        Inches(0.28),
        lang.upper(),
        theme=theme,
        size=11,
        bold=True,
        color=_CODE_ACCENT,
        font=theme.body_font,
    )
    box = slide.shapes.add_textbox(
        code_left + Inches(0.25),
        code_top + Inches(0.45),
        code_w - Inches(0.45),
        code_h - Inches(0.6),
    )
    if len(code_lines) > 24:
        raise ValueError(
            f"Code slide '{heading}' has {len(code_lines)} lines; the readable limit is 24. "
            "Split it across slides, show a focused excerpt, and put the complete program in the handout/source files."
        )
    font_size = 18 if len(code_lines) <= 14 else (15 if len(code_lines) <= 18 else 12)
    longest = max((_display_units(line) for line in code_lines), default=0)
    width_points = Emu(code_w - Inches(0.45)).pt
    while font_size > 12 and longest * font_size * 0.56 > width_points:
        font_size -= 1
    if longest * font_size * 0.56 > width_points:
        raise ValueError(
            f"A code line on slide '{heading}' is too wide for a readable slide. "
            "Break long lines at language-safe boundaries, remove the explanation column, or move the full source into the handout."
        )
    _write_code_lines(box.text_frame, code_lines, size=font_size)

    if has_explain:
        ex_left = Inches(8.35)
        _add_round_rect(
            slide, ex_left, code_top, Inches(4.25), code_h, theme.surface
        )
        _add_rect(slide, ex_left, code_top, Inches(4.25), Inches(0.08), theme.accent)
        _textbox(
            slide,
            ex_left + Inches(0.25),
            code_top + Inches(0.2),
            Inches(3.75),
            Inches(0.35),
            "要点讲解",
            theme=theme,
            size=14,
            bold=True,
            color=theme.accent_dark,
            font=theme.title_font,
        )
        body = slide.shapes.add_textbox(
            ex_left + Inches(0.2),
            code_top + Inches(0.65),
            Inches(3.85),
            code_h - Inches(0.85),
        )
        _write_bullets(body.text_frame, explain, theme, size=13)

    _add_footer(slide, theme, page, total, brand)


def compose_table(
    slide, theme: Theme, *, heading: str, columns: list[Any], rows: list[Any],
    caption: str, page: int, total: int, brand: str,
) -> None:
    """Editable evidence table with conservative bounds, never clipped rows."""
    if not isinstance(columns, list) or not 1 <= len(columns) <= 6:
        raise ValueError(f"Table slide '{heading}' needs 1-6 column headings.")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"Table slide '{heading}' needs at least one data row.")
    if len(rows) > 8:
        raise ValueError(
            f"Table slide '{heading}' has {len(rows)} data rows; the readable limit is 8. "
            "Split the table across slides or put the full table in the PDF."
        )
    if any(not isinstance(row, (list, tuple)) or len(row) != len(columns) for row in rows):
        raise ValueError(f"Every row on table slide '{heading}' must have {len(columns)} cells.")
    values = [[str(value) if value is not None else "" for value in columns]] + [
        [str(value) if value is not None else "" for value in row] for row in rows
    ]
    weights = [
        min(30, max(7, max(_display_units(row[column]) for row in values)))
        for column in range(len(columns))
    ]
    width = Inches(11.9)
    widths = [int(width * weight / sum(weights)) for weight in weights]
    widths[-1] += width - sum(widths)
    font_size = 17
    row_heights = []
    for row in values:
        lines = max(
            sum(max(1, ceil(_display_units(line) * font_size * 0.56 / max(1, Emu(cell_w).pt - 18)))
                for line in cell.split("\n"))
            for cell, cell_w in zip(row, widths)
        )
        row_heights.append(Pt(lines * font_size * 1.2 + 16))
    if sum(row_heights) > Inches(4.85):
        raise ValueError(
            f"Table slide '{heading}' is too dense to fit legibly. "
            "Shorten cell text or split the table; no rows were discarded."
        )
    _paint_bg(slide, theme)
    _slide_heading(slide, theme, heading)
    shape = slide.shapes.add_table(
        len(values), len(columns), Inches(0.7), Inches(1.6), width, sum(row_heights)
    )
    table = shape.table
    for column, cell_w in zip(table.columns, widths):
        column.width = cell_w
    for r, row in enumerate(values):
        table.rows[r].height = row_heights[r]
        for c, text in enumerate(row):
            cell = table.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _CODE_BG if r == 0 else (theme.surface if r % 2 else theme.bg)
            cell.margin_left = cell.margin_right = Pt(8)
            cell.margin_top = cell.margin_bottom = Pt(7)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.text_frame.clear()
            cell.text_frame.word_wrap = True
            for i, line in enumerate(text.split("\n")):
                p = cell.text_frame.paragraphs[0] if i == 0 else cell.text_frame.add_paragraph()
                p.line_spacing = Pt(font_size * 1.2)
                _set_paragraph_spacing(p, space_after=0)
                run = p.add_run()
                run.text = line
                _set_run_font(run, size=font_size, color=_LIGHT if r == 0 else theme.text,
                              bold=r == 0, font_name=theme.body_font)
    if caption:
        _textbox(slide, Inches(0.7), Inches(6.55), Inches(11.9), Inches(0.42),
                 caption, theme=theme, size=13, color=theme.muted)
    _add_footer(slide, theme, page, total, brand)


def compose_figure(
    slide, theme: Theme, *, heading: str, image: str, caption: str,
    page: int, total: int, brand: str,
) -> None:
    if not image:
        raise ValueError(f"Figure slide '{heading}' requires an image reference.")
    _paint_bg(slide, theme)
    _slide_heading(slide, theme, heading)
    _add_picture_contained(slide, image, Inches(0.7), Inches(1.5), Inches(11.9), Inches(4.9))
    if caption:
        _textbox(slide, Inches(0.7), Inches(6.55), Inches(11.9), Inches(0.42),
                 caption, theme=theme, size=13, color=theme.muted)
    _add_footer(slide, theme, page, total, brand)


# ── public API ────────────────────────────────────────────────────────────


def build_presentation(
    *,
    title: str,
    slides: list[dict[str, Any]],
    subtitle: str | None = None,
    theme_id: str | None = "nous",
    brand: str | None = None,
    expected_slide_count: int | None = None,
    cover_image: str | None = None,
) -> Presentation:
    """Build a designed Presentation object (not yet saved)."""
    theme = resolve_theme(theme_id)
    brand_text = (brand or "Nous").strip() or "Nous"
    deck_subtitle = (subtitle or "").strip()

    prs = Presentation()
    prs.slide_width = _SLIDE_W
    prs.slide_height = _SLIDE_H
    blank = prs.slide_layouts[6]

    if expected_slide_count is not None and (
        isinstance(expected_slide_count, bool)
        or not isinstance(expected_slide_count, int)
        or not 1 <= expected_slide_count <= 60
    ):
        raise ValueError("expected_slide_count must be an integer from 1 to 60, including the cover.")
    if not slides or len(slides) > 60:
        raise ValueError("Presentation must contain 1-60 slide objects; split larger decks explicitly.")
    normalized: list[dict[str, Any]] = []
    for raw in slides:
        if not isinstance(raw, dict):
            raise ValueError("Each slide must be an object with a heading and content.")
        item = dict(raw)
        item["_layout"] = _infer_layout(item)
        if not str(item.get("heading") or item.get("title") or "").strip():
            if item["_layout"] == "quote":
                item["heading"] = "引用"
            elif item["_layout"] == "closing":
                item["heading"] = "谢谢"
            elif item["_layout"] == "code":
                item["heading"] = "代码示例"
            else:
                item["heading"] = "内容"
        normalized.append(item)

    # Auto cover if caller didn't start with a title layout
    has_cover = bool(normalized) and normalized[0]["_layout"] == "title"
    content_slides = normalized if has_cover or expected_slide_count is not None else [
        {
            "heading": title,
            "subtitle": deck_subtitle or "Generated by Nous",
            "_layout": "title",
        },
        *normalized,
    ]

    # Ensure a closing slide when deck has real content and no closing
    if (expected_slide_count is None and content_slides
            and content_slides[-1]["_layout"] != "closing" and len(content_slides) >= 3):
        content_slides.append(
            {
                "heading": "谢谢",
                "subtitle": "欢迎交流与反馈",
                "_layout": "closing",
            }
        )

    if expected_slide_count is not None and len(content_slides) != expected_slide_count:
        raise ValueError(
            f"Expected exactly {expected_slide_count} slides including the cover, received {len(content_slides)}. "
            "Provide the complete ordered slide list; the builder will not add cover or closing slides in exact-count mode."
        )
    if cover_image:
        if content_slides[0]["_layout"] != "title":
            raise ValueError("cover_image requires the first slide to use layout='title'.")
        content_slides[0].setdefault("image", cover_image)

    # Page numbers skip title + closing for a cleaner feel? Count all content pages.
    numbered = [
        i
        for i, s in enumerate(content_slides)
        if s["_layout"] not in {"title", "closing"}
    ]
    total_numbered = max(len(numbered), 1)
    page_cursor = 0
    section_idx = 0

    for slide_number, item in enumerate(content_slides, start=1):
        layout = item["_layout"]
        heading = str(item.get("heading") or item.get("title") or "").strip()
        sub = str(
            item.get("subtitle")
            or item.get("notes")
            or item.get("body")
            or ""
        ).strip()
        slide = prs.slides.add_slide(blank)
        _write_speaker_notes(slide, item)

        if layout == "title":
            compose_title(
                slide,
                theme,
                title=heading or title,
                subtitle=sub or deck_subtitle,
                brand=brand_text,
                image=item.get("image") or item.get("cover_image"),
            )
            continue

        if layout == "section":
            section_idx += 1
            compose_section(
                slide,
                theme,
                heading=heading,
                subtitle=sub,
                index_label=f"PART {section_idx:02d}",
            )
            continue

        if layout == "closing":
            compose_closing(
                slide,
                theme,
                heading=heading or "谢谢",
                subtitle=sub or "Generated by Nous",
                brand=brand_text,
            )
            continue

        page_cursor += 1
        page = slide_number if expected_slide_count is not None else page_cursor
        total = expected_slide_count or total_numbered

        if layout == "table":
            compose_table(
                slide, theme, heading=heading, columns=item.get("columns") or [],
                rows=item.get("rows") or [], caption=str(item.get("caption") or ""),
                page=page, total=total, brand=brand_text,
            )
            continue

        if layout == "figure":
            compose_figure(
                slide, theme, heading=heading, image=str(item.get("image") or ""),
                caption=str(item.get("caption") or ""), page=page, total=total, brand=brand_text,
            )
            continue

        if layout == "two_column":
            columns = item.get("columns") or []
            left = columns[0] if isinstance(columns, list) and len(columns) > 0 else {}
            right = columns[1] if isinstance(columns, list) and len(columns) > 1 else {}
            if not isinstance(left, dict):
                left = {}
            if not isinstance(right, dict):
                right = {}
            left_bullets = _normalize_bullets(
                item.get("left_bullets") or left.get("bullets") or left.get("points")
            )
            right_bullets = _normalize_bullets(
                item.get("right_bullets") or right.get("bullets") or right.get("points")
            )
            compose_two_column(
                slide,
                theme,
                heading=heading,
                left_title=str(
                    item.get("left_heading") or left.get("heading") or left.get("title") or ""
                ),
                left_bullets=left_bullets,
                right_title=str(
                    item.get("right_heading")
                    or right.get("heading")
                    or right.get("title")
                    or ""
                ),
                right_bullets=right_bullets,
                page=page,
                total=total,
                brand=brand_text,
            )
            continue

        if layout == "code":
            code_lines = _normalize_code(
                item.get("code")
                or item.get("source")
                or item.get("snippet")
                or item.get("notes")
            )
            explain = _normalize_bullets(
                item.get("explain")
                or item.get("bullets")
                or item.get("points")
                or item.get("right_bullets")
            )
            # If code missing but bullets look like code lines, promote them.
            if not code_lines and explain:
                maybe = [t for t, _ in explain]
                if any(line.startswith(("    ", "\t", "public ", "class ", "if ", "for ")) for line in maybe):
                    code_lines = _normalize_code(maybe)
                    explain = []
            if not code_lines:
                raise ValueError(f"Code slide '{heading}' requires real code; provide a multiline code field.")
            compose_code(
                slide,
                theme,
                heading=heading,
                code_lines=code_lines,
                language=str(item.get("language") or item.get("lang") or "code"),
                explain=explain,
                page=page,
                total=total,
                brand=brand_text,
            )
            continue

        if layout == "cards":
            raw_cards = item.get("cards") or item.get("metrics") or []
            if not isinstance(raw_cards, list) or any(not isinstance(c, dict) for c in raw_cards):
                raise ValueError("Each card must be an object with label, value and hint.")
            cards = list(raw_cards)
            compose_cards(
                slide,
                theme,
                heading=heading,
                cards=cards,
                page=page,
                total=total,
                brand=brand_text,
            )
            continue

        if layout == "quote":
            compose_quote(
                slide,
                theme,
                quote=str(item.get("quote") or heading),
                attribution=str(item.get("attribution") or item.get("author") or ""),
                page=page,
                total=total,
                brand=brand_text,
            )
            continue

        # bullets (default)
        bullets = _normalize_bullets(
            item.get("bullets") or item.get("points")
        )
        if not bullets and sub:
            bullets = [(sub, 0)]
        compose_bullets(
            slide,
            theme,
            heading=heading,
            bullets=bullets,
            page=page,
            total=total,
            brand=brand_text,
        )

    return prs


def available_themes() -> list[dict[str, str]]:
    return [{"id": t.id, "label": t.label} for t in THEMES.values()]
