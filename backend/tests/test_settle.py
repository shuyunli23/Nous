"""Mode-free settle proposal helpers (no LLM)."""

from __future__ import annotations

from app.core.exceptions import ValidationError
from app.schemas.conversation import SettleKindResult
from app.services.settle_service import (
    _validate_kinds,
    display_skill_reason,
    fallback_items,
    normalize_items,
    step_status,
    step_title,
)


def test_normalize_fills_missing_kinds() -> None:
    items = normalize_items(
        [
            {
                "kind": "skill",
                "recommended": True,
                "confidence": 0.8,
                "reason": "有可复用步骤",
            },
            {"kind": "other", "recommended": True, "reason": "ignore"},
        ]
    )
    assert [item.kind for item in items] == ["skill", "knowledge", "persona", "pack"]
    assert items[0].recommended is True
    assert items[0].reason == "有可复用步骤"
    assert items[1].recommended is False
    assert items[2].recommended is False
    assert items[3].recommended is False


def test_fallback_uses_mode_only_as_hint() -> None:
    workbench = fallback_items("workbench")
    assert workbench[0].recommended is True
    assert workbench[1].recommended is False
    assert workbench[2].recommended is False

    tutor = fallback_items("tutor")
    assert tutor[0].recommended is False
    assert tutor[1].recommended is True

    companion = fallback_items("companion")
    assert companion[2].recommended is True

    custom = fallback_items("review")
    assert all(item.recommended is False for item in custom)


def test_validate_kinds_dedupes_and_rejects_empty() -> None:
    assert _validate_kinds(["persona", "skill", "skill"]) == ["persona", "skill"]
    try:
        _validate_kinds([])
    except ValidationError:
        return
    raise AssertionError("expected ValidationError")


def test_skipped_skill_is_not_success():
    skipped = SettleKindResult(
        kind="skill",
        ok=False,
        skipped=True,
        detail="对话过于简单重复",
    )
    written = SettleKindResult(kind="skill", ok=True, skipped=False, skill_id="s1")
    failed = SettleKindResult(kind="skill", ok=False, skipped=False, error="boom")
    assert step_status(skipped) == "info"
    assert step_title("抽取 Skill", skipped) == "未写入 · 抽取 Skill"
    assert step_status(written) == "ok"
    assert step_title("抽取 Skill", written) == "已写入 · 抽取 Skill"
    assert step_status(failed) == "error"


def test_display_skill_reason_strips_extractor_english():
    assert display_skill_reason(
        "Not reusable: 对话过于简单重复 (confidence=0.30)"
    ) == "对话过于简单重复"
    assert display_skill_reason("Too few messages (1 < 4).") == "对话还太短，不够抽成 Skill。"


if __name__ == "__main__":
    test_normalize_fills_missing_kinds()
    test_fallback_uses_mode_only_as_hint()
    test_validate_kinds_dedupes_and_rejects_empty()
    test_skipped_skill_is_not_success()
    test_display_skill_reason_strips_extractor_english()
    print("ok")
