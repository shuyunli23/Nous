"""Smoke test: runtime LLM provider configuration.

Runs against an isolated store file in a temp directory so it never touches the
real ``data/llm_providers.json``. No network and no AWS credentials are needed:
the outbound completion call is mocked, and the Bedrock checks exercise the pure
payload-translation helpers.

Verifies:
 1. Credential masking and provider validation rules
 2. Bedrock <-> OpenAI payload translation (system split, turn merging, tools)
 3. Config endpoint reports the .env fallback when nothing is active
 4. Create / activate / partial update / delete lifecycle over HTTP
 5. Secrets are never returned in cleartext by any endpoint
 6. A saved provider overrides .env for real LLM calls
 7. Deleting or deactivating the active provider falls back to .env
 8. The store survives a reload from disk
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile

# Must be set before app.core.config is imported.
_STORE_DIR = tempfile.mkdtemp(prefix="nous-llmcfg-")
os.environ["LLM_PROVIDER_STORE"] = os.path.join(_STORE_DIR, "providers.json")
os.environ["RUNTIME_LLM_CONFIG_ENABLED"] = "true"
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["VECTOR_BACKEND"] = "memory"

from unittest.mock import AsyncMock, patch  # noqa: E402

import httpx  # noqa: E402

from app.llm.bedrock import (  # noqa: E402
    _parse_converse_response,
    to_converse_messages,
    to_tool_config,
)
from app.llm.client import CompletionResult, Usage, _strip_json_fence  # noqa: E402
from app.llm.provider_store import get_provider_store, resolve_llm  # noqa: E402
from app.llm.providers import ProviderInput, mask_secret  # noqa: E402
from app.main import app  # noqa: E402

# Obvious placeholders: these must never reach a network.
FAKE_OPENAI_KEY = "unit-test-placeholder-key-0000000042"
FAKE_AWS_ID = "AKIAEXAMPLEEXAMPLE00"
FAKE_AWS_SECRET = "wJalrXUtnFEMIEXAMPLEKEYEXAMPLEKEY000000"

PROBE_REPLY = CompletionResult(
    content="pong",
    usage=Usage(prompt_tokens=3, completion_tokens=1, total_tokens=4),
)


def unit_checks() -> None:
    """Validation, masking and payload translation, no HTTP involved."""
    assert mask_secret(FAKE_OPENAI_KEY) == "****0042", mask_secret(FAKE_OPENAI_KEY)
    assert mask_secret("tiny") == "****", "short keys must not leak any characters"
    assert mask_secret("") is None and mask_secret(None) is None
    print("[OK] Secret masking keeps only the last 4 characters")

    # Trailing slashes would produce //chat/completions.
    p = ProviderInput(
        label="x",
        model="qwen-plus",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/",
    )
    assert p.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1", p.base_url
    # Blank form fields must become None, not "".
    p2 = ProviderInput(label="x", model="m", base_url="http://h/v1", api_key="   ")
    assert p2.api_key is None, p2.api_key
    print("[OK] base_url normalised, blank credentials coerced to None")

    for kwargs, expect in [
        ({"label": "a", "model": "m"}, "base_url is required"),
        ({"label": "a", "model": "m", "base_url": "ftp://x"}, "http"),
        ({"label": "a", "model": "m", "kind": "bedrock"}, "aws_region is required"),
        (
            {
                "label": "a",
                "model": "m",
                "kind": "bedrock",
                "aws_region": "us-west-2",
                "aws_access_key_id": FAKE_AWS_ID,
            },
            "must be set together",
        ),
    ]:
        try:
            ProviderInput(**kwargs)
        except ValueError as exc:
            assert expect in str(exc), f"expected {expect!r} in {exc}"
        else:
            raise AssertionError(f"{kwargs} should have failed validation")
    print("[OK] Provider validation rejects incomplete openai/bedrock configs")

    hf = ProviderInput(
        label="flux",
        kind="huggingface_image",
        model="black-forest-labs/FLUX.1-dev",
        api_key="hf_xxxx",
    )
    assert hf.hf_provider == "fal-ai" and hf.base_url is None
    print("[OK] huggingface_image does not require a chat base_url")

    # Bedrock needs system prompts hoisted out and alternating user/assistant.
    system, messages = to_converse_messages(
        [
            {"role": "system", "content": "be brief"},
            {"role": "system", "content": "in english"},
            {"role": "user", "content": "hello"},
            {"role": "user", "content": "again"},
            {"role": "assistant", "content": "hi"},
        ]
    )
    assert system == [{"text": "be brief"}, {"text": "in english"}], system
    assert [m["role"] for m in messages] == ["user", "assistant"], messages
    assert messages[0]["content"] == [{"text": "hello"}, {"text": "again"}], messages[0]
    print("[OK] Bedrock conversion hoists system blocks and merges same-role turns")

    # Converse rejects a conversation that opens on an assistant turn.
    _, only_assistant = to_converse_messages([{"role": "assistant", "content": "hi"}])
    assert only_assistant[0]["role"] == "user", only_assistant
    _, empty = to_converse_messages([{"role": "system", "content": "x"}])
    assert empty and empty[0]["role"] == "user", empty
    print("[OK] Bedrock conversion always starts on a user turn")

    tool_cfg = to_tool_config(
        [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "search docs",
                    "parameters": {"type": "object", "properties": {"q": {}}},
                },
            },
            {"function": {}},  # nameless tools are dropped
        ]
    )
    assert len(tool_cfg["tools"]) == 1, tool_cfg
    assert tool_cfg["tools"][0]["toolSpec"]["name"] == "search"
    assert "json" in tool_cfg["tools"][0]["toolSpec"]["inputSchema"]
    print("[OK] Tool schema translated to Converse toolConfig")

    parsed = _parse_converse_response(
        {
            "output": {
                "message": {
                    "content": [
                        {"text": "done"},
                        {
                            "toolUse": {
                                "toolUseId": "t1",
                                "name": "search",
                                "input": {"q": "ssh"},
                            }
                        },
                    ]
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 7, "outputTokens": 5, "totalTokens": 12},
        }
    )
    assert parsed.content == "done", parsed.content
    assert parsed.finish_reason == "tool_calls", parsed.finish_reason
    assert parsed.tool_calls[0]["function"]["name"] == "search"
    assert parsed.usage.total_tokens == 12
    print("[OK] Converse response mapped onto the OpenAI-shaped result")

    # Providers without JSON mode tend to wrap output in a markdown fence.
    assert _strip_json_fence('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert _strip_json_fence('{"a": 1}') == '{"a": 1}'
    print("[OK] JSON fences stripped for structured output")


async def api_checks() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        async with app.router.lifespan_context(app):
            # ── starts on the .env fallback ────────────────────────────────
            r = await client.get("/api/v1/llm/config")
            assert r.status_code == 200, r.text
            cfg = r.json()
            assert cfg["enabled"] is True
            assert cfg["active"]["source"] == "env", cfg["active"]
            assert cfg["providers"] == [], cfg["providers"]
            assert len(cfg["presets"]) >= 5, cfg["presets"]
            preset_ids = {p["id"] for p in cfg["presets"]}
            assert {"deepseek", "aliyun", "bedrock"} <= preset_ids, preset_ids
            assert cfg["env_defaults"]["model"], cfg["env_defaults"]
            print(
                f"[OK] Config starts on .env  model={cfg['active']['model']} "
                f"presets={len(cfg['presets'])}"
            )

            # ── create an OpenAI-compatible provider ──────────────────────
            r = await client.post(
                "/api/v1/llm/providers",
                json={
                    "label": "Ali Qwen",
                    "kind": "openai_compatible",
                    "model": "qwen-plus",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "api_key": FAKE_OPENAI_KEY,
                    "temperature": 0.7,
                    "activate": True,
                },
            )
            assert r.status_code == 201, r.text
            cfg = r.json()
            ali = cfg["providers"][0]
            ali_id = ali["id"]
            assert cfg["active"]["source"] == "runtime", cfg["active"]
            assert cfg["active"]["model"] == "qwen-plus", cfg["active"]
            assert cfg["active"]["configured"] is True
            assert cfg["active"]["temperature"] == 0.7, cfg["active"]
            print(
                f"[OK] Provider created and activated  {ali['label']} "
                f"({cfg['active']['model']})"
            )

            # ── the raw key must never come back ──────────────────────────
            assert ali["api_key"] == "****0042", ali["api_key"]
            assert FAKE_OPENAI_KEY not in r.text, "cleartext key leaked in response"
            assert ali["is_active"] is True and ali["has_credentials"] is True
            print("[OK] Stored credential returned masked only")

            # ── it really overrides .env for LLM calls ────────────────────
            cfg_used = resolve_llm()
            assert cfg_used.source == "runtime", cfg_used.source
            assert cfg_used.api_key == FAKE_OPENAI_KEY, "call path must see real key"
            assert cfg_used.base_url.endswith("/compatible-mode/v1"), cfg_used.base_url
            print(f"[OK] Call path resolves to the runtime provider  {cfg_used.label}")

            # ── test endpoint reports success and latency ─────────────────
            with patch(
                "app.llm.client.chat_complete", new=AsyncMock(return_value=PROBE_REPLY)
            ):
                r = await client.post("/api/v1/llm/test", json={"provider_id": ali_id})
            assert r.status_code == 200, r.text
            probe = r.json()
            assert probe["ok"] is True, probe
            assert probe["content"] == "pong", probe
            assert probe["total_tokens"] == 4, probe
            assert probe["latency_ms"] is not None
            print(f"[OK] Provider test probe ok  {probe['latency_ms']}ms")

            # ── an upstream failure is reported, not raised ───────────────
            from app.core.exceptions import LLMError

            with patch(
                "app.llm.client.chat_complete",
                new=AsyncMock(side_effect=LLMError("bad key", details={"hint": "x"})),
            ):
                r = await client.post("/api/v1/llm/test", json={"provider_id": ali_id})
            assert r.status_code == 200, r.text
            probe = r.json()
            assert probe["ok"] is False and probe["error_code"] == "llm_error", probe
            assert probe["error_message"] == "bad key", probe
            print("[OK] Failed probe returns diagnostics instead of a 5xx")

            # ── testing an unsaved draft ──────────────────────────────────
            with patch(
                "app.llm.client.chat_complete", new=AsyncMock(return_value=PROBE_REPLY)
            ):
                r = await client.post(
                    "/api/v1/llm/test",
                    json={
                        "draft": {
                            "label": "draft",
                            "model": "gpt-4o-mini",
                            "base_url": "https://api.openai.com/v1",
                            "api_key": FAKE_OPENAI_KEY,
                        }
                    },
                )
            assert r.status_code == 200 and r.json()["ok"] is True, r.text
            assert len(get_provider_store().list()) == 1, "draft must not be saved"
            print("[OK] Draft can be tested without being saved")

            # ── partial update keeps the stored secret ────────────────────
            r = await client.put(
                f"/api/v1/llm/providers/{ali_id}", json={"model": "qwen-max"}
            )
            assert r.status_code == 200, r.text
            assert r.json()["active"]["model"] == "qwen-max", r.json()["active"]
            assert get_provider_store().get(ali_id).api_key == FAKE_OPENAI_KEY, (
                "omitting api_key must not wipe it"
            )
            print("[OK] Partial update changed model and preserved the key")

            # ── explicit empty string clears a field ──────────────────────
            r = await client.put(
                f"/api/v1/llm/providers/{ali_id}", json={"api_key": ""}
            )
            assert r.status_code == 200, r.text
            assert get_provider_store().get(ali_id).api_key is None
            assert r.json()["active"]["configured"] is False
            # Put it back for the remaining checks.
            await client.put(
                f"/api/v1/llm/providers/{ali_id}", json={"api_key": FAKE_OPENAI_KEY}
            )
            print("[OK] Empty string explicitly clears a credential")

            # ── duplicate labels rejected ─────────────────────────────────
            r = await client.post(
                "/api/v1/llm/providers",
                json={
                    "label": "Ali Qwen",
                    "model": "qwen-plus",
                    "base_url": "https://example.com/v1",
                },
            )
            assert r.status_code == 409, r.text
            print("[OK] Duplicate provider label rejected with 409")

            # ── invalid payloads rejected ─────────────────────────────────
            for bad in [
                {"label": "no-url", "model": "m"},
                {"label": "bad-kind", "model": "m", "kind": "nope"},
                {"label": "bedrock-no-region", "model": "m", "kind": "bedrock"},
            ]:
                r = await client.post("/api/v1/llm/providers", json=bad)
                assert r.status_code == 422, f"{bad} -> {r.status_code} {r.text}"
            print("[OK] Invalid provider payloads rejected with 422")

            # ── add a Bedrock provider ────────────────────────────────────
            r = await client.post(
                "/api/v1/llm/providers",
                json={
                    "label": "Bedrock Claude",
                    "kind": "bedrock",
                    "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                    "aws_region": "us-west-2",
                    "aws_access_key_id": FAKE_AWS_ID,
                    "aws_secret_access_key": FAKE_AWS_SECRET,
                    "activate": False,
                },
            )
            assert r.status_code == 201, r.text
            cfg = r.json()
            bedrock = next(p for p in cfg["providers"] if p["label"] == "Bedrock Claude")
            bedrock_id = bedrock["id"]
            assert cfg["active"]["provider_id"] == ali_id, "activate=false must not switch"
            assert bedrock["aws_secret_access_key"] == "****0000", bedrock
            assert FAKE_AWS_SECRET not in r.text, "cleartext AWS secret leaked"
            assert FAKE_AWS_ID not in r.text, "cleartext AWS key id leaked"
            assert bedrock["aws_region"] == "us-west-2", bedrock
            print("[OK] Bedrock provider saved with masked AWS credentials")

            # ── switching the active provider ─────────────────────────────
            r = await client.post(f"/api/v1/llm/providers/{bedrock_id}/activate")
            assert r.status_code == 200, r.text
            assert r.json()["active"]["kind"] == "bedrock", r.json()["active"]
            assert resolve_llm().kind == "bedrock"
            assert resolve_llm().configured is True, "region is enough for bedrock"
            print("[OK] Activation switches protocol family to bedrock")

            # ── store survives a reload from disk ─────────────────────────
            get_provider_store().reload()
            reloaded = get_provider_store()
            assert len(reloaded.list()) == 2, reloaded.list()
            assert reloaded.active_id == bedrock_id, reloaded.active_id
            assert reloaded.get(bedrock_id).aws_secret_access_key == FAKE_AWS_SECRET
            print("[OK] Providers and active choice persisted across reload")

            # ── deactivate falls back to .env ─────────────────────────────
            r = await client.post("/api/v1/llm/deactivate")
            assert r.status_code == 200, r.text
            assert r.json()["active"]["source"] == "env", r.json()["active"]
            assert resolve_llm().source == "env"
            print("[OK] Deactivate falls back to .env")

            # ── deleting the active provider also falls back ──────────────
            await client.post(f"/api/v1/llm/providers/{ali_id}/activate")
            r = await client.delete(f"/api/v1/llm/providers/{ali_id}")
            assert r.status_code == 200, r.text
            cfg = r.json()
            assert cfg["active"]["source"] == "env", cfg["active"]
            assert [p["id"] for p in cfg["providers"]] == [bedrock_id], cfg["providers"]
            print("[OK] Deleting the active provider reverts to .env")

            r = await client.delete("/api/v1/llm/providers/does-not-exist")
            assert r.status_code == 404, r.text
            print("[OK] Unknown provider id returns 404")

            # ── health reflects the active provider ───────────────────────
            r = await client.get("/api/v1/health")
            body = r.json()
            assert body["llm_source"] == "env", body
            await client.post(f"/api/v1/llm/providers/{bedrock_id}/activate")
            body = (await client.get("/api/v1/health")).json()
            assert body["llm_source"] == "runtime", body
            assert body["llm_provider"] == "Bedrock Claude", body
            assert body["llm_configured"] is True, body
            print(f"[OK] Health reports active provider  {body['llm_provider']}")

            r = await client.post(
                "/api/v1/llm/providers",
                json={
                    "label": "FLUX.1-dev",
                    "kind": "huggingface_image",
                    "model": "black-forest-labs/FLUX.1-dev",
                    "hf_provider": "fal-ai",
                    "api_key": "hf_placeholder_token_0001",
                    "activate": True,
                },
            )
            assert r.status_code == 201, r.text
            cfg = r.json()
            flux = next(p for p in cfg["providers"] if p["kind"] == "huggingface_image")
            assert cfg["active"]["kind"] == "bedrock", cfg["active"]
            assert flux["hf_provider"] == "fal-ai"
            assert "hf_placeholder_token_0001" not in r.text
            r = await client.post(f"/api/v1/llm/providers/{flux['id']}/activate")
            assert r.status_code == 422, r.text
            r = await client.put("/api/v1/llm/routes", json={"image": flux["id"]})
            assert r.status_code == 200, r.text
            assert r.json()["routes"]["image"] == flux["id"]
            r = await client.put("/api/v1/llm/routes", json={"chat": flux["id"]})
            assert r.status_code == 422, r.text
            print("[OK] huggingface_image is routed for image, never the chat default")


def bedrock_sdk_checks() -> None:
    """If boto3 is installed, confirm the client and payload actually build.

    Region only, no credentials and no network call: this checks that the
    optional dependency is wired correctly, not that any account works.
    """
    try:
        import boto3
    except ImportError:
        print("[SKIP] boto3 not installed; Bedrock calls would raise a clear error")
        return

    from app.llm.bedrock import _build_client, _build_kwargs
    from app.llm.providers import ResolvedLLM

    cfg = ResolvedLLM(
        source="runtime",
        kind="bedrock",
        label="probe",
        model="anthropic.claude-3-5-sonnet-20241022-v2:0",
        aws_region="us-west-2",
        temperature=0.0,
        max_tokens=32,
        timeout_seconds=30,
        max_retries=0,
    )
    assert cfg.configured is True, "region alone must count as configured"

    client = _build_client(cfg)
    assert "bedrock-runtime" in client.meta.endpoint_url, client.meta.endpoint_url
    assert "us-west-2" in client.meta.endpoint_url, client.meta.endpoint_url
    assert hasattr(client, "converse") and hasattr(client, "converse_stream")
    print(f"[OK] boto3 {boto3.__version__} client -> {client.meta.endpoint_url}")

    kwargs = _build_kwargs(
        cfg,
        [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "ping"},
        ],
        model=None,
        temperature=None,
        max_tokens=None,
        tools=None,
    )
    assert kwargs["modelId"] == cfg.model, kwargs["modelId"]
    assert kwargs["system"] == [{"text": "be brief"}], kwargs["system"]
    assert kwargs["messages"] == [
        {"role": "user", "content": [{"text": "ping"}]}
    ], kwargs["messages"]
    assert kwargs["inferenceConfig"] == {"temperature": 0.0, "maxTokens": 32}
    # Converse would reject an OpenAI-style flat "messages"/"max_tokens" payload.
    assert "max_tokens" not in kwargs and "temperature" not in kwargs
    print("[OK] Converse request payload well-formed for the AWS SDK")


async def disabled_flag_check() -> None:
    """With the feature switched off, .env wins and writes are refused."""
    from app.core.config import settings

    original = settings.runtime_llm_config_enabled
    settings.runtime_llm_config_enabled = False
    try:
        assert resolve_llm().source == "env", "disabled flag must ignore the store"
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            async with app.router.lifespan_context(app):
                r = await client.post(
                    "/api/v1/llm/providers",
                    json={
                        "label": "should-fail",
                        "model": "m",
                        "base_url": "https://example.com/v1",
                    },
                )
                assert r.status_code == 422, r.text
                assert "disabled" in r.text, r.text
        print("[OK] RUNTIME_LLM_CONFIG_ENABLED=false forces .env and blocks writes")
    finally:
        settings.runtime_llm_config_enabled = original


async def main() -> None:
    unit_checks()
    print()
    bedrock_sdk_checks()
    print()
    await api_checks()
    print()
    await disabled_flag_check()
    print("\n[PASS] LLM config all tests passed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        shutil.rmtree(_STORE_DIR, ignore_errors=True)
