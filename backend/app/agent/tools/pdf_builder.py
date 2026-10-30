"""Readable PDF handouts with flowing sections, figures and splittable code.

The legacy heading/body/bullets/code shape remains valid. Rich sections append
ordered blocks, and callers can request explicit page breaks when appropriate.
"""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache
import threading
from typing import Any
from urllib.parse import urlsplit
from xml.sax.saxutils import escape, quoteattr

from PIL import Image as PillowImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak, Flowable, Image, ListFlowable, ListItem, LongTable, PageBreak,
    Paragraph, SimpleDocTemplate, Spacer, TableStyle,
)

_ACCENT = colors.HexColor("#087C7D")
_ACCENT_DARK = colors.HexColor("#086C6E")
_TEXT = colors.HexColor("#142432")
_MUTED = colors.HexColor("#586777")
_HAIRLINE = colors.HexColor("#D7DDD9")
_PAGE_BG = colors.HexColor("#FAF8F2")
_CODE_BG = colors.HexColor("#142B38")
_CODE_FG = colors.HexColor("#E5EFEE")
_CALLOUT_BG = colors.HexColor("#E9F1EE")
_CONTENT_WIDTH = A4[0] - 36 * mm
_CJK_CANDIDATES = [
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\msyh.ttf"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
    # WenQuanYi has TrueType outlines ReportLab can embed. Some Noto CJK
    # distributions have unsupported CFF outlines, hence the extra fallback.
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
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
_FONT_LOCK = threading.RLock()
_BODY_FONT = "Helvetica"
_BOLD_FONT = "Helvetica-Bold"
_MONO_FONT = "Courier"


def _register_font(name: str, path: Path, *, subfont_index: int = 0) -> bool:
    try:
        pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=subfont_index))
        return True
    except Exception:  # noqa: BLE001
        return False


def _ensure_fonts() -> None:
    global _FONTS_READY, _BODY_FONT, _BOLD_FONT, _MONO_FONT
    with _FONT_LOCK:
        if _FONTS_READY:
            return
        for path in _CJK_CANDIDATES:
            if not path.is_file() or not _register_font("NousCJK", path):
                continue
            _BODY_FONT = _BOLD_FONT = "NousCJK"
            for bold in [path.with_name(path.name.replace(".ttc", "bd.ttc")),
                         path.with_name(path.name.replace(".ttf", "bd.ttf"))]:
                if bold != path and bold.is_file() and _register_font("NousCJK-Bold", bold):
                    _BOLD_FONT = "NousCJK-Bold"
                    break
            break
        for path in _MONO_CANDIDATES:
            if path.is_file() and _register_font("NousMono", path):
                _MONO_FONT = "NousMono"
                break
        _FONTS_READY = True


def _has_cjk(text: str) -> bool:
    return any("\u2e80" <= ch <= "\ud7af" or "\uf900" <= ch <= "\ufaff" for ch in text)


def _styles() -> dict[str, ParagraphStyle]:
    _ensure_fonts()
    body = ParagraphStyle(
        "NousBody", parent=getSampleStyleSheet()["Normal"], fontName=_BODY_FONT,
        fontSize=10.5, leading=16.5, textColor=_TEXT, alignment=TA_LEFT,
        spaceAfter=8, wordWrap="CJK", splitLongWords=True,
    )
    return {
        "cover_brand": ParagraphStyle("NousBrand", parent=body, fontName=_BOLD_FONT,
                                      fontSize=10, leading=14, textColor=_ACCENT),
        "cover_title": ParagraphStyle("NousTitle", parent=body, fontName=_BOLD_FONT,
                                      fontSize=29, leading=38, spaceBefore=11, spaceAfter=13),
        "cover_sub": ParagraphStyle("NousSubtitle", parent=body, fontSize=12,
                                    leading=18, textColor=_MUTED, spaceAfter=10),
        "h1": ParagraphStyle("NousH1", parent=body, fontName=_BOLD_FONT, fontSize=17,
                             leading=24, spaceBefore=18, spaceAfter=10),
        "h2": ParagraphStyle("NousH2", parent=body, fontName=_BOLD_FONT, fontSize=13,
                             leading=19, textColor=_ACCENT_DARK, spaceBefore=10,
                             spaceAfter=7),
        "body": body,
        "bullet": ParagraphStyle("NousBullet", parent=body, spaceAfter=3),
        "caption": ParagraphStyle("NousCaption", parent=body, fontSize=8.5, leading=13,
                                  textColor=_MUTED, spaceAfter=9),
        "table": ParagraphStyle("NousTable", parent=body, fontSize=9, leading=14, spaceAfter=0),
        "table_head": ParagraphStyle("NousTableHead", parent=body, fontName=_BOLD_FONT,
                                     fontSize=9, leading=14, spaceAfter=0),
        "callout": ParagraphStyle("NousCallout", parent=body, backColor=_CALLOUT_BG,
                                  borderPadding=10, spaceBefore=5, spaceAfter=12),
        "reference": ParagraphStyle("NousReference", parent=body, fontSize=8.5,
                                    leading=13, spaceAfter=9),
    }


