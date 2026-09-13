"""Unit tests for the Codex-inspired plan / act / verify loop (no LLM)."""

from __future__ import annotations

from pathlib import Path

from app.agent.goal import (
    ATTACH_START,
    evaluate_turn,
    extract_goal_text,
    infer_required_tools,
)
from app.agent.nodes.llm_call import should_call_tools
from app.core.config import settings
from app.agent.nodes.verify import should_continue_after_verify
from app.agent.tools.export_urls import (
    rewrite_invented_export_links,
    strip_unbacked_export_links,
)


def test_extract_goal_strips_attachment_dump() -> None:
    query = f"帮我做个 demo\n\n{ATTACH_START}\n[PAPER FIGURES] /api/v1/files/uploads/x.png"
    assert extract_goal_text(query) == "帮我做个 demo"
    assert extract_goal_text(query, title_source="帮我做个 demo") == "帮我做个 demo"


def test_infer_required_tools_routes_artifacts() -> None:
    assert infer_required_tools("把这篇论文做成 demo 网页") == ["create_webpage"]
    assert infer_required_tools("做一份 PPT") == ["create_presentation"]
    assert infer_required_tools("demo 也顺便给个 ppt") == ["create_webpage"]
    assert infer_required_tools("生成一份讲义 PDF") == ["create_pdf"]
    assert infer_required_tools("这篇 PDF 讲了什么") == []
    assert infer_required_tools("今天天气怎么样") == []
    assert infer_required_tools("加一个求职者图像") == ["create_webpage"]
    assert infer_required_tools("把简历里的一寸照片截下来加在demo里") == [
        "crop_image",
        "create_webpage",
    ]
    assert "generate_image" not in infer_required_tools("加一个求职者图像")
    assert infer_required_tools("画一张插画") == ["generate_image"]
    assert infer_required_tools("生成一张美女的图像") == ["generate_image"]
    assert infer_required_tools("这个网页的源码是？") == []
    assert infer_required_tools("把 demo 网页的 html 源码给我") == []
    assert infer_required_tools("给 demo 加一段伪代码") == ["create_webpage"]
    assert infer_required_tools("加上核心伪代码") == ["create_webpage"]


def test_evaluate_turn_missing_webpage_is_incomplete() -> None:
    verdict = evaluate_turn(
        required_tools=["create_webpage"],
        response="已生成 Demo：[打开](/api/v1/files/exports/DNPR_Demo_fake.html)",
        trace=[],
        exports_dir=Path("/tmp/nous-missing-exports"),
    )
    assert not verdict.complete
    assert verdict.missing_tools == ["create_webpage"]
    assert any("DNPR_Demo_fake.html" in url for url in verdict.invented_urls)
    assert "MUST call" in verdict.critique()


def test_evaluate_turn_open_todos_is_incomplete() -> None:
    verdict = evaluate_turn(
        required_tools=[],
        response="先跑脚本。",
        trace=[],
        exports_dir=Path("/tmp/nous-missing-exports"),
        todos=[
            {"content": "编写并运行 stats.py", "status": "in_progress"},
            {"content": "制作网页汇报", "status": "pending"},
        ],
    )
    assert not verdict.complete
    # The webpage item names a tool that never ran, so it blocks the turn.
    assert verdict.open_todos == ["制作网页汇报"]
    # Prose work no artifact can prove only earns a reminder.
    assert verdict.unverifiable_todos == ["编写并运行 stats.py"]
    critique = verdict.critique()
    assert "todo list is not finished" in critique
    assert "stats.py" in critique


def test_prose_only_todos_do_not_block_the_turn() -> None:
    """A checklist of un-inferable items must not deadlock verify."""
    verdict = evaluate_turn(
        required_tools=[],
        response="已经整理好提纲了。",
        trace=[],
        exports_dir=Path("/tmp/nous-missing-exports"),
        todos=[{"content": "整理提纲", "status": "pending"}],
    )
    assert verdict.complete
    assert verdict.open_todos == []
    assert verdict.unverifiable_todos == ["整理提纲"]


