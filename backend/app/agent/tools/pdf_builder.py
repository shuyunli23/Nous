"""Designed PDF document builder for Nous ``create_pdf``.

Produces an A4 tutorial/handout (not slides): cover, flowing sections,
code panels, bullets, page numbers. Chinese text uses a local CJK font.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Nous teal
_ACCENT = colors.HexColor("#0F8F86")
_ACCENT_DARK = colors.HexColor("#0B6F68")
_TEXT = colors.HexColor("#102033")
_MUTED = colors.HexColor("#5B6B7C")
_HAIRLINE = colors.HexColor("#D5DEDC")
_PAGE_BG = colors.HexColor("#F4F7F6")
_CODE_BG = colors.HexColor("#1B222C")
_CODE_FG = colors.HexColor("#E6EDF3")
_SURFACE = colors.white

_CJK_CANDIDATES = [
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\msyh.ttf"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
]

_MONO_CANDIDATES = [
    Path(r"C:\Windows\Fonts\consola.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    Path("/System/Library/Fonts/Menlo.ttc"),
]

_FONTS_READY = False
_BODY_FONT = "Helvetica"
_BOLD_FONT = "Helvetica-Bold"
_MONO_FONT = "Courier"


def _register_font(name: str, path: Path, *, subfont_index: int = 0) -> bool:
    try:
        if path.suffix.lower() == ".ttc":
            pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=subfont_index))
        else:
            pdfmetrics.registerFont(TTFont(name, str(path)))
        return True
    except Exception:  # noqa: BLE001
        return False


def _ensure_fonts() -> None:
    global _FONTS_READY, _BODY_FONT, _BOLD_FONT, _MONO_FONT
    if _FONTS_READY:
        return
    for path in _CJK_CANDIDATES:
        if path.is_file() and _register_font("NousCJK", path):
            _BODY_FONT = "NousCJK"
            if path.suffix.lower() == ".ttc":
                if _register_font("NousCJK-Bold", path, subfont_index=0):
                    _BOLD_FONT = "NousCJK-Bold"
                else:
                    _BOLD_FONT = "NousCJK"
            else:
                bold = path.with_name(path.name.replace(".ttf", "bd.ttf"))
                if bold.is_file() and _register_font("NousCJK-Bold", bold):
                    _BOLD_FONT = "NousCJK-Bold"
                else:
                    _BOLD_FONT = "NousCJK"
            break
    for path in _MONO_CANDIDATES:
        if path.is_file() and _register_font("NousMono", path):
            _MONO_FONT = "NousMono"
            break
    _FONTS_READY = True


def _styles() -> dict[str, ParagraphStyle]:
    _ensure_fonts()
    base = getSampleStyleSheet()
    return {
        "cover_brand": ParagraphStyle(
            "cover_brand",
            parent=base["Normal"],
            fontName=_BOLD_FONT,
            fontSize=11,
            textColor=colors.white,
            tracking=1.2,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Normal"],
            fontName=_BOLD_FONT,
            fontSize=28,
            leading=36,
            textColor=_TEXT,
            alignment=TA_LEFT,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Normal"],
            fontName=_BODY_FONT,
            fontSize=12,
            leading=18,
            textColor=_MUTED,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Normal"],
            fontName=_BOLD_FONT,
            fontSize=16,
            leading=22,
            textColor=_TEXT,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Normal"],
            fontName=_BOLD_FONT,
            fontSize=13,
            leading=18,
            textColor=_ACCENT_DARK,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName=_BODY_FONT,
            fontSize=10.5,
            leading=16,
            textColor=_TEXT,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontName=_BODY_FONT,
            fontSize=10.5,
            leading=15,
            textColor=_TEXT,
            leftIndent=4,
        ),
        "code": ParagraphStyle(
            "code",
            parent=base["Code"],
            fontName=_BODY_FONT if _BODY_FONT != "Helvetica" else _MONO_FONT,
            fontSize=8.5,
            leading=12,
            textColor=_CODE_FG,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["Normal"],
            fontName=_BOLD_FONT,
            fontSize=8,
            textColor=_ACCENT,
            spaceAfter=2,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName=_BODY_FONT,
            fontSize=8,
            textColor=_MUTED,
        ),
    }


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _draw_page(canvas, doc, *, brand: str, title: str) -> None:
    canvas.saveState()
    canvas.setFillColor(_PAGE_BG)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setFillColor(_ACCENT)
    canvas.rect(0, 0, 4.5 * mm, A4[1], fill=1, stroke=0)
    canvas.setStrokeColor(_HAIRLINE)
    canvas.setLineWidth(0.4)
    canvas.line(16 * mm, 14 * mm, A4[0] - 16 * mm, 14 * mm)
    canvas.setFillColor(_MUTED)
    canvas.setFont(_BODY_FONT, 8)
    canvas.drawString(16 * mm, 8 * mm, brand)
    canvas.drawRightString(A4[0] - 16 * mm, 8 * mm, f"{title}  ·  {doc.page}")
    canvas.restoreState()


def _code_block(code: str, language: str, styles: dict[str, ParagraphStyle]):
    lang = (language or "code").strip() or "code"
    header = Paragraph(_escape(lang.upper()), styles["caption"])
    # Keep spaces; Preformatted handles newlines
    body = Preformatted(code.replace("\t", "    ") or " ", styles["code"])
    inner = Table(
        [[header], [body]],
        colWidths=[A4[0] - 40 * mm],
    )
    inner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _CODE_BG),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (0, 0), 6),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    wrap = Table([[inner]], colWidths=[A4[0] - 36 * mm])
    wrap.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _CODE_BG),
                ("BOX", (0, 0), (-1, -1), 0, _CODE_BG),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return wrap


def _cover(title: str, subtitle: str, brand: str, styles: dict[str, ParagraphStyle]):
    brand_p_style = styles["cover_brand"]
    title_p = Paragraph(_escape(title), styles["cover_title"])
    sub_p = Paragraph(_escape(subtitle), styles["cover_sub"]) if subtitle else Spacer(1, 1)
    banner = Table(
        [[Paragraph(_escape(brand.upper()), brand_p_style)]],
        colWidths=[A4[0] - 36 * mm],
        rowHeights=[18 * mm],
    )
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _ACCENT_DARK),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    accent = Table([[""]], colWidths=[18 * mm], rowHeights=[2.2 * mm])
    accent.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _ACCENT)]))
    return [
        banner,
        Spacer(1, 28 * mm),
        accent,
        Spacer(1, 8 * mm),
        title_p,
        Spacer(1, 8 * mm),
        sub_p,
        Spacer(1, 16 * mm),
        Paragraph(_escape("Nous 生成的学习讲义 · 可直接阅读与打印"), styles["cover_sub"]),
        PageBreak(),
    ]


def _normalize_sections(raw: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in raw[:80]:
        if isinstance(item, str) and item.strip():
            out.append({"heading": item.strip(), "body": ""})
            continue
        if not isinstance(item, dict):
            continue
        out.append(item)
    return out


def build_pdf(
    *,
    path: Path,
    title: str,
    sections: list[dict[str, Any]],
    subtitle: str | None = None,
    brand: str = "Nous",
) -> int:
    """Write a PDF to ``path``. Returns page count."""
    _ensure_fonts()
    styles = _styles()
    brand_text = (brand or "Nous").strip() or "Nous"
    title_text = (title or "Untitled").strip() or "Untitled"
    sub_text = (subtitle or "").strip()

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=title_text,
        author=brand_text,
    )

    story: list[Any] = []
    story.extend(_cover(title_text, sub_text, brand_text, styles))

    for item in _normalize_sections(sections):
        heading = str(item.get("heading") or item.get("title") or "").strip()
        level = int(item.get("level") or 1)
        body = str(item.get("body") or item.get("text") or item.get("notes") or "").strip()
        bullets = item.get("bullets") or item.get("points") or item.get("explain") or []
        if isinstance(bullets, str):
            bullets = [bullets]
        code = item.get("code") or item.get("source") or item.get("snippet")
        language = str(item.get("language") or item.get("lang") or "code")

        block: list[Any] = []
        if heading:
            style = styles["h1"] if level <= 1 else styles["h2"]
            block.append(Paragraph(_escape(heading), style))
            if level <= 1:
                rule = Table([[""]], colWidths=[22 * mm], rowHeights=[1.4 * mm])
                rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _ACCENT)]))
                block.append(rule)
                block.append(Spacer(1, 6))
        if body:
            for para in body.split("\n\n"):
                chunk = para.strip()
                if chunk:
                    block.append(Paragraph(_escape(chunk).replace("\n", "<br/>"), styles["body"]))
        if bullets:
            items = []
            for b in bullets:
                text = str(b.get("text") if isinstance(b, dict) else b).strip()
                if text:
                    items.append(
                        ListItem(
                            Paragraph(_escape(text), styles["bullet"]),
                            leftIndent=12,
                            bulletColor=_ACCENT,
                        )
                    )
            if items:
                block.append(
                    ListFlowable(
                        items,
                        bulletType="bullet",
                        start="▸",
                        leftIndent=16,
                        bulletFontName=_BOLD_FONT,
                        bulletFontSize=9,
                        spaceBefore=2,
                        spaceAfter=8,
                    )
                )
        if code:
            code_text = code if isinstance(code, str) else "\n".join(str(x) for x in code)
            block.append(Spacer(1, 4))
            block.append(_code_block(code_text, language, styles))
            block.append(Spacer(1, 10))
        if block:
            story.append(KeepTogether(block))

    def _on_page(canvas, doc_):
        _draw_page(canvas, doc_, brand=brand_text, title=title_text)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return int(getattr(doc, "page", 1) or 1)
