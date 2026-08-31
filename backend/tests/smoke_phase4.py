"""Phase 4 smoke test: embeddings, vector store, hybrid retrieval, injection.

Runs with EMBEDDING_PROVIDER=hash and VECTOR_BACKEND=memory so no network
access or model download is required. Verifies:
 1. Embedding provider basics (determinism, dimension, similarity ordering)
 2. Vector store upsert/query/delete/where-filter
 3. Reindex builds the index from the DB
 4. Hybrid search finds the right skill and reports score breakdown
 5. Irrelevant queries are filtered by the similarity threshold
 6. Disabled skills are excluded from retrieval
 7. Chat injects retrieved skills into the system prompt
 8. skill_usages ledger + usage_count increment on retrieval
"""

from __future__ import annotations

import asyncio
import os

# Must be set before app.core.config is imported.
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["VECTOR_BACKEND"] = "memory"
os.environ["SKILL_MIN_SIMILARITY"] = "0.28"

from unittest.mock import AsyncMock, patch  # noqa: E402

import httpx  # noqa: E402

from app.llm.client import CompletionResult, Usage  # noqa: E402
from app.llm.embeddings import (  # noqa: E402
    cosine_similarity,
    embed_text,
    embed_texts,
    get_dimension,
)
from app.main import app  # noqa: E402
from app.memory.vector_store import get_vector_store  # noqa: E402

CHAT_REPLY = CompletionResult(
    content="Follow the workflow: check connectivity, port, proxy, then key.",
    usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
)

SSH_SKILL = {
    "name": "GitLab SSH connection troubleshooting",
    "description": "Solve GitLab SSH connection timeout and port issues",
    "instruction": "Follow workflow in order, network first then config",
    "trigger_keywords": ["ssh timeout", "gitlab ssh", "port 22", "connection refused"],
    "trigger_intent": "troubleshoot git remote connection failure",
    "workflow": [
        {"step": 1, "action": "check ssh connectivity", "command": "ssh -vT git@gitlab.com"},
        {"step": 2, "action": "check if port 22 is open"},
        {"step": 3, "action": "check proxy config"},
    ],
}

DOCKER_SKILL = {
    "name": "Docker container disk cleanup",
    "description": "Reclaim disk space taken by dangling images and volumes",
    "trigger_keywords": ["docker disk full", "no space left", "prune images"],
    "trigger_intent": "free disk space consumed by docker",
    "workflow": [{"step": 1, "action": "run docker system prune"}],
}


async def unit_checks() -> None:
    """Provider + vector store behaviour, no HTTP involved."""
    dim = get_dimension()
    assert dim == 512, f"hash provider dim should be 512, got {dim}"

    v1 = await embed_text("gitlab ssh timeout port 22")
    v2 = await embed_text("gitlab ssh timeout port 22")
    assert v1 == v2, "hash embeddings must be deterministic"
    assert len(v1) == dim
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-6, f"vector should be L2-normalised, norm={norm}"
    print(f"[OK] Embeddings deterministic, dim={dim}, L2-normalised")

    batch = await embed_texts(["ssh timeout", "docker disk full"])
    assert len(batch) == 2
    related = cosine_similarity(
        await embed_text("gitlab ssh connection timeout"),
        await embed_text("ssh timeout on gitlab"),
    )
    unrelated = cosine_similarity(
        await embed_text("gitlab ssh connection timeout"),
        await embed_text("docker disk full prune images"),
    )
    assert related > unrelated, f"related={related:.3f} should beat unrelated={unrelated:.3f}"
    print(f"[OK] Similarity ordering  related={related:.3f} > unrelated={unrelated:.3f}")

    store = get_vector_store()
    store.reset()
    store.upsert(skill_id="a", embedding=v1, metadata={"user_id": "u1", "status": "active"})
    store.upsert(
        skill_id="b",
        embedding=await embed_text("docker disk full"),
        metadata={"user_id": "u1", "status": "disabled"},
    )
    store.upsert(skill_id="c", embedding=v1, metadata={"user_id": "u2", "status": "active"})
    assert store.count() == 3, store.count()

    hits = store.query(embedding=v1, top_k=5, where={"user_id": "u1"})
    ids = [h.skill_id for h in hits]
    assert "c" not in ids, "where filter must exclude other users"
    assert ids[0] == "a", f"exact vector match should rank first: {ids}"
    print(f"[OK] Vector store query + where filter  ids={ids}")

    hits_active = store.query(
        embedding=v1, top_k=5, where={"user_id": "u1", "status": "active"}
    )
    assert [h.skill_id for h in hits_active] == ["a"], hits_active
    print("[OK] Multi-key where filter (user_id + status)")

    store.delete("a")
    assert store.count() == 2
    store.reset()
    assert store.count() == 0
    print("[OK] Vector store delete + reset")