def test_artifact_settles_a_forgotten_checklist_item() -> None:
    """Model built the page but forgot the closing todo_write."""
    from app.agent.goal import settle_todos

    trace = [{"kind": "tool", "tool": "create_webpage", "status": "ok"}]
    todos = [{"content": "制作网页汇报", "status": "in_progress"}]
    settled = settle_todos(todos, trace)
    assert settled == [{"content": "制作网页汇报", "status": "completed"}]
    verdict = evaluate_turn(
        required_tools=["create_webpage"],
        response="页面好了。",
        trace=trace,
        exports_dir=Path("/tmp/nous-missing-exports"),
        todos=settled,
    )
    assert verdict.complete
    # The original list is left untouched for the caller to swap in.
    assert todos[0]["status"] == "in_progress"


def test_evaluate_turn_succeeds_after_tool() -> None:
    trace = [
        {
            "kind": "tool",
            "tool": "create_webpage",
            "status": "ok",
            "detail": "产出 /api/v1/files/exports/NexusMind_AI_301cf3433926.html",
        }
    ]
    verdict = evaluate_turn(
        required_tools=["create_webpage"],
        response="[打开汇报网页](/api/v1/files/exports/NexusMind_AI_301cf3433926.html)",
        trace=trace,
        exports_dir=Path("/tmp/nous-missing-exports"),
    )
    assert verdict.complete
    assert verdict.missing_tools == []
    assert verdict.invented_urls == []


def test_failed_required_tool_is_incomplete_until_retry_succeeds() -> None:
    failed = [
        {
            "kind": "tool",
            "tool": "create_webpage",
            "status": "error",
            "detail": "sections too large",
        }
    ]
    verdict = evaluate_turn(
        required_tools=["create_webpage"],
        response="网页生成失败",
        trace=failed,
        exports_dir=Path("/tmp/nous-missing-exports"),
    )
    assert not verdict.complete
    assert verdict.failed_tools == ["create_webpage"]


def test_should_call_tools_then_verify() -> None:
    assert (
        should_call_tools(
            {
                "tool_calls": [{"id": "1"}],
                "tool_loop_count": 0,
            }
        )
        == "tools"
    )
    assert should_call_tools({"tool_calls": [], "tool_loop_count": 0}) == "verify"
    assert should_continue_after_verify({"needs_retry": True}) == "llm_call"
    assert should_continue_after_verify({"needs_retry": False}) == "persist"


def test_strip_unbacked_export_links_drops_hallucinations() -> None:
    real = "/api/v1/files/exports/NexusMind_AI_301cf3433926.html"
    fake = "/api/v1/files/exports/DNPR_Demo_fake.html"
    text = f"真的：[打开]({real}) 假的：[打开]({fake})"
    trace = [{"kind": "tool", "status": "ok", "detail": f"产出 {real}"}]
    rewritten = rewrite_invented_export_links(text, trace)
    cleaned = strip_unbacked_export_links(rewritten, trace)
    assert real in cleaned
    assert "DNPR_Demo_fake.html" not in cleaned

    leftover = strip_unbacked_export_links(f"[打开]({fake})", [])
    assert "DNPR_Demo_fake.html" not in leftover
    assert leftover.strip() == ""


def test_hero_renders_cover_portrait() -> None:
    from app.agent.tools.html_builder import build_webpage

    path = Path("data/exports/_test_hero_photo.html")
    path.parent.mkdir(parents=True, exist_ok=True)
    build_webpage(
        path=path,
        title="陶亮梅",
        sections=[
            {
                "layout": "hero",
                "heading": "陶亮梅",
                "image": "data:image/png;base64,aaa",
            }
        ],
    )
    html = path.read_text(encoding="utf-8")
    assert "hero__photo" in html
    assert "<img" in html
    path.unlink(missing_ok=True)


