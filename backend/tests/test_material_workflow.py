"""Delivery contracts across planning, source validation and final verification."""

from __future__ import annotations

import asyncio
import hashlib
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from app.agent.execution_trace import tool_step
from app.agent.goal import infer_required_tools, material_delivery_gaps
from app.agent.tools import material_workflow as workflow


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    export = tmp_path / "exports"
    export.mkdir()
    shell = tmp_path / "workspace"
    shell.mkdir()
    monkeypatch.setattr(workflow, "exports_dir", lambda: export)
    policy = SimpleNamespace(enabled=True, workspace_path=str(shell))
    monkeypatch.setattr("app.agent.tools.shell_config.resolve_shell", lambda: policy)
    return export, shell, policy


def source(title="Example", content='print("hello")\n'):
    return asyncio.run(workflow.create_code_files(
        title=title, files=[{"filename": "example.py", "content": content}],
    ))


def step(name, result):
    return tool_step(name=name, call_id="contract-test", raw_args={}, result=result)


def document_trace(export: Path):
    path = export / "handbook.pdf"
    document = fitz.open()
    document.new_page().insert_text((60, 60), "Training handbook and runnable examples")
    document.save(path)
    document.close()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    artifact = {"kind": "tool", "tool": "create_pdf", "status": "ok",
                "inspect": {"kind": "pdf", "file": path.name, "page_count": 1}}
    inspected = {"file": path.name, "sha256": digest, "current_sha256": digest,
                 "issues": [], "render": {"status": "rendered"},
                 "visual": {"status": "passed"}}
    review = step("review_materials", {
        "ok": True, "status": "passed", "review_complete": True,
        "visual_review_complete": True, "review_scope": "visual_and_structural",
        "issues": [], "files": [inspected],
    })
    return artifact, review


def test_requesting_sources_does_not_bypass_material_creation_contract():
    required = infer_required_tools("给初学者制作8页PPT和一份PDF讲义，并附完整源代码")
    assert {"plan_materials", "create_presentation", "create_pdf", "review_materials"} <= set(required)
    assert infer_required_tools("查看这个网页已有的源码") == []


def test_source_bundle_preserves_compilable_names_and_spacing_without_execution(workspace):
    _, _, policy = workspace
    policy.enabled = False
    contents = 'def main():\n    print("hello")\n\nmain()\n'
    delivered = source(content=contents)
    assert delivered["verification_status"] == "not_run"
    assert delivered["execution_enabled"] is False
    with zipfile.ZipFile(delivered["path"]) as archive:
        assert archive.namelist() == ["example.py"]
        assert archive.read("example.py").decode("utf-8") == contents


def test_code_verification_cannot_bypass_the_shell_enable_gate(workspace, monkeypatch):
    _, shell, policy = workspace
    policy.enabled = False

    async def forbidden(**kwargs):
        pytest.fail("Disabled execution must never call run_command")

    monkeypatch.setattr("app.agent.tools.shell.run_command", forbidden)
    result = asyncio.run(workflow.verify_code_examples(workspace=str(shell), commands=["echo hello"]))
    assert result["ok"] is False
    assert result["verification_status"] == "unavailable"


def test_verification_workspace_must_remain_inside_the_shell_root(workspace, tmp_path):
    outside = tmp_path / "materials_outside"
    outside.mkdir()
    with pytest.raises(ValueError, match="workspace"):
        asyncio.run(workflow.verify_code_examples(workspace=str(outside), commands=["echo hello"]))


def test_commands_that_change_sources_do_not_certify_the_original_bundle(workspace, monkeypatch):
    delivered = source()
    folder = Path(delivered["workspace"])

    async def changed(**kwargs):
        (folder / "example.py").write_text('print("different program")\n', encoding="utf-8")
        return {"ok": True, "exit_code": 0, "stdout": "different program"}

    monkeypatch.setattr("app.agent.tools.shell.run_command", changed)
    result = asyncio.run(workflow.verify_code_examples(workspace=str(folder), commands=["python example.py"]))
    assert result["verification_status"] == "failed"
    assert result["ok"] is False


def test_old_source_verification_cannot_certify_a_new_source_delivery(workspace, monkeypatch):
    export, _, _ = workspace
    old_source = source(content='print("old version")\n')

    async def passed(**kwargs):
        return {"ok": True, "exit_code": 0, "stdout": "old version"}

    monkeypatch.setattr("app.agent.tools.shell.run_command", passed)
    verified = asyncio.run(workflow.verify_code_examples(
        workspace=old_source["workspace"], commands=["python example.py"],
    ))
    new_source = source(content='print("new version with different behavior")\n')
    trace = [*document_trace(export), step("create_code_files", old_source),
             step("verify_code_examples", verified), step("create_code_files", new_source)]
    gaps = material_delivery_gaps(
        "制作PDF讲义，包含代码示例", "代码已运行通过。", trace, export,
    )
    assert any("source" in gap.lower() or "代码" in gap for gap in gaps), gaps


