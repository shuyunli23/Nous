"""Material review can use its own provider without changing chat/image routes."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.llm import provider_store
from app.llm.provider_store import ProviderStore
from app.llm.providers import ProviderInput
from app.schemas.llm_config import LLMRoutesUpdate


def _provider(label: str, model: str = "local-vision") -> ProviderInput:
    return ProviderInput(
        label=label, kind="openai_compatible", model=model,
        base_url="http://localhost:11434/v1",
    )


def _enable_resolver(monkeypatch, store: ProviderStore):
    monkeypatch.setattr(provider_store, "get_provider_store", lambda: store)
    monkeypatch.setattr(provider_store, "settings", SimpleNamespace(
        runtime_llm_config_enabled=True, llm_temperature=0.3,
        llm_timeout_seconds=120.0, llm_max_retries=2,
    ))


def test_materials_schema_distinguishes_omitted_and_explicit_clear():
    assert LLMRoutesUpdate().changes() == {}
    assert LLMRoutesUpdate(materials=None).changes() == {"materials": None}
    assert LLMRoutesUpdate(materials="  ").changes() == {"materials": None}
    assert LLMRoutesUpdate(materials="  review-model-id  ").changes() == {"materials": "review-model-id"}


def test_materials_assignment_survives_reload_and_preserves_other_routes(tmp_path: Path):
    path = tmp_path / "providers.json"
    store = ProviderStore(path)
    chat = store.create(_provider("Chat", "text-model"), activate=True)
    review = store.create(_provider("Review"))
    store.set_routes({"chat": chat.id, "skill": chat.id})
    store.set_routes(LLMRoutesUpdate(materials=review.id).changes())

    restored = ProviderStore(path)
    assert restored.route_for("materials") == review.id
    assert restored.route_for("chat") == chat.id
    assert restored.route_for("skill") == chat.id
    assert restored.active_id == chat.id


def test_clear_materials_leaves_chat_route_and_default_unchanged(tmp_path: Path):
    store = ProviderStore(tmp_path / "providers.json")
    chat = store.create(_provider("Chat"), activate=True)
    review = store.create(_provider("Review"))
    store.set_routes({"chat": chat.id, "materials": review.id})
    store.set_routes(LLMRoutesUpdate(materials="").changes())
    assert store.route_for("materials") is None
    assert store.route_for("chat") == chat.id
    assert store.active_id == chat.id


def test_materials_rejects_image_only_provider_without_replacing_route(tmp_path: Path):
    store = ProviderStore(tmp_path / "providers.json")
    review = store.create(_provider("Review"), activate=True)
    image = store.create(ProviderInput(
        label="Illustrations", kind="huggingface_image",
        model="black-forest-labs/FLUX.1-dev", api_key="hf_test", hf_provider="fal-ai",
    ))
    store.set_routes({"materials": review.id, "image": image.id})
    with pytest.raises(ValidationError, match="Image-only"):
        store.set_routes({"materials": image.id})
    assert store.route_for("materials") == review.id
    assert store.route_for("image") == image.id


def test_materials_rejects_unknown_provider(tmp_path: Path):
    store = ProviderStore(tmp_path / "providers.json")
    with pytest.raises(NotFoundError):
        store.set_routes(LLMRoutesUpdate(materials="deleted-provider").changes())


def test_materials_resolver_uses_review_route_then_default(tmp_path: Path, monkeypatch):
    store = ProviderStore(tmp_path / "providers.json")
    chat = store.create(_provider("Chat", "text-model"), activate=True)
    review = store.create(_provider("Review", "vision-model"))
    store.set_routes({"materials": review.id})
    _enable_resolver(monkeypatch, store)

    resolved = provider_store.resolve_llm(purpose="materials")
    assert resolved.provider_id == review.id
    assert resolved.model == "vision-model"
    assert provider_store.resolve_llm(purpose="chat").provider_id == chat.id

    store.set_routes({"materials": None})
    assert provider_store.resolve_llm(purpose="materials").provider_id == chat.id


def test_deleting_review_provider_clears_materials_route(tmp_path: Path):
    path = tmp_path / "providers.json"
    store = ProviderStore(path)
    chat = store.create(_provider("Chat"), activate=True)
    review = store.create(_provider("Review"))
    store.set_routes({"materials": review.id})
    store.delete(review.id)
    restored = ProviderStore(path)
    assert restored.route_for("materials") is None
    assert restored.active_id == chat.id