def test_evaluate_turn_requires_photo_in_html(tmp_path: Path | None = None) -> None:
    exports = Path("data/exports")
    exports.mkdir(parents=True, exist_ok=True)
    empty = exports / "_test_no_photo.html"
    empty.write_text("<html><body><h1>no photo</h1></body></html>", encoding="utf-8")
    url = f"/api/v1/files/exports/{empty.name}"
    trace = [
        {
            "kind": "tool",
            "tool": "create_webpage",
            "status": "ok",
            "detail": f"产出 {url}",
        }
    ]
    verdict = evaluate_turn(
        required_tools=["create_webpage"],
        response=f"[打开]({url})",
        trace=trace,
        exports_dir=exports,
        must_embed_image=True,
    )
    assert not verdict.complete
    assert verdict.missing_embedded_image
    assert "hero.image" in verdict.critique()

    with_img = exports / "_test_with_photo.html"
    with_img.write_text(
        '<html><body><img src="data:image/jpeg;base64,/9j/" alt="p" /></body></html>',
        encoding="utf-8",
    )
    url2 = f"/api/v1/files/exports/{with_img.name}"
    ok = evaluate_turn(
        required_tools=["create_webpage"],
        response=f"[打开]({url2})",
        trace=[
            {
                "kind": "tool",
                "tool": "create_webpage",
                "status": "ok",
                "detail": f"产出 {url2}",
            }
        ],
        exports_dir=exports,
        must_embed_image=True,
    )
    assert ok.complete
    empty.unlink(missing_ok=True)
    with_img.unlink(missing_ok=True)


def test_overclaim_is_caught_by_inspect() -> None:
    exports = Path("data/exports")
    empty = exports / "_test_overclaim.html"
    empty.write_text("<html><body><h1>demo</h1></body></html>", encoding="utf-8")
    url = f"/api/v1/files/exports/{empty.name}"
    verdict = evaluate_turn(
        required_tools=["create_webpage"],
        response="我已经添加了您的照片并优化了整体布局",
        trace=[
            {
                "kind": "tool",
                "tool": "create_webpage",
                "status": "ok",
                "detail": f"产出 {url}",
            }
        ],
        exports_dir=exports,
        goal_text="改一下封面",
    )
    assert not verdict.complete
    assert verdict.delivery_gaps
    empty.unlink(missing_ok=True)


def test_inspect_reports_hero_photo() -> None:
    from app.agent.artifacts import inspect_path
    from app.agent.tools.html_builder import build_webpage

    path = Path("data/exports/_test_inspect_hero.html")
    path.parent.mkdir(parents=True, exist_ok=True)
    build_webpage(
        path=path,
        title="Cover",
        sections=[{"layout": "hero", "heading": "Cover", "image": "data:image/png;base64,aaa"}],
    )
    info = inspect_path(path)
    assert info is not None
    assert info["kind"] == "webpage"
    assert info["image_count"] >= 1
    assert info["hero_has_photo"] is True
    path.unlink(missing_ok=True)


def test_empty_pseudocode_heading_is_not_has_code() -> None:
    from app.agent.artifacts import inspect_path
    from app.agent.tools.html_builder import build_webpage

    path = Path("data/exports/_test_empty_pseudo.html")
    path.parent.mkdir(parents=True, exist_ok=True)
    build_webpage(
        path=path,
        title="DNPR",
        sections=[
            {"layout": "hero", "heading": "DNPR"},
            {"layout": "narrative", "heading": "核心伪代码"},
        ],
    )
    info = inspect_path(path)
    assert info is not None
    assert info["has_code"] is False
    assert "核心伪代码" in (info.get("empty_headings") or [])
    html = path.read_text(encoding="utf-8")
    assert "<pre" in html  # layout promoted to code, but still empty
    assert info["code_chars"] < 40
    path.unlink(missing_ok=True)


