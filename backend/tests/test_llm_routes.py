"""Purpose → provider routing in the runtime store."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.llm.provider_store import ProviderStore
from app.llm.providers import ProviderInput


def _store(tmp_path: Path) -> ProviderStore:
    return ProviderStore(tmp_path / "providers.json")


def _openai(label: str = "DeepSeek") -> ProviderInput:
    return ProviderInput(
        label=label,
        kind="openai_compatible",
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        api_key="sk-test",
    )


def test_set_and_clear_route(tmp_path: Path) -> None:
    store = _store(tmp_path)
    rec = store.create(_openai(), activate=True)
    store.set_routes({"skill": rec.id, "notes": rec.id})
    assert store.route_for("skill") == rec.id
    assert store.route_for("chat") is None

    store.set_routes({"skill": None})
    assert store.route_for("skill") is None
    assert store.route_for("notes") == rec.id


def test_delete_provider_clears_routes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    rec = store.create(_openai(), activate=True)
    store.set_routes({"memory": rec.id})
    store.delete(rec.id)
    assert store.route_for("memory") is None


def test_unknown_purpose_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ValidationError):
        store.set_routes({"probe": "x"})


def test_missing_provider_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(NotFoundError):
        store.set_routes({"chat": "does-not-exist"})


def test_routes_survive_reload(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    first = ProviderStore(path)
    rec = first.create(_openai(), activate=True)
    first.set_routes({"knowledge": rec.id})

    second = ProviderStore(path)
    assert second.route_for("knowledge") == rec.id


def _flux(label: str = "FLUX.1-dev") -> ProviderInput:
    return ProviderInput(
        label=label,
        kind="huggingface_image",
        model="black-forest-labs/FLUX.1-dev",
        hf_provider="fal-ai",
        api_key="hf_test",
    )


def test_image_provider_does_not_become_chat_default(tmp_path: Path) -> None:
    store = _store(tmp_path)
    flux = store.create(_flux(), activate=True)
    assert store.active_id is None
    chat = store.create(_openai(), activate=True)
    assert store.active_id == chat.id
    with pytest.raises(ValidationError):
        store.activate(flux.id)
    with pytest.raises(ValidationError):
        store.set_routes({"chat": flux.id})
    store.set_routes({"image": flux.id})
    assert store.route_for("image") == flux.id


def test_image_route_survives_reload(tmp_path: Path) -> None:
    path = tmp_path / "providers.json"
    first = ProviderStore(path)
    flux = first.create(_flux())
    first.set_routes({"image": flux.id})
    second = ProviderStore(path)
    assert second.route_for("image") == flux.id
    assert second.active_id is None