def test_unrelated_review_does_not_clear_a_final_files_content_error(workspace):
    export, _, _ = workspace
    artifact, reviewed = document_trace(export)
    reviewed["material_review"]["status"] = "needs_revision"
    reviewed["material_review"]["review_complete"] = False
    reviewed["material_review"]["issues"] = [{
        "severity": "error", "kind": "structure", "page": None,
        "message": "The mandatory exercise answers are missing.",
    }]
    unrelated = step("review_materials", {
        "ok": True, "status": "passed", "review_complete": True,
        "visual_review_complete": True, "review_scope": "visual_and_structural",
        "issues": [], "files": [{"file": "unrelated.pdf", "sha256": "other",
                                  "current_sha256": "other", "issues": []}],
    })
    gaps = material_delivery_gaps(
        "制作PDF讲义", "材料已完成。", [artifact, reviewed, unrelated], export,
    )
    assert any("exercise answers" in gap for gap in gaps), gaps


def managed_settings(export: Path):
    """Keep real tool dispatch confined to the test's authored directories."""
    uploads = export.parent / "uploads"
    uploads.mkdir(exist_ok=True)
    return SimpleNamespace(
        resolve_path=lambda raw: export if str(raw).endswith("/exports") else uploads,
        api_prefix="/api/v1",
    )


def plan(*, pptx=False, pdf=True, count=8):
    deliverables = []
    outline = []
    if pptx:
        deliverables.append({"kind": "pptx", "purpose": "Classroom explanation", "total_slides": count})
        outline.extend({"kind": "pptx", "heading": f"Lesson {number}",
                        "purpose": f"Explain example {number}"} for number in range(1, count + 1))
    if pdf:
        deliverables.append({"kind": "pdf", "purpose": "Independent study"})
        outline.extend([
            {"kind": "pdf", "heading": "Overview", "purpose": "Explain the problem"},
            {"kind": "pdf", "heading": "Exercises", "purpose": "Check understanding"},
        ])
    return asyncio.run(workflow.plan_materials(
        title="Concurrency introduction", audience="Java beginners", objectives=["Explain lost updates"],
        deliverables=deliverables, outline=outline,
        acceptance_criteria=["Include a worked trace and exercise answers"],
    ))


def test_downloaded_review_receipt_contains_the_checked_plan_snapshot(workspace, monkeypatch):
    from app.agent.tools import material_assets, material_review, material_schemas

    export, _, _ = workspace
    config = managed_settings(export)
    monkeypatch.setattr(material_assets, "settings", config)
    monkeypatch.setattr(material_review, "settings", config)
    saved = plan()
    path = export / "handbook.pdf"
    document = fitz.open()
    document.new_page().insert_text((55, 65), "Overview\nExercises\nA worked trace and exercise answers")
    document.save(path)
    document.close()
    result = asyncio.run(material_schemas._review(
        files=[str(path)], plan_id=saved["plan_id"], visual=False,
    ))
    receipt = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    expected_hash = hashlib.sha256(json.dumps(
        saved["plan"], ensure_ascii=False, sort_keys=True,
    ).encode("utf-8")).hexdigest()
    assert receipt["plan_id"] == saved["plan_id"]
    assert receipt["plan_sha256"] == result["plan_sha256"] == expected_hash
    assert receipt["planned_sections"] == ["Overview", "Exercises"]
    assert receipt["plan_acceptance_criteria"] == saved["plan"]["acceptance_criteria"]
    assert receipt["files"][0]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def previous_material_rows(saved):
    old = {**saved["plan"], "plan_id": "old-plan", "title": "Old lesson"}
    return [
        SimpleNamespace(execution_trace=[
            {"status": "ok", "material_plan": old},
            {"status": "ok", "inspect": {"kind": "pptx", "file": "old.pptx"}},
        ]),
        SimpleNamespace(execution_trace=[
            {"status": "ok", "material_plan": saved["plan"]},
            {"status": "ok", "inspect": {"kind": "pptx", "file": "current.pptx"}},
            {"status": "ok", "inspect": {"kind": "pdf", "file": "current.pdf"}},
            {"status": "error", "material_plan": {"plan_id": "failed-plan"}},
            {"status": "error", "inspect": {"kind": "pdf", "file": "failed.pdf"}},
        ]),
    ]


def test_next_turn_restores_plan_and_files_but_not_old_review_approval(workspace, monkeypatch):
    from app.agent.nodes import load_memory

    saved = plan(pptx=True)
    rows = previous_material_rows(saved)
    rows[-1].execution_trace.append({"status": "ok", "material_review": {
        "review_complete": True, "visual_review_complete": True,
    }})

    class Repository:
        async def get(self, conversation_id):
            return SimpleNamespace(todos=[], summary=None)

        async def list_messages(self, conversation_id, *, limit):
            assert limit > 0
            return rows

    async def history(*args, **kwargs):
        return [{"role": "user", "content": "制作8页PPT与PDF讲义"}]

    monkeypatch.setattr(load_memory, "ConversationRepository", lambda session: Repository())
    monkeypatch.setattr(load_memory, "load_history", history)
    state = asyncio.run(load_memory.load_memory_node({
        "conversation_id": "next-turn", "query": "把PPT改成6页，讲义维持原内容",
    }, session=object()))
    assert state["material_plan_id"] == saved["plan_id"]
    assert state["material_plan"]["audience"] == "Java beginners"
    assert state["material_files"] == {
        "pptx": "/api/v1/files/exports/current.pptx",
        "pdf": "/api/v1/files/exports/current.pdf",
    }
    assert "material_review" not in state
    assert "visual_review_complete" not in state