async def api_checks() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=30
    ) as client:
        async with app.router.lifespan_context(app):
            get_vector_store().reset()

            # Clean slate: remove skills left by earlier phase runs.
            existing = await client.get("/api/v1/skills?limit=100")
            for item in existing.json()["items"]:
                await client.delete(f"/api/v1/skills/{item['id']}")

            r = await client.post("/api/v1/skills", json=SSH_SKILL)
            assert r.status_code == 201, r.text
            ssh_id = r.json()["id"]
            r = await client.post("/api/v1/skills", json=DOCKER_SKILL)
            assert r.status_code == 201, r.text
            docker_id = r.json()["id"]
            print(f"[OK] Seeded 2 skills  ssh={ssh_id[:8]} docker={docker_id[:8]}")

            # Creating a skill should have indexed it already.
            assert get_vector_store().count() == 2, get_vector_store().count()
            print(f"[OK] Auto-indexed on create  vectors={get_vector_store().count()}")

            # ── reindex ───────────────────────────────────────────────────
            r = await client.post("/api/v1/skills/reindex")
            assert r.status_code == 200, r.text
            stats = r.json()
            assert stats["skipped"] == 2, f"unchanged rows should skip: {stats}"
            print(f"[OK] Reindex skips unchanged  {stats['skipped']} skipped")

            r = await client.post("/api/v1/skills/reindex?force=true")
            stats = r.json()
            assert stats["indexed"] == 2, f"force should reindex all: {stats}"
            assert stats["embedding_provider"] == "hash"
            print(f"[OK] Force reindex  indexed={stats['indexed']} provider={stats['embedding_provider']}")

            # ── hybrid search: relevant query ─────────────────────────────
            r = await client.post(
                "/api/v1/skills/search",
                json={"query": "my gitlab ssh is timing out again on port 22"},
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["count"] >= 1, data
            top = data["results"][0]
            assert top["id"] == ssh_id, f"SSH skill should win: {data['results']}"
            assert top["keyword_score"] > 0, top
            assert top["matched_keywords"], top
            print(
                f"[OK] Hybrid search  top={top['name'][:32]!r} score={top['score']} "
                f"(vec={top['vector_similarity']} kw={top['keyword_score']})"
            )
            print(f"     matched_keywords={top['matched_keywords']}")

            # ── docker query hits the other skill ─────────────────────────
            r = await client.post(
                "/api/v1/skills/search",
                json={"query": "docker disk full, no space left on device"},
            )
            top = r.json()["results"][0]
            assert top["id"] == docker_id, f"Docker skill should win: {r.json()}"
            print(f"[OK] Different query -> different skill  {top['name'][:32]!r}")

            # ── irrelevant query filtered by threshold ────────────────────
            r = await client.post(
                "/api/v1/skills/search",
                json={"query": "what is the capital city of France"},
            )
            assert r.json()["count"] == 0, f"should filter out: {r.json()}"
            print("[OK] Irrelevant query -> 0 results (threshold works)")

            # ── disabled skill excluded ───────────────────────────────────
            await client.patch(
                f"/api/v1/skills/{ssh_id}/status", json={"status": "disabled"}
            )
            r = await client.post(
                "/api/v1/skills/search",
                json={"query": "gitlab ssh timeout port 22"},
            )
            ids = [item["id"] for item in r.json()["results"]]
            assert ssh_id not in ids, f"disabled skill must be excluded: {ids}"
            print("[OK] Disabled skill excluded from retrieval")

            await client.patch(
                f"/api/v1/skills/{ssh_id}/status", json={"status": "active"}
            )

            # ── chat injects the skill ────────────────────────────────────
            captured: dict = {}

            async def capture(messages, **kwargs):
                captured["messages"] = messages
                return CHAT_REPLY

            with patch("app.agent.nodes.llm_call.chat_complete", new=capture):
                r = await client.post(
                    "/api/v1/chat",
                    json={"message": "gitlab ssh timeout again, port 22 refused"},
                )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["used_skills"], f"chat should report used skills: {body}"
            assert body["used_skills"][0]["id"] == ssh_id
            assert body["used_skills"][0]["similarity"] is not None
            print(
                f"[OK] Chat reports used_skills  "
                f"{body['used_skills'][0]['name'][:32]!r} "
                f"sim={body['used_skills'][0]['similarity']}"
            )

            system_prompt = captured["messages"][0]["content"]
            assert captured["messages"][0]["role"] == "system"
            assert "GitLab SSH connection troubleshooting" in system_prompt, system_prompt[:400]
            assert "check ssh connectivity" in system_prompt, "workflow must be injected"
            assert "Skill" in system_prompt
            print("[OK] System prompt contains injected skill name + workflow steps")

            # ── usage ledger ──────────────────────────────────────────────
            r = await client.get(f"/api/v1/skills/{ssh_id}")
            sk = r.json()
            assert sk["usage_count"] >= 1, sk["usage_count"]
            assert sk["last_used_at"] is not None
            print(
                f"[OK] Usage recorded  usage_count={sk['usage_count']} "
                f"last_used_at set"
            )

            # message row records which skills were used
            cid = body["conversation_id"]
            r = await client.get(f"/api/v1/conversations/{cid}")
            assistant_msgs = [
                m for m in r.json()["messages"] if m["role"] == "assistant"
            ]
            assert assistant_msgs[-1]["used_skill_ids"] == [ssh_id], assistant_msgs[-1]
            print("[OK] Assistant message stores used_skill_ids (audit trail)")

            # ── delete removes from index ─────────────────────────────────
            before = get_vector_store().count()
            await client.delete(f"/api/v1/skills/{docker_id}")
            after = get_vector_store().count()
            assert after == before - 1, f"delete must unindex: {before} -> {after}"
            print(f"[OK] Delete unindexes  vectors {before} -> {after}")


async def main() -> None:
    await unit_checks()
    print()
    await api_checks()
    print("\n[PASS] Phase 4 all tests passed")


if __name__ == "__main__":
    asyncio.run(main())
