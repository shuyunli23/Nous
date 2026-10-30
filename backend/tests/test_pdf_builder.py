"""Document regressions: actual pages, complete code, rich blocks and glyphs."""

from __future__ import annotations

from pathlib import Path
import ast
import re

import fitz
from PIL import Image
from pypdf import PdfReader
import pytest

from app.agent.tools import pdf_builder as builder


def _read(path: Path) -> tuple[PdfReader, str]:
    reader = PdfReader(path)
    return reader, "\n".join(page.extract_text() or "" for page in reader.pages)


def _require_cjk() -> None:
    builder._ensure_fonts()
    if builder._BODY_FONT == "Helvetica":
        pytest.skip("No embeddable CJK font on this test host.")


def test_legacy_sections_flow_after_intro_without_empty_cover(tmp_path: Path) -> None:
    target = tmp_path / "legacy.pdf"
    count = builder.build_pdf(path=target, title="A small lesson", sections=[{
        "heading": "First explanation", "body": "A short independent explanation.",
        "bullets": ["The state is shared.", "Every update follows one protocol."],
        "code": "int value = 1;\n    value++;", "language": "java",
    }])
    reader, text = _read(target)
    assert count == len(reader.pages) == 1
    assert "First explanation" in text
    assert "    value++;" in text
    assert "\u00a0" not in text


def test_long_code_splits_without_dropping_lines_or_indentation(tmp_path: Path) -> None:
    source = "\n".join(f"    int value_{index:03d} = {index};" for index in range(190))
    target = tmp_path / "long-code.pdf"
    count = builder.build_pdf(path=target, title="Complete source", sections=[{
        "heading": "Program", "blocks": [{"type": "code", "language": "java", "code": source}],
    }])
    reader, text = _read(target)
    assert count == len(reader.pages) >= 4
    assert re.findall(r"int value_(\d{3})", text) == [f"{index:03d}" for index in range(190)]
    assert "    int value_000 = 0;" in text
    assert "    int value_189 = 189;" in text
    assert "continued" in text
    assert "int value_000" in reader.pages[0].extract_text()


def test_unreadably_long_code_is_rejected_instead_of_clipped(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="language-valid line breaks"):
        builder.build_pdf(path=tmp_path / "overwide.pdf", title="Long string", sections=[{
            "heading": "A long source line", "code": 'String value = "' + "x" * 600 + '";',
        }])


def test_copied_code_remains_valid_source(tmp_path: Path) -> None:
    source = 'def total(values):\n    result = 0\n    for value in values:\n        result += value\n    return result\nprint(total([1, 2, 3]))'
    target = tmp_path / "copyable.pdf"
    builder.build_pdf(path=target, title="A runnable example", sections=[{
        "heading": "Python example", "code": source, "language": "python",
    }])
    _, text = _read(target)
    copied = text[text.index("def total(values):"):text.index("print(total([1, 2, 3]))") + len("print(total([1, 2, 3]))")]
    ast.parse(copied)
    assert "        result += value" in copied


def test_cjk_comments_keep_the_same_monospace_indentation_and_copyable_source(tmp_path: Path) -> None:
    _require_cjk()
    source = ('def label():\n'
              '    # ASCII comment\n'
              '    # 中文注释\n'
              '    value = "计数" + "ASCII"\n'
              '    return value\n'
              'print(label())')
    target = tmp_path / "mixed-code.pdf"
    builder.build_pdf(path=target, title="Mixed source", sections=[{
        "heading": "An example", "code": source, "language": "python",
        "caption": "中英文代码",
    }])
    _, text = _read(target)
    copied = text[text.index("def label():"):text.index("print(label())") + len("print(label())")]
    assert copied == source
    ast.parse(copied)
    assert "\x00" not in text

    with fitz.open(target) as document:
        lines = []
        for block in document[0].get_text("rawdict")["blocks"]:
            for line in block.get("lines", []):
                characters = [(character["c"], character["origin"][0], span["font"])
                              for span in line["spans"] for character in span.get("chars", [])]
                lines.append(("".join(item[0] for item in characters), characters))
    ascii_line = next(chars for value, chars in lines if value == "    # ASCII comment")
    cjk_line = next(chars for value, chars in lines if value == "    # 中文注释")
    # The same four spaces and '#' must occupy identical x coordinates,
    # whether or not a later character on the line needs a Chinese font.
    assert [item[1] for item in cjk_line[:6]] == pytest.approx([item[1] for item in ascii_line[:6]], abs=0.01)
    mono_font = ascii_line[0][2]
    assert all(font == mono_font for character, _, font in cjk_line if character.isascii())
    mixed = next(chars for value, chars in lines if 'value = "计数" + "ASCII"' in value)
    assert all(font == mono_font for character, _, font in mixed if character.isascii())