def test_code_layout_renders_pre_and_inspects() -> None:
    from app.agent.artifacts import inspect_path
    from app.agent.tools.html_builder import build_webpage

    path = Path("data/exports/_test_real_pseudo.html")
    path.parent.mkdir(parents=True, exist_ok=True)
    snippet = (
        "for t in 1..T:\n"
        "    glob = refine(glob, layer3)\n"
        "    loc  = aggregate(nbr=9, layer2)\n"
        "    score = glob + loc\n"
        "return score"
    )
    build_webpage(
        path=path,
        title="DNPR",
        sections=[
            {"layout": "hero", "heading": "DNPR"},
            {"layout": "code", "heading": "核心伪代码", "code": snippet},
        ],
    )
    info = inspect_path(path)
    html = path.read_text(encoding="utf-8")
    assert "<pre class=\"code\">" in html
    assert "aggregate(nbr=9" in html
    assert info is not None
    assert info["has_code"] is True
    assert info["code_chars"] >= 40
    assert "核心伪代码" not in (info.get("empty_headings") or [])
    path.unlink(missing_ok=True)


def test_overclaim_pseudocode_is_caught() -> None:
    exports = Path("data/exports")
    empty = exports / "_test_overclaim_code.html"
    empty.parent.mkdir(parents=True, exist_ok=True)
    empty.write_text(
        "<html><body><section><h2>核心伪代码</h2></section></body></html>",
        encoding="utf-8",
    )
    url = f"/api/v1/files/exports/{empty.name}"
    verdict = evaluate_turn(
        required_tools=["create_webpage"],
        response="已经加上核心伪代码，可以投屏演示了",
        trace=[
            {
                "kind": "tool",
                "tool": "create_webpage",
                "status": "ok",
                "detail": f"产出 {url}",
            }
        ],
        exports_dir=exports,
        goal_text="给 DNPR demo 加伪代码",
    )
    assert not verdict.complete
    assert any("has_code" in gap for gap in verdict.delivery_gaps)
    empty.unlink(missing_ok=True)


def test_crop_keeps_existing_portrait() -> None:
    import asyncio

    src = next(Path("data/uploads").glob("*_img41.png"), None)
    if src is None:
        print("skip crop: no img41")
        return
    from app.agent.tools.image_crop import crop_image

    result = asyncio.run(
        crop_image(src=str(src), preset="portrait", filename_hint="id_photo")
    )
    assert result.get("ok") is True, result
    assert result.get("height", 0) >= result.get("width", 0)
    out = Path("data/exports") / result["filename"]
    assert out.is_file()
    out.unlink(missing_ok=True)


def test_progress_emit_is_noop_without_sink() -> None:
    from app.agent.progress import emit

    emit({"type": "step_start"})


def test_progress_emit_reaches_bound_sink() -> None:
    from app.agent.progress import bind_progress, emit, reset_progress

    events: list[dict] = []
    token = bind_progress(events.append)
    try:
        emit({"type": "step_start", "kind": "plan"})
        emit({"type": "step_end", "elapsed_ms": 1200})
    finally:
        reset_progress(token)
    assert [e["type"] for e in events] == ["step_start", "step_end"]
    assert events[1]["elapsed_ms"] == 1200


def test_stamp_node_trace_adds_think_and_elapsed() -> None:
    from app.agent.progress import stamp_node_trace

    skill = {"kind": "skill_retrieve", "title": "检索 Skill", "status": "ok"}
    stamped = stamp_node_trace(
        "retrieve_skills",
        [skill],
        before=0,
        elapsed_ms=350,
    )
    assert stamped[0]["elapsed_ms"] == 350

    with_think = stamp_node_trace("llm_call", stamped, before=1, elapsed_ms=4200)
    assert with_think[-1]["kind"] == "think"
    assert with_think[-1]["elapsed_ms"] == 4200
    assert with_think[-1]["title"] == "模型推理"


def test_stamp_llm_think_keeps_model_text_and_tools() -> None:
    from app.agent.progress import stamp_node_trace

    out = stamp_node_trace(
        "llm_call",
        [],
        before=0,
        elapsed_ms=800,
        state={
            "response": "先查天气再回答",
            "tool_calls": [{"function": {"name": "get_weather"}}],
        },
    )
    assert out[-1]["kind"] == "think"
    assert "先查天气再回答" in out[-1]["detail"]
    assert "get_weather" in out[-1]["detail"]