def _escape(text: str) -> str:
    return escape(str(text or ""))


def _paragraphs(text: str, style: ParagraphStyle) -> list[Flowable]:
    return [Paragraph(_escape(part.strip()).replace("\n", "<br/>"), style)
            for part in str(text or "").replace("\r\n", "\n").split("\n\n") if part.strip()]


def _draw_page(canvas, doc, *, brand: str, title: str) -> None:
    canvas.saveState()
    canvas.setFillColor(_PAGE_BG)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setStrokeColor(_HAIRLINE)
    canvas.setLineWidth(0.4)
    canvas.line(18 * mm, 17 * mm, A4[0] - 18 * mm, 17 * mm)
    canvas.setFillColor(_MUTED)
    canvas.setFont(_BODY_FONT, 8)
    footer = f"{brand} · {title}"
    while pdfmetrics.stringWidth(footer, _BODY_FONT, 8) > _CONTENT_WIDTH - 45:
        footer = footer[:-5].rstrip(".") + "..."
    canvas.drawString(18 * mm, 11 * mm, footer)
    canvas.drawRightString(A4[0] - 18 * mm, 11 * mm, str(doc.page))
    canvas.restoreState()


@lru_cache(maxsize=8192)
def _code_glyph_available(font_name: str, character: str) -> bool:
    """Check the actual embedded font rather than trusting its fallback width.

    TTFont.stringWidth uses the .notdef width for unknown characters, so a
    positive measured width alone cannot prove that source will render or
    extract correctly. Built-in fonts use their explicit encoding instead.
    """
    font = pdfmetrics.getFont(font_name)
    glyphs = getattr(font.face, "charToGlyph", None)
    if glyphs is not None:
        return bool(glyphs.get(ord(character)))
    try:
        encoded = character.encode("cp1252")
    except UnicodeEncodeError:
        return False
    glyph = font.encoding[encoded[0]]
    return bool(glyph and glyph != ".notdef" and glyph in font.face.glyphWidths)


def _code_runs(line: str) -> list[tuple[str, str]]:
    """Keep ASCII, especially indentation, in the monospace font on every line."""
    runs: list[tuple[str, list[str]]] = []
    for character in line:
        point = ord(character)
        # ReportLab 4.2.x's TrueType ToUnicode CMap writes BMP code units.
        # Reject supplementary characters and controls rather than producing
        # broken extraction or silently replacing the caller's source.
        if point < 32 or point == 127 or point > 0xFFFF or 0xD800 <= point <= 0xDFFF:
            raise ValueError(
                f"Unsupported source character U+{point:04X} in PDF code. "
                "Use a language-valid visible escape or provide the complete source file. "
                "No source characters were removed or replaced."
            )
        candidates = ([_MONO_FONT] if character.isascii() else [_BODY_FONT] if _has_cjk(character)
                      else [_MONO_FONT, _BODY_FONT])
        font = next((candidate for candidate in candidates
                     if _code_glyph_available(candidate, character)), None)
        if font is None:
            raise ValueError(
                f"Unsupported source character U+{point:04X} in the PDF code fonts. "
                "Use a supporting font or a language-valid visible escape; "
                "no source characters were removed or replaced."
            )
        if runs and runs[-1][0] == font:
            runs[-1][1].append(character)
        else:
            runs.append((font, [character]))
    return [(font, "".join(characters)) for font, characters in runs]


