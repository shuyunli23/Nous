"""todo_write validation and prompt injection (no LLM)."""

from __future__ import annotations

from app.agent.todo import (
    TODO_GUIDANCE,
    apply_todo_write,
    format_todos_for_prompt,
    unfinished_todos,
    validate_todos,
    wants_structured_plan,
)


def test_rejects_empty_and_duplicates() -> None:
    assert validate_todos([])[1]
    assert validate_todos(None)[1]
    todos, err = validate_todos(
        [
            {"content": "a", "status": "pending"},
            {"content": "A", "status": "pending"},
        ]
    )
    assert todos is None
    assert "duplicate" in (err or "")


def test_rejects_extra_keys_and_two_in_progress() -> None:
    _, err = validate_todos(
        [{"content": "a", "status": "pending", "id": "1"}]
    )
    assert err and "only `content`" in err
    _, err = validate_todos(
        [
            {"content": "a", "status": "in_progress"},
            {"content": "b", "status": "in_progress"},
        ]
    )
    assert err and "at most one" in err


def test_unfinished_todos_skips_completed() -> None:
    leftover = unfinished_todos(
        [
            {"content": "搜资料", "status": "completed"},
            {"content": "写脚本", "status": "in_progress"},
            {"content": "做汇报页", "status": "pending"},
        ]
    )
    assert leftover == ["写脚本", "做汇报页"]


def test_apply_returns_harness_shaped_ack() -> None:
    result = apply_todo_write(
        [
            {"content": "搜资料", "status": "completed"},
            {"content": "写页面", "status": "in_progress"},
            {"content": "核对 inspect", "status": "pending"},
        ]
    )
    assert result["ok"] is True
    assert result["counts"] == {"pending": 1, "inProgress": 1, "completed": 1}
    assert "1 pending" in result["message"]
    assert result["todos"][1]["status"] == "in_progress"


def test_prompt_lists_standing_plan() -> None:
    text = format_todos_for_prompt(
        [
            {"content": "clone repo", "status": "completed"},
            {"content": "run tests", "status": "in_progress"},
        ]
    )
    assert "[x] clone repo" in text
    assert "[>] run tests" in text
    assert "todo_write" in text


def test_complex_goal_wants_a_checklist() -> None:
    assert wants_structured_plan(
        "search first and then make a demo page please",
        ["create_webpage"],
    )
    assert wants_structured_plan("crop then webpage", ["crop_image", "create_webpage"])
    assert not wants_structured_plan("weather today", [])


def test_guidance_mentions_wholesale_replace() -> None:
    assert "ENTIRE list" in TODO_GUIDANCE
    assert "in_progress" in TODO_GUIDANCE