def test_material_edit_requires_updated_plan_and_restores_prompt_context(workspace):
    from app.agent.nodes.compose_prompt import compose_prompt_node
    from app.agent.nodes.plan import plan_node

    saved = plan(pptx=True)
    state = {
        "conversation_id": "edit-lesson", "query": "把PPT改成6页，讲义维持原内容",
        "history": [], "material_plan": saved["plan"], "material_plan_id": saved["plan_id"],
        "material_files": {"pptx": "/api/v1/files/exports/current.pptx"},
    }
    planned = asyncio.run(plan_node(state))
    assert {"plan_materials", "create_presentation", "create_pdf", "review_materials"} <= set(planned["required_tools"])
    composed = asyncio.run(compose_prompt_node(planned))
    system = composed["messages"][0]["content"]
    assert saved["plan_id"] in system
    assert "Java beginners" in system
    assert "current.pptx" in system
    assert "重新调用plan_materials" in system


def test_old_conversation_without_material_metadata_keeps_normal_chat_behavior():
    from app.agent.nodes.load_memory import material_context
    from app.agent.nodes.plan import plan_node

    context = material_context([SimpleNamespace(execution_trace=None)])
    assert context == {"material_plan": None, "material_plan_id": None, "material_files": {}, "material_drafts": {}}
    result = asyncio.run(plan_node({"query": "你好", "history": [], **context}))
    assert result["required_tools"] == []


def test_executor_enforces_user_slide_count_and_keeps_review_evidence_after_spill(workspace, monkeypatch):
    from app.agent.nodes.tool_executor import tool_executor_node
    from app.agent.tools import builtins, material_assets, material_review
    from app.core.config import settings

    export, _, _ = workspace
    config = managed_settings(export)
    monkeypatch.setattr(builtins, "settings", config)
    monkeypatch.setattr(material_assets, "settings", config)
    monkeypatch.setattr(material_review, "settings", config)
    monkeypatch.setattr(material_review, "_find_libreoffice", lambda: None)
    monkeypatch.setattr(settings, "spill_max_inline_bytes", 500)
    monkeypatch.setattr(settings, "spill_dir", str(export.parent / "spills"))
    saved = plan(pptx=True, pdf=False)
    slides = [{"layout": "title" if number == 1 else "bullets", "heading": f"Lesson {number}",
               "bullets": [f"Explain example {number}"]} for number in range(1, 9)]
    initial = {
        "user_id": "test-user", "conversation_id": "test-material-executor", "messages": [],
        "goal_text": "制作8页PPT培训材料", "material_plan_id": saved["plan_id"],
        "tool_calls": [{"id": "author-deck", "function": {"name": "create_presentation", "arguments": json.dumps({
            "title": "Concurrency introduction", "expected_slide_count": 1, "slides": slides,
        })}}],
    }
    authored = asyncio.run(tool_executor_node(initial, session=object()))
    deck_step = authored["execution_trace"][-1]
    assert deck_step["status"] == "ok", authored["messages"][-1]
    assert deck_step["inspect"]["slide_count"] == 8
    assert deck_step["args"]["expected_slide_count"] == "8"
    author_response = json.loads(authored["messages"][-1]["content"])
    assert author_response["plan_id"] == saved["plan_id"]
    authored["tool_calls"] = [{"id": "review-deck", "function": {"name": "review_materials", "arguments": json.dumps({
        "files": [author_response["download_url"]], "expected_slide_count": 2, "visual": False,
    })}}]
    checked = asyncio.run(tool_executor_node(authored, session=object()))
    trace = checked["execution_trace"][-1]
    tool_response = json.loads(checked["messages"][-1]["content"])
    assert trace["status"] != "error"
    assert trace["args"]["expected_slide_count"] == "8"
    assert tool_response["spilled"] is True
    evidence = trace["material_review"]
    assert evidence["review_scope"] == "structural_only"
    assert evidence["visual_review_complete"] is False
    file = evidence["files"][0]
    assert file["sha256"] == file["current_sha256"] == deck_step["inspect"]["sha256"]
    assert file["render"]["status"] == "unavailable"
    assert not file["issues"]
    spilled = json.loads(Path(tool_response["spill_path"]).read_text(encoding="utf-8"))
    assert spilled["files"][0]["current_sha256"] == file["sha256"]
    assert spilled["plan_id"] == saved["plan_id"]
    assert "planned_sections" in spilled