@pytest.mark.parametrize("character", ["\x00", "\x1b", "\u0378", "\U0010ffff", "\U0001f600"])
def test_unsupported_source_characters_are_explicit_errors(tmp_path: Path, character: str) -> None:
    with pytest.raises(ValueError, match="Unsupported source character U\\+"):
        builder.build_pdf(path=tmp_path / "unsupported.pdf", title="Unsupported source", sections=[{
            "heading": "Source", "code": f'value = "{character}"', "language": "python",
        }])


def test_rich_blocks_objectives_exercises_and_reference_links(tmp_path: Path) -> None:
    _require_cjk()
    target = tmp_path / "rich.pdf"
    url = "https://example.com/docs/" + "a-very-long-path/" * 14 + "?x=1&y=2"
    builder.build_pdf(path=target, title="线程安全", audience="刚学完 Java 基础的读者",
        objectives=["解释丢失更新", "复现实验"], sections=[{
            "heading": "共享状态", "blocks": [
                {"type": "paragraph", "text": "两个线程访问同一个实例。"},
                {"type": "table", "columns": ["步骤", "线程 A", "线程 B"],
                 "rows": [["1", "读取 0", "等待"], ["2", "等待", "读取 0"]]},
                {"type": "code", "language": "java", "caption": "完整可运行代码",
                 "code": "// 保留中文注释\n    count++;"},
                {"type": "callout", "title": "使用前提", "text": "两个线程都已经结束。"},
                {"type": "exercise", "title": "练习 1", "question": "哪一次写回丢失？", "answer": "后一次覆盖前一次。"},
            ],
        }], references=[{"title": "官方规则与扩展资料", "url": url}])
    reader, text = _read(target)
    for expected in ("线程安全", "学习目标", "步骤", "完整可运行代码", "// 保留中文注释", "参考答案", "后一次覆盖前一次", "官方规则"):
        assert expected in text
    assert "\x00" not in text and "\ufffd" not in text
    links = [annotation.get_object().get("/A", {}).get("/URI")
             for page in reader.pages for annotation in page.get("/Annots", [])]
    assert url in links


def test_image_block_embeds_managed_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agent.tools import material_assets

    asset = tmp_path / "figure.png"
    Image.new("RGB", (400, 180), "teal").save(asset)
    monkeypatch.setattr(material_assets, "resolve_material_asset", lambda source: asset)
    target = tmp_path / "figure.pdf"
    builder.build_pdf(path=target, title="A figure", sections=[{
        "heading": "Original figure", "blocks": [{"type": "image", "image": "/api/v1/files/uploads/figure.png", "caption": "Original evidence"}],
    }])
    reader, text = _read(target)
    assert sum(len(page.images) for page in reader.pages) == 1
    assert "Original evidence" in text


def test_page_break_is_explicit_and_sections_are_not_discarded(tmp_path: Path) -> None:
    target = tmp_path / "breaks.pdf"
    count = builder.build_pdf(path=target, title="Two parts", sections=[
        {"heading": "Part one", "body": "First content."},
        {"heading": "Part two", "page_break_before": True, "body": "Last content."},
    ])
    reader, text = _read(target)
    assert count == len(reader.pages) == 2
    assert "Part one" in reader.pages[0].extract_text()
    assert "Part two" in reader.pages[1].extract_text()
    # The old normalizer silently dropped section 81 and later.
    many = [{"heading": f"Section {index}", "body": f"Unique content {index}."} for index in range(85)]
    builder.build_pdf(path=tmp_path / "many.pdf", title="All sections", sections=many)
    assert "Unique content 84." in _read(tmp_path / "many.pdf")[1]


@pytest.mark.parametrize("block", [
    {"type": "table", "columns": ["A", "B"], "rows": [["missing cell"]]},
    {"type": "code", "code": ""},
    {"type": "not-supported", "text": "Do not silently omit me."},
])
def test_invalid_blocks_are_actionable_errors(tmp_path: Path, block: dict) -> None:
    with pytest.raises(ValueError):
        builder.build_pdf(path=tmp_path / "invalid.pdf", title="Invalid input", sections=[{"heading": "Input", "blocks": [block]}])


def test_non_http_reference_cannot_inject_an_action(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute http"):
        builder.build_pdf(path=tmp_path / "links.pdf", title="References", sections=[{"heading": "Content"}],
                          references=[{"title": "Bad reference", "url": "javascript:alert(1)"}])