def test_stamp_verify_synthesizes_step_when_node_skipped() -> None:
    from app.agent.progress import stamp_node_trace

    out = stamp_node_trace("verify", [{"kind": "think"}], before=1, elapsed_ms=12)
    assert out[-1]["kind"] == "verify"
    assert out[-1]["elapsed_ms"] == 12
    assert out[-1]["status"] == "ok"


def test_skill_gate_skips_chitchat_and_recap() -> None:
    from app.agent.skill_gate import should_retrieve_skills

    assert should_retrieve_skills("你好") is False
    assert should_retrieve_skills("我问过你什么") is False
    assert should_retrieve_skills("在试试") is False
    assert should_retrieve_skills("我说了在试试？") is False
    assert should_retrieve_skills("生成一张美女的图像") is True
    assert should_retrieve_skills("查一下北京天气") is True


def test_should_call_tools_does_not_drop_in_flight_call_at_cap() -> None:
    from app.agent.state import TOOL_LOOP_GRACE

    cap = settings.agent_max_tool_loops
    state = {
        "tool_policy": "full",
        "tool_calls": [
            {"function": {"name": "run_command", "arguments": "{}"}},
        ],
        "tool_loop_count": cap,
    }
    assert should_call_tools(state) == "tools"
    state["tool_loop_count"] = cap + TOOL_LOOP_GRACE
    assert should_call_tools(state) == "verify"


def test_checklist_only_rounds_have_their_own_budget() -> None:
    """todo_write spends no work loop, so it needs a separate bound."""
    from app.agent.state import TODO_ONLY_LOOP_BUDGET

    state = {
        "tool_policy": "full",
        "tool_calls": [{"function": {"name": "todo_write", "arguments": "{}"}}],
        "tool_loop_count": 0,
        "todo_loop_count": TODO_ONLY_LOOP_BUDGET - 1,
    }
    assert should_call_tools(state) == "tools"
    state["todo_loop_count"] = TODO_ONLY_LOOP_BUDGET
    assert should_call_tools(state) == "verify"
    # A round that also does real work still uses the work cap, not this one.
    state["tool_calls"] = [
        {"function": {"name": "todo_write", "arguments": "{}"}},
        {"function": {"name": "run_command", "arguments": "{}"}},
    ]
    assert should_call_tools(state) == "tools"


def test_retry_reuses_last_actionable_user_turn() -> None:
    from app.agent.goal import resolve_goal_text

    history = [
        {"role": "user", "content": "生成一张美女的图像"},
        {"role": "assistant", "content": "好的，这是图片"},
    ]
    assert resolve_goal_text("在试试", history=history) == "生成一张美女的图像"
    assert infer_required_tools(resolve_goal_text("在试试", history=history)) == [
        "generate_image"
    ]


def test_failed_turn_keeps_question_and_trace() -> None:
    from app.agent.nodes.persist import FAILED_KEEP_NOTE, failed_turn_content, finalize_failed_trace

    state = {
        "query": "做一套 AGI 一周简报",
        "response": "已写完 notes.md",
        "execution_trace": [
            {"kind": "tool", "title": "todo_write", "status": "ok"},
            {"kind": "think", "title": "模型推理", "status": "running"},
        ],
    }
    reason = "This turn used too many graph steps before finishing."
    text = failed_turn_content(state, reason)
    assert "已写完 notes.md" in text
    assert reason in text
    assert FAILED_KEEP_NOTE in text
    trace = finalize_failed_trace(state["execution_trace"], reason)
    assert trace[0]["status"] == "ok"
    assert trace[1]["status"] == "error"
    assert any(step.get("title") == "本轮中断" for step in trace)