class _CodePanel(Flowable):
    """Page-splittable code with ordinary spaces and no copy-polluting line numbers.

    Ordinary source lines fit at 7-8.4pt. Reject unreadably long lines with a
    repair instruction rather than clipping or changing source semantics by
    blindly inserting a newline into a string literal.
    """

    def __init__(self, code: str, language: str = "code", caption: str = "", *, continued: bool = False, font_size: float = 8.4):
        super().__init__()
        _ensure_fonts()
        self.lines = code.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4).split("\n")
        self.line_runs = [_code_runs(line) for line in self.lines]
        self.label = " · ".join(part for part in (language.upper().strip(), caption.strip()) if part)
        self.continued = continued
        self._base_font_size = font_size
        self.font_size, self.leading = font_size, max(10.5, font_size * 1.45)
        self.spaceBefore, self.spaceAfter = 5, 11
        self.width = _CONTENT_WIDTH

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        base = self._base_font_size
        widest = max((sum(pdfmetrics.stringWidth(text, font, base) for font, text in runs)
                      for runs in self.line_runs), default=0)
        fitted = min(base, base * (availWidth - 26) / widest) if widest else base
        if fitted < 7:
            raise ValueError("A PDF code line is too long to read at 7pt. Reformat source with language-valid line breaks, or attach the full file and show a shorter excerpt. No code was truncated.")
        self.font_size, self.leading = fitted, max(10.5, fitted * 1.45)
        label = self.label + (" (continued)" if self.continued else "")
        self.header = Paragraph(_escape(label or "CODE"), ParagraphStyle(
            "NousCodeCaption", fontName=_BODY_FONT, fontSize=8, leading=11,
            textColor=colors.HexColor("#9ECAC4"), wordWrap="CJK",
        ))
        _, self.header_height = self.header.wrap(availWidth - 26, availHeight)
        self.height = 22 + self.header_height + len(self.lines) * self.leading
        return self.width, self.height

    def split(self, availWidth, availHeight):
        self.wrap(availWidth, availHeight)
        fit = int((availHeight - 22 - self.header_height) // self.leading)
        if fit < 1:
            return []
        if fit >= len(self.lines):
            return [self]
        first = _CodePanel("\n".join(self.lines[:fit]), continued=self.continued, font_size=self.font_size)
        rest = _CodePanel("\n".join(self.lines[fit:]), continued=True, font_size=self.font_size)
        first.label = rest.label = self.label
        return [first, rest]

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setFillColor(_CODE_BG)
        canvas.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        self.header.drawOn(canvas, 13, self.height - 10 - self.header_height)
        canvas.setFillColor(_CODE_FG)
        y = self.height - 15 - self.header_height - self.font_size
        for runs in self.line_runs:
            text = canvas.beginText(13, y)
            for font, value in runs:
                text.setFont(font, self.font_size)
                text.textOut(value)
            canvas.drawText(text)
            y -= self.leading
        canvas.restoreState()


def _code_block(code: str, language: str, styles=None, caption: str = "") -> Flowable:
    return _CodePanel(code, language, caption)


def _table_block(columns: Any, rows: Any, styles: dict[str, ParagraphStyle]) -> Flowable:
    if not isinstance(columns, list) or not columns or len(columns) > 8:
        raise ValueError("PDF tables need 1-8 column headings; split wider tables into smaller comparisons.")
    if not isinstance(rows, list) or not rows:
        raise ValueError("PDF table rows must be a non-empty array of arrays.")
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != len(columns):
            raise ValueError("Every PDF table row must have the same number of cells as columns.")
    values = [[Paragraph(_escape(str(v)), styles["table_head"]) for v in columns]]
    values.extend([[Paragraph(_escape(str(v)).replace("\n", "<br/>"), styles["table"]) for v in row] for row in rows])
    table = LongTable(values, colWidths=[_CONTENT_WIDTH / len(columns)] * len(columns),
                      repeatRows=1, hAlign="LEFT", splitByRow=True, splitInRow=True)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _CALLOUT_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, _ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, _HAIRLINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    table.spaceBefore, table.spaceAfter = 5, 12
    return table


def _image_block(source: str, caption: str, styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    from app.agent.tools.material_assets import resolve_material_asset

    asset = resolve_material_asset(source)
    try:
        with PillowImage.open(asset) as source_image:
            width, height = source_image.size
            if width <= 0 or height <= 0 or width * height > 40_000_000:
                raise ValueError("Material image dimensions are invalid or exceed 40 megapixels.")
            source_image.verify()
    except (OSError, PillowImage.DecompressionBombError) as exc:
        raise ValueError(f"Cannot read material image {asset.name}; use a valid PNG or JPEG.") from exc
    scale = min(_CONTENT_WIDTH / width, 155 * mm / height)
    picture = Image(str(asset), width=width * scale, height=height * scale, hAlign="LEFT")
    picture.spaceBefore, picture.spaceAfter = 5, 6
    result: list[Flowable] = [picture]
    if caption:
        result.extend(_paragraphs(caption, styles["caption"]))
    return result


def _render_block(block: dict[str, Any], styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    kind = str(block.get("type") or "paragraph").strip().lower()
    if kind in {"paragraph", "text"}:
        return _paragraphs(str(block.get("text") or block.get("body") or ""), styles["body"])
    if kind == "code":
        code = block.get("code", "")
        code = code if isinstance(code, str) else "\n".join(str(line) for line in code)
        if not code.strip():
            raise ValueError("A PDF code block is empty. Include source code or omit the block.")
        return [_code_block(code, str(block.get("language") or "code"), caption=str(block.get("caption") or ""))]
    if kind == "table":
        return [_table_block(block.get("columns"), block.get("rows"), styles)]
    if kind in {"image", "figure"}:
        return _image_block(str(block.get("image") or block.get("src") or ""), str(block.get("caption") or ""), styles)
    if kind == "callout":
        title = str(block.get("title") or "").strip()
        text = str(block.get("text") or block.get("body") or "").strip()
        result = [CondPageBreak(80), Paragraph(_escape(title), styles["h2"])] if title else []
        result.extend(_paragraphs(text, styles["callout"]))
        return result
    if kind == "exercise":
        question, answer = str(block.get("question") or "").strip(), str(block.get("answer") or "").strip()
        if not question and not answer:
            raise ValueError("A PDF exercise must include a question or an answer.")
        result = [CondPageBreak(80), Paragraph(_escape(str(block.get("title") or ("练习" if _BODY_FONT != "Helvetica" else "Exercise"))), styles["h2"])]
        result.extend(_paragraphs(question, styles["body"]))
        if answer:
            result.extend([CondPageBreak(65), Paragraph("参考答案" if _BODY_FONT != "Helvetica" else "Reference answer", styles["h2"])])
            result.extend(_paragraphs(answer, styles["body"]))
        return result
    raise ValueError(f"Unknown PDF block type '{kind}'. Use paragraph, code, table, image, callout or exercise.")


def _reference_blocks(references: Any, styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    if not references:
        return []
    if not isinstance(references, list):
        raise ValueError("PDF references must be an array of {title, url} objects.")
    result: list[Flowable] = [CondPageBreak(90), Paragraph("参考资料" if _BODY_FONT != "Helvetica" else "References", styles["h1"])]
    for index, reference in enumerate(references, 1):
        if not isinstance(reference, dict):
            raise ValueError("Each PDF reference needs title and url fields.")
        title = str(reference.get("title") or reference.get("url") or "").strip()
        url = str(reference.get("url") or "").strip()
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("PDF reference URLs must be absolute http(s) URLs.")
        result.append(Paragraph(
            f'[{index}] <link href={quoteattr(url)} color="#087C7D">{_escape(title)}</link><br/>{_escape(url)}',
            styles["reference"],
        ))
    return result


def _bullets(raw: Any, styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    if isinstance(raw, str):
        raw = [raw]
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValueError("PDF bullets must be strings in an array.")
    items = []
    for item in raw:
        text = str(item.get("text") or "") if isinstance(item, dict) else str(item)
        if text.strip():
            items.append(ListItem(Paragraph(_escape(text), styles["bullet"]), leftIndent=10))
    return [ListFlowable(items, bulletType="bullet", start="-", leftIndent=12,
                         bulletFontName=_BODY_FONT, bulletFontSize=9, spaceAfter=8)] if items else []


def _cover(title, subtitle, brand, styles, *, audience="", objectives=None, cover_image=None):
    result: list[Flowable] = [Paragraph(_escape(brand.upper()), styles["cover_brand"]),
                            Paragraph(_escape(title), styles["cover_title"])]
    if subtitle:
        result.extend(_paragraphs(subtitle, styles["cover_sub"]))
    if audience:
        prefix = "适用读者：" if _BODY_FONT != "Helvetica" else "Audience: "
        result.extend(_paragraphs(prefix + audience, styles["cover_sub"]))
    if cover_image:
        result.extend(_image_block(cover_image, "", styles))
    if objectives:
        result.append(Paragraph("学习目标" if _BODY_FONT != "Helvetica" else "Learning objectives", styles["h2"]))
        result.extend(_bullets(objectives, styles))
    result.append(Spacer(1, 7))
    # Content follows the introduction unless the caller requests a break.
    return result


def _normalize_sections(raw: list[Any]) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("PDF sections must be a non-empty array.")
    if len(raw) > 200:
        raise ValueError("PDF supports up to 200 sections. Split this document into volumes; none were discarded.")
    result = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            result.append({"heading": item.strip()})
        elif isinstance(item, dict):
            result.append(item)
        else:
            raise ValueError("Each PDF section must be an object or a heading string.")
    return result


def build_pdf(
    *, path: Path, title: str, sections: list[dict[str, Any]],
    subtitle: str | None = None, brand: str = "Nous",
    audience: str | None = None, objectives: list[str] | None = None,
    references: list[dict[str, str]] | None = None, cover_image: str | None = None,
) -> int:
    """Write an A4 handout and return its actual page count."""
    _ensure_fonts()
    normalized = _normalize_sections(sections)
    if _BODY_FONT == "Helvetica" and _has_cjk(str((title, subtitle, audience, objectives, normalized, references))):
        raise ValueError("A Chinese TrueType font is required. Install fonts-wqy-zenhei on Linux or a supported CJK font; refusing to export missing glyphs.")
    styles = _styles()
    brand_text, title_text = str(brand or "Nous").strip(), str(title or "Untitled").strip()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=23 * mm, title=title_text, author=brand_text)
    story = _cover(title_text, str(subtitle or ""), brand_text, styles,
                   audience=str(audience or ""), objectives=objectives, cover_image=cover_image)
    for item in normalized:
        if item.get("page_break_before"):
            story.append(PageBreak())
        heading = str(item.get("heading") or item.get("title") or "").strip()
        if heading:
            style = styles["h1" if int(item.get("level") or 1) <= 1 else "h2"]
            # ReportLab's keepWithNext would group a heading with the entire
            # next code flowable and push long programs onto a fresh page.
            # Reserve a few lines instead, while allowing the code to split.
            story.extend([CondPageBreak(95), Paragraph(_escape(heading), style)])
        story.extend(_paragraphs(str(item.get("body") or item.get("text") or item.get("notes") or ""), styles["body"]))
        story.extend(_bullets(item.get("bullets") or item.get("points") or item.get("explain"), styles))
        code = item.get("code") or item.get("source") or item.get("snippet")
        if code:
            story.extend(_render_block({"type": "code", "code": code,
                "language": item.get("language") or item.get("lang") or "code",
                "caption": item.get("caption") or ""}, styles))
        blocks = item.get("blocks") or []
        if not isinstance(blocks, list):
            raise ValueError("PDF section blocks must be an ordered array of content objects.")
        for block in blocks:
            if not isinstance(block, dict):
                raise ValueError("Each PDF content block must be an object with a type.")
            story.extend(_render_block(block, styles))
    story.extend(_reference_blocks(references, styles))

    def on_page(canvas, document):
        _draw_page(canvas, document, brand=brand_text, title=title_text)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return int(doc.page or 1)
