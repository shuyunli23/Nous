"""Pack author: name coercion, materialised layout, and the parser contract.

The DB-writing install path (``PackService.import_bytes``) reuses the plugin
import machinery already covered by ``test_plugin_import``; here we lock down the
new code: the tree the author materialises must round-trip through
``parse_plugin_directory`` and its script must smoke-run in the sandbox exactly
as it will once installed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from app.plugin.loader import parse_plugin_directory
from app.skill.pack_author import (
    PackDraft,
    _coerce_tool_name,
    _materialize,
    _normalize_parameters,
    _slug,
)
from app.skill.pack_runner import smoke_run_script


def test_slug_is_pack_id_safe() -> None:
    assert _slug("CSV 汇总 Tool!!") == "csv-tool"
    assert _slug("") == "tool"
    assert _slug("---") == "tool"


def test_coerce_tool_name_falls_back() -> None:
    assert _coerce_tool_name("csv_summary") == "csv_summary"
    assert _coerce_tool_name("CSV Summary") == "csv_summary"
    assert _coerce_tool_name("123") == "t_123"
    assert _coerce_tool_name("") == "run"
    assert _coerce_tool_name("!!!") == "run"


def test_normalize_parameters_defaults_to_object() -> None:
    assert _normalize_parameters({}) == {"type": "object", "properties": {}}
    assert _normalize_parameters({"properties": {"x": {"type": "string"}}}) == {
        "type": "object",
        "properties": {"x": {"type": "string"}},
    }


def _draft() -> PackDraft:
    return PackDraft(
        reusable=True,
        confidence=0.9,
        name="CSV 行数",
        description="数一个 CSV 有几行",
        instruction="用它来统计 CSV 行数。",
        trigger_keywords=["csv", "行数"],
        trigger_intent="统计 CSV 行数",
        tool_name="csv_rows",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        python_source=(
            "import json, sys\n"
            "data = json.load(sys.stdin)\n"
            "rows = len([l for l in data['text'].splitlines() if l.strip()])\n"
            "print(json.dumps({'ok': True, 'rows': rows}))\n"
        ),
        needs_network=False,
        smoke_input={"text": "a\nb\nc"},
    )


def test_materialized_tree_parses_and_smoke_runs() -> None:
    draft = _draft()
    tool_name = _coerce_tool_name(draft.tool_name)
    pack_id = "auto-csv-rows-abc123"
    with TemporaryDirectory() as raw:
        root = Path(raw)
        skill_dir = _materialize(draft, pack_id=pack_id, tool_name=tool_name, root=root)

        # The parser accepts the layout with no errors and finds the tool.
        parsed = parse_plugin_directory(root)
        assert not parsed.errors, parsed.errors
        assert parsed.pack_id == pack_id
        assert parsed.permissions_requested and "script.python" in parsed.permissions_requested
        assert parsed.skills and parsed.skills[0].tools
        tool = parsed.skills[0].tools[0]
        assert tool.name == tool_name
        assert tool.exposed_name.startswith("pack__")
        assert tool.runner["entry"] == "scripts/main.py"

        # And the script honours the contract in the same sandbox.
        result = asyncio.run(
            smoke_run_script(
                script_path=skill_dir / "scripts" / "main.py",
                skill_dir=skill_dir,
                stdin_json=dict(draft.smoke_input),
            )
        )
    assert result.ok is True
    assert result.returned == {"ok": True, "rows": 3}


def test_materialized_network_tool_requests_permission() -> None:
    draft = _draft()
    draft.needs_network = True
    with TemporaryDirectory() as raw:
        root = Path(raw)
        _materialize(draft, pack_id="auto-net-xyz", tool_name="netty", root=root)
        parsed = parse_plugin_directory(root)
    assert not parsed.errors, parsed.errors
    assert "network" in parsed.permissions_requested
    assert parsed.skills[0].tools[0].runner["network"] is True


if __name__ == "__main__":
    test_slug_is_pack_id_safe()
    test_coerce_tool_name_falls_back()
    test_normalize_parameters_defaults_to_object()
    test_materialized_tree_parses_and_smoke_runs()
    test_materialized_network_tool_requests_permission()
    print("ok")
