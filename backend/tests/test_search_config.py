"""Runtime web-search overlay and DeepSeek result mapping."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from app.agent.search_config import (
    SearchConfigStore,
    planned_backends,
    resolve_search,
)
from app.agent.tools.deepseek_search import map_anthropic_response
from app.core.exceptions import ValidationError


def test_store_override_and_clear(tmp_path: Path) -> None:
    store = SearchConfigStore(tmp_path / "web_search.json")
    store.update(
        {
            "provider": "brave",
            "brave_search_api_key": "bsa_live_key",
        }
    )
    assert store.snapshot()["provider"] == "brave"
    assert store.snapshot()["brave_search_api_key"] == "bsa_live_key"

    store.update({"brave_search_api_key": ""})
    assert "brave_search_api_key" not in store.snapshot()
    assert store.snapshot()["provider"] == "brave"

    reloaded = SearchConfigStore(tmp_path / "web_search.json")
    assert reloaded.snapshot()["provider"] == "brave"
    assert "brave_search_api_key" not in reloaded.snapshot()


def test_unknown_provider_rejected(tmp_path: Path) -> None:
    store = SearchConfigStore(tmp_path / "web_search.json")
    try:
        store.update({"provider": "bing"})
    except ValidationError:
        return
    raise AssertionError("expected ValidationError")


def _env(**overrides: object) -> SimpleNamespace:
    data = dict(
        web_search_provider="auto",
        brave_search_api_key="",
        tavily_api_key="",
        serper_api_key="",
        deepseek_search_api_key="",
        deepseek_search_base_url="https://api.deepseek.com/anthropic/v1",
        deepseek_search_model="deepseek-v4-flash",
        deepseek_search_max_tokens=4096,
        deepseek_search_max_uses=2,
        web_search_timeout_seconds=15,
        deepseek_search_timeout_seconds=90,
        web_search_ddgs_backends="bing,duckduckgo,brave",
        llm_base_url="https://api.openai.com/v1",
        llm_api_key="",
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_resolve_runtime_overrides_env() -> None:
    with patch(
        "app.agent.search_config.settings",
        _env(brave_search_api_key="env-brave"),
    ):
        cfg = resolve_search(
            {
                "provider": "tavily",
                "tavily_api_key": "tvly-runtime",
            }
        )
    assert cfg.provider == "tavily"
    assert cfg.provider_source == "runtime"
    assert cfg.tavily_api_key == "tvly-runtime"
    assert cfg.brave_search_api_key == "env-brave"
    assert cfg.key_sources["brave_search_api_key"] == "env"
    assert cfg.key_sources["tavily_api_key"] == "runtime"


def test_auto_never_includes_deepseek() -> None:
    cfg = resolve_search(
        {
            "provider": "auto",
            "brave_search_api_key": "bsa",
            "deepseek_api_key": "sk-deepseek",
        }
    )
    names = planned_backends(cfg)
    assert names[0] == "brave"
    assert "deepseek" not in names
    assert names[-2:] == ["ddg_html", "ddgs"]


def test_explicit_deepseek_is_only_backend() -> None:
    cfg = resolve_search({"provider": "deepseek", "deepseek_api_key": "sk-x"})
    assert planned_backends(cfg) == ["deepseek"]


def test_deepseek_key_reuses_chat_provider() -> None:
    def _fake_resolve_llm(*, purpose: str | None = None):
        return SimpleNamespace(
            api_key="sk-from-chat",
            base_url="https://api.deepseek.com/v1",
        )

    with (
        patch("app.agent.search_config.settings", _env()),
        patch("app.llm.provider_store.resolve_llm", _fake_resolve_llm),
    ):
        cfg = resolve_search({"provider": "deepseek"})
    assert cfg.deepseek_api_key == "sk-from-chat"
    assert cfg.key_sources["deepseek_api_key"] == "llm"


def test_map_anthropic_response_joins_citations() -> None:
    payload = {
        "content": [
            {
                "type": "web_search_tool_result",
                "content": [
                    {
                        "type": "web_search_result",
                        "url": "https://example.com/a",
                        "title": "Example A",
                    },
                    {
                        "type": "web_search_result",
                        "url": "https://example.com/a",
                        "title": "Duplicate",
                    },
                    {
                        "type": "web_search_result",
                        "url": "https://example.com/b",
                        "title": "Example B",
                    },
                ],
            },
            {
                "type": "text",
                "text": "summary",
                "citations": [
                    {
                        "url": "https://example.com/a",
                        "cited_text": "Alpha snippet",
                    }
                ],
            },
        ]
    }
    rows = map_anthropic_response(payload)
    assert [row["url"] for row in rows] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert rows[0]["snippet"] == "Alpha snippet"
    assert rows[1]["title"] == "Example B"
    assert map_anthropic_response({"content": [{"type": "text", "text": "no search"}]}) == []


if __name__ == "__main__":
    with TemporaryDirectory() as raw:
        root = Path(raw)
        test_store_override_and_clear(root)
        test_unknown_provider_rejected(root / "other")
    test_resolve_runtime_overrides_env()
    test_auto_never_includes_deepseek()
    test_explicit_deepseek_is_only_backend()
    test_deepseek_key_reuses_chat_provider()
    test_map_anthropic_response_joins_citations()
    print("ok")
