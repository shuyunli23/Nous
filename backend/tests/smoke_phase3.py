"""Phase 3 smoke test: Skill Extractor + skill CRUD.

Mocks the LLM so no API key is needed. Verifies:
 1. Manual skill CRUD (create / list / get / update+version / status / delete)
 2. Extraction: too-few-messages -> skipped
 3. Extraction: not reusable -> skipped
 4. Extraction: reusable -> skill created with correct fields
 5. Deduplication: second similar conversation -> merged, not duplicated
 6. Feedback: negative feedback x3 -> auto-disabled
 7. Positive feedback updates success_rate
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from app.llm.client import CompletionResult, Usage
from app.main import app
from app.skill.extractor import ReusabilityResult, SkillDraft

CHAT_REPLY = CompletionResult(
    content="GitLab SSH timeout fix: 1) ssh -vT 2) check port 22 3) check proxy 4) verify key",
    usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
)

JUDGE_YES = ReusabilityResult(
    reusable=True, confidence=0.92, reason="contains reusable troubleshooting steps"
)
JUDGE_NO = ReusabilityResult(
    reusable=False, confidence=0.1, reason="just chitchat, no reuse value"
)

DRAFT = SkillDraft(
    name="GitLab SSH connection troubleshooting",
    description="Solve GitLab SSH connection timeout issues",
    instruction="Follow workflow in order, network first then config",
    trigger_keywords=["ssh timeout", "gitlab ssh", "port 22", "connection timeout"],
    trigger_intent="troubleshoot git remote connection failure",
    workflow=[
        {"step": 1, "action": "check ssh connectivity", "command": "ssh -vT git@gitlab.com"},
        {"step": 2, "action": "check if port 22 is open"},
        {"step": 3, "action": "check proxy config"},
        {"step": 4, "action": "verify ssh key"},
    ],
    examples=[{"question": "SSH cannot connect to GitLab", "solution": "Follow 4-step checklist"}],
    tools=[],
)


async def seed_conversation(client: httpx.AsyncClient, turns: int) -> str:
    """Create a conversation with N user+assistant turns via mocked chat."""
    cid: str | None = None
    with patch(
        "app.agent.nodes.llm_call.chat_complete",
        new=AsyncMock(return_value=CHAT_REPLY),
    ):
        for i in range(turns):
            body: dict = {"message": f"GitLab SSH timeout fix? question {i + 1}"}
            if cid:
                body["conversation_id"] = cid
            r = await client.post("/api/v1/chat", json=body)
            assert r.status_code == 200, f"chat failed: {r.text}"
            cid = r.json()["conversation_id"]
    assert cid
    return cid


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=30
    ) as client:
        async with app.router.lifespan_context(app):

            # Isolate from skills left behind by other phase runs, otherwise
            # dedup correctly merges into an existing skill and the "create"
            # assertions below no longer apply.
            existing = await client.get("/api/v1/skills?limit=100")
            for item in existing.json()["items"]:
                await client.delete(f"/api/v1/skills/{item['id']}")

            # === 1. Manual skill CRUD =====================================
            r = await client.post(
                "/api/v1/skills",
                json={
                    "name": "Manual Test Skill",
                    "description": "created manually for testing",
                    "trigger_keywords": ["test", "manual"],
                    "workflow": [{"step": 1, "action": "step one"}],
                },
            )
            assert r.status_code == 201, r.text
            manual = r.json()
            sid = manual["id"]
            assert manual["source"] == "manual"
            assert manual["status"] == "active"
            assert manual["version"] == 1
            print(f"[OK] Manual create  id={sid[:8]}... v{manual['version']} {manual['status']}")

            r = await client.get("/api/v1/skills")
            assert r.status_code == 200
            assert r.json()["total"] >= 1
            print(f"[OK] List skills  total={r.json()['total']}")

            r = await client.put(
                f"/api/v1/skills/{sid}",
                json={"description": "updated description"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["version"] == 2, f"version should bump: {r.json()['version']}"
            assert r.json()["description"] == "updated description"
            print(f"[OK] Update bumps version -> v{r.json()['version']}")

            r = await client.patch(
                f"/api/v1/skills/{sid}/status", json={"status": "disabled"}
            )
            assert r.status_code == 200
            assert r.json()["status"] == "disabled"
            print("[OK] Status patch -> disabled")

            r = await client.delete(f"/api/v1/skills/{sid}")
            assert r.status_code == 204
            r = await client.get(f"/api/v1/skills/{sid}")
            assert r.status_code == 404
            print("[OK] Delete + 404 confirmed")

            # === 2. Too few messages -> skipped ===========================
            cid_short = await seed_conversation(client, turns=1)  # 2 messages
            r = await client.post(
                "/api/v1/skills/generate", json={"conversation_id": cid_short}
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["skipped"] is True
            assert data["extraction_status"] == "skipped"
            assert "Too few messages" in (data["reason"] or "")
            print(f"[OK] Too few messages -> skipped  ({data['reason']})")

            # === 3. Not reusable -> skipped ===============================
            cid_chat = await seed_conversation(client, turns=3)  # 6 messages
            with patch(
                "app.skill.extractor.structured_complete",
                new=AsyncMock(return_value=JUDGE_NO),
            ):
                r = await client.post(
                    "/api/v1/skills/generate", json={"conversation_id": cid_chat}
                )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["skipped"] is True
            assert "Not reusable" in (data["reason"] or "")
            print(f"[OK] Not reusable -> skipped  ({data['reason'][:50]})")

            # === 4. Reusable -> skill created =============================
            cid_good = await seed_conversation(client, turns=3)
            with patch(
                "app.skill.extractor.structured_complete",
                new=AsyncMock(side_effect=[JUDGE_YES, DRAFT]),
            ):
                r = await client.post(
                    "/api/v1/skills/generate", json={"conversation_id": cid_good}
                )
            assert r.status_code == 200, r.text
            data = r.json()
            assert not data["skipped"], data
            assert data["extraction_status"] == "done"
            assert data["skill_id"], data
            new_sid = data["skill_id"]
            print(f"[OK] Extraction created skill  id={new_sid[:8]}...")

            r = await client.get(f"/api/v1/skills/{new_sid}")
            assert r.status_code == 200
            sk = r.json()
            assert sk["name"] == DRAFT.name
            assert sk["source"] == "auto"
            assert sk["status"] == "draft", f"auto skills start as draft: {sk['status']}"
            assert sk["confidence"] == 0.92
            assert len(sk["workflow"]) == 4
            assert sk["created_from_conversation_id"] == cid_good
            assert sk["examples"][0]["conversation_id"] == cid_good
            print(f"    name={sk['name']!r} status={sk['status']} conf={sk['confidence']}")
            print(f"    keywords={sk['trigger_keywords']}")
            print(f"    workflow steps={len(sk['workflow'])}")

            # === 5. Dedup: same skill name -> merged =======================
            cid_dup = await seed_conversation(client, turns=3)
            with patch(
                "app.skill.extractor.structured_complete",
                new=AsyncMock(side_effect=[JUDGE_YES, DRAFT]),
            ):
                r = await client.post(
                    "/api/v1/skills/generate", json={"conversation_id": cid_dup}
                )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["merged_into"] == new_sid, data
            assert data["skill_id"] is None
            print(f"[OK] Dedup merged into existing  {data['reason']}")

            r = await client.get(f"/api/v1/skills/{new_sid}")
            merged = r.json()
            assert len(merged["examples"]) == 2, f"should have 2 examples: {len(merged['examples'])}"
            assert merged["version"] == 2, f"merge bumps version: {merged['version']}"
            print(f"    examples={len(merged['examples'])} version=v{merged['version']}")

            # === 6. Feedback -> auto-disable after 3 negatives ============
            await client.patch(
                f"/api/v1/skills/{new_sid}/status", json={"status": "active"}
            )
            for _ in range(3):
                r = await client.post(
                    f"/api/v1/skills/{new_sid}/feedback",
                    json={"feedback": "negative"},
                )
                assert r.status_code == 200, r.text

            r = await client.get(f"/api/v1/skills/{new_sid}")
            final = r.json()
            assert final["failure_count"] == 3, final["failure_count"]
            assert final["status"] == "disabled", f"should auto-disable: {final['status']}"
            assert final["success_rate"] == 0.0
            print(
                f"[OK] 3x negative feedback -> auto-disabled  "
                f"(fail={final['failure_count']}, rate={final['success_rate']})"
            )

            # === 7. Positive feedback updates success_rate ================
            for _ in range(3):
                await client.post(
                    f"/api/v1/skills/{new_sid}/feedback",
                    json={"feedback": "positive"},
                )
            r = await client.get(f"/api/v1/skills/{new_sid}")
            fin = r.json()
            assert fin["success_count"] == 3
            assert fin["success_rate"] == 0.5, fin["success_rate"]
            print(
                f"[OK] Feedback ledger  success={fin['success_count']} "
                f"fail={fin['failure_count']} rate={fin['success_rate']} "
                f"usage={fin['usage_count']}"
            )

    print("\n[PASS] Phase 3 all tests passed")


if __name__ == "__main__":
    asyncio.run(main())
