"""Plugin import: nous-plugin/1, dsh package.json, GitHub URL parsing."""

from __future__ import annotations

import json
from pathlib import Path

from app.plugin.dsh import synthesize_dsh_pack
from app.plugin.github import parse_plugin_source
from app.plugin.ids import npm_name_to_pack_id
from app.plugin.loader import parse_plugin_directory
from app.skill.pack_format import FORMAT_DSH, FORMAT_PLUGIN


def test_npm_name_to_pack_id() -> None:
    assert npm_name_to_pack_id("@deepseek-ai/weather") == "deepseek-ai.weather"
    assert npm_name_to_pack_id("dsh-example-plugin") == "dsh-example-plugin"


def test_parse_github_urls() -> None:
    src = parse_plugin_source("https://github.com/acme/hello-plugin")
    assert src.kind == "github"
    assert src.owner == "acme"
    assert src.repo == "hello-plugin"
    short = parse_plugin_source("acme/hello-plugin")
    assert short.owner == "acme" and short.repo == "hello-plugin"
    branch = parse_plugin_source("https://github.com/acme/hello-plugin/tree/dev")
    assert branch.ref == "dev"


def test_parse_hello_plugin_example() -> None:
    root = Path(__file__).resolve().parents[2] / "docs" / "examples" / "hello-plugin"
    parsed = parse_plugin_directory(root)
    assert parsed.manifest.get("format") == FORMAT_PLUGIN
    assert parsed.pack_id == "nous.hello-plugin"
    assert parsed.skills
    assert parsed.skills[0].name == "Hello Plugin"
    assert not parsed.errors


def test_synthesize_dsh_package() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "package.json").write_text(
            json.dumps(
                {
                    "name": "@acme/dsh-notes",
                    "version": "2.1.0",
                    "description": "Take notes in the harness.",
                    "license": "MIT",
                    "keywords": ["dsh-plugin", "notes"],
                    "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
                }
            ),
            encoding="utf-8",
        )
        (root / "README.md").write_text(
            "# Notes\n\nRegisters a Cordis notes service.",
            encoding="utf-8",
        )
        parsed = synthesize_dsh_pack(root)
        assert parsed.manifest.get("format") == FORMAT_DSH
        assert parsed.pack_id == "acme.dsh-notes"
        assert parsed.version == "2.1.0"
        assert parsed.skills[0].instruction.startswith("# Notes")
        assert any("Cordis runtime is not executed" in w for w in parsed.warnings)


if __name__ == "__main__":
    test_npm_name_to_pack_id()
    test_parse_github_urls()
    test_parse_hello_plugin_example()
    test_synthesize_dsh_package()
    print("ok")