def test_run_agent_persists_partial_turn_on_recursion() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from langgraph.errors import GraphRecursionError

    from app.agent.graph import remember_state, run_agent
    from app.core.exceptions import AppError

    captured: dict = {}

    class FakeApp:
        async def ainvoke(self, initial, config=None):
            remember_state(
                {
                    **initial,
                    "todos": [{"content": "搜索", "status": "completed"}],
                    "execution_trace": [
                        {"kind": "tool", "title": "todo_write", "status": "ok"},
                    ],
                }
            )
            raise GraphRecursionError("limit")

    async def fake_persist(state, *, session, reason):
        captured["query"] = state["query"]
        captured["reason"] = reason
        captured["todos"] = state.get("todos")
        captured["trace"] = state.get("execution_trace")
        return {**state, "assistant_message_id": "kept"}

    async def _run() -> None:
        from app.agent import graph as graph_mod

        original_build = graph_mod.build_graph
        original_persist = graph_mod.persist_failed_turn
        graph_mod.build_graph = lambda session: FakeApp()  # type: ignore[assignment]
        graph_mod.persist_failed_turn = fake_persist  # type: ignore[assignment]
        try:
            try:
                await run_agent(
                    session=AsyncMock(),
                    user_id="u",
                    conversation_id="c",
                    query="做一套 AGI 一周简报",
                )
            except AppError as exc:
                assert "graph steps" in exc.message
                assert exc.details.get("conversation_id") == "c"
            else:
                raise AssertionError("expected AppError")
        finally:
            graph_mod.build_graph = original_build
            graph_mod.persist_failed_turn = original_persist

    asyncio.run(_run())
    assert captured["query"] == "做一套 AGI 一周简报"
    assert captured["todos"]
    assert captured["trace"]


def test_graph_recursion_limit_covers_a_full_tool_loop() -> None:
    from app.agent.graph import graph_recursion_limit
    from app.core.config import settings

    limit = graph_recursion_limit()
    # Default LangGraph cap is 25; a 12-loop brief is ~5 startup + 2 hops
    # per batch + verify/persist and must not die as GraphRecursionError.
    hops_needed = 8 + 2 * (settings.agent_max_tool_loops + settings.agent_max_verify_retries)
    assert limit >= 60
    assert limit >= hops_needed


def test_history_compaction_keeps_user_intent() -> None:
    from app.memory.conversation_memory import compact_history_text

    huge = "data:image/png;base64," + ("A" * 8000)
    md = f"这是结果\n\n![]({huge})\n\n还可以再改"
    compact = compact_history_text("assistant", md)
    assert "data:image" not in compact
    assert "生成一张美女" not in compact
    assert "[图片]" in compact
    user = compact_history_text("user", "生成一张美女的图像")
    assert user == "生成一张美女的图像"


def test_db_lock_error_is_named_and_actionable() -> None:
    """A locked SQLite file must not surface as the opaque generic message."""
    from sqlalchemy.exc import OperationalError

    from app.agent.graph import _map_run_error

    exc = OperationalError("INSERT INTO messages", {}, Exception("database is locked"))
    mapped = _map_run_error(exc, "conv-1")
    assert "database was locked" in mapped.message
    assert mapped.details["exception"] == "OperationalError"

    other = RuntimeError("boom")
    generic = _map_run_error(other, "conv-1")
    assert "stopped before a reply" in generic.message
    # Whatever it was, the type is recorded so the stored turn is diagnosable.
    assert generic.details["exception"] == "RuntimeError"
    assert generic.details["exception_message"] == "boom"


def test_interrupted_stream_is_not_a_finished_turn() -> None:
    """A salvaged half-reply reads fine, so only finish_reason can catch it."""
    verdict = evaluate_turn(
        required_tools=[],
        response="AGI 指的是通用人工智能，它",
        trace=[],
        exports_dir=Path("/tmp/nous-missing-exports"),
        finish_reason="interrupted",
    )
    assert verdict.truncated
    assert not verdict.complete
    critique = verdict.critique()
    assert "cut off mid-stream" in critique
    assert "do not repeat what you already wrote" in critique

    # A normal finish with the same (short) answer stays complete.
    ok = evaluate_turn(
        required_tools=[],
        response="AGI 指的是通用人工智能，它",
        trace=[],
        exports_dir=Path("/tmp/nous-missing-exports"),
        finish_reason="stop",
    )
    assert not ok.truncated
    assert ok.complete


if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print(_name, "ok")
    print("all ok")
