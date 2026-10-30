"""User wording, exact slide totals, and honest partial delivery."""

from pathlib import Path

import pytest

from app.agent.goal import infer_required_tools, requested_slide_count, material_delivery_gaps


@pytest.mark.parametrize("query, expected", [
    ("制作一份8页PPT和一份PDF讲义", 8),
    ("一份总计 8 页的 PPT", 8),
    ("PPT，总共8页，PDF16页", 8),
    ("把PPT改成6页", 6),
    ("八页PPT", 8),
    ("PPT共十二页", 12),
    ("20-slide PowerPoint", 20),
    ("PPT和PDF讲义，PDF13页", None),
    ("做一份PPT和PDF讲义16页", None),
])
def test_slide_total_is_about_the_presentation(query, expected):
    assert requested_slide_count(query) == expected


def test_exact_count_is_verified_even_for_a_simple_presentation(tmp_path: Path):
    trace = [{"kind": "tool", "tool": "create_presentation", "status": "ok", "inspect": {
        "kind": "pptx", "file": "deck.pptx", "slide_count": 10,
    }}]
    gaps = material_delivery_gaps("制作8页的PPT", "已完成", trace, tmp_path)
    assert any("exactly 8" in gap for gap in gaps)


def test_existing_handout_source_is_a_read_request():
    assert infer_required_tools("查看这个PPT的源码") == []
    assert infer_required_tools("把讲义里面的源码给我看看") == []
    assert "create_presentation" in infer_required_tools("做8页PPT并附完整源码")
