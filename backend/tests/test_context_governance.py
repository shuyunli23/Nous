"""Guard / spill / compaction — no LLM, no network."""

from __future__ import annotations

from pathlib import Path

from app.agent.context_compact import apply_window, extract_checkpoint, prune_text
from app.agent.context_guard import canonicalize_args, note_call
from app.agent.context_spill import maybe_spill
from app.core.config import settings
from app.memory.conversation_memory import compact_history_text


def test_canonical_args_ignore_key_order() -> None:
    a = canonicalize_args('{"q":"agi","n":2}')
    b = canonicalize_args({"n": 2, "q": "agi"})
    assert a == b


def test_repeat_reminder_escalates_and_ignores_todo() -> None:
    settings.guard_repeat_enabled = True
    settings.guard_repeat_thresholds = "3,5"
    settings.guard_repeat_exclude = "todo_write"
    chain: dict = {}
    reminder = None
    for _ in range(3):
        chain, reminder = note_call(chain, name="web_search", raw_args='{"query":"agi"}')
    assert reminder and "repeating the exact same tool call" in reminder
    chain, reminder = note_call(chain, name="todo_write", raw_args='{"todos":[]}')
    assert reminder is None
    assert chain["count"] == 3
    chain, reminder = note_call(chain, name="web_search", raw_args='{"query":"agi"}')
    chain, reminder = note_call(chain, name="web_search", raw_args='{"query":"agi"}')
    assert reminder and "consecutive_calls: 5" in reminder
    chain, reminder = note_call(chain, name="web_search", raw_args='{"query":"other"}')
    assert reminder is None
    assert chain["count"] == 1


def test_spill_keeps_artifact_fields(tmp_path: Path) -> None:
    settings.spill_max_inline_bytes = 200
    settings.spill_dir = str(tmp_path)
    fat = {
        "ok": True,
        "download_url": "/api/v1/files/exports/demo.html",
        "inspect": {"image_count": 1},
        "text": "x" * 4000,
    }
    slim = maybe_spill(fat, tool="fetch_url", conversation_id="abc12345")
    assert slim["spilled"] is True
    assert slim["download_url"] == fat["download_url"]
    assert slim["inspect"]["image_count"] == 1
    path = Path(slim["spill_path"])
    assert path.is_file()
    assert "x" * 100 in path.read_text(encoding="utf-8")


def test_spill_leaves_small_results() -> None:
    settings.spill_max_inline_bytes = 8000
    small = {"ok": True, "text": "hi"}
    assert maybe_spill(small, tool="calculator") is small or maybe_spill(
        small, tool="calculator"
    ) == small


def test_prune_keeps_head_and_tail() -> None:
    text = "HEAD" + ("m" * 200) + "TAIL"
    out, pruned = prune_text(text, threshold=40, head=8, tail=8)
    assert pruned is True
    assert out.startswith("HEAD")
    assert out.endswith("TAIL")
    assert "middle pruned" in out
    assert len(out) < len(text)


def test_checkpoint_mentions_user_goal() -> None:
    dropped = [
        {"role": "user", "content": "先搜索 AGI 再做成汇报页"},
        {
            "role": "assistant",
            "content": "做好了 [打开](/api/v1/files/exports/agi.html)",
        },
    ]
    text = extract_checkpoint(dropped)
    assert "<compacted-summary>" in text
    assert "AGI" in text
    assert "/api/v1/files/exports/agi.html" in text


def test_window_inserts_checkpoint_when_over_budget() -> None:
    messages = []
    for i in range(8):
        messages.append({"role": "user", "content": f"request {i} " + ("z" * 80)})
        messages.append({"role": "assistant", "content": f"answer {i} " + ("y" * 80)})
    kept, note = apply_window(
        messages,
        max_chars=300,
        max_turns=4,
        checkpoint=True,
    )
    assert note and "<compacted-summary>" in note
    assert kept[0]["role"] == "user"
    assert "<compacted-summary>" in (kept[0].get("content") or "")
    assert len(kept) <= 5


def test_tool_history_uses_prune_not_hard_cut() -> None:
    settings.compact_tool_threshold_chars = 80
    settings.compact_tool_head_chars = 20
    settings.compact_tool_tail_chars = 10
    blob = "BEGIN" + ("n" * 400) + "END"
    out = compact_history_text("tool", blob)
    assert "BEGIN" in out
    assert "END" in out
    assert len(out) < len(blob)
