"""Phase 2 smoke test: agent graph + chat endpoint.

Two scenarios:
1. LLM not configured -> expect 502 with code=llm_error  (no API key)
2. Conversation wiring: the conversation is created and messages are stored
   (we mock the LLM call so we don't need a real API key).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from app.llm.client import CompletionResult, Usage
from app.main import app

MOCK_RESULT = CompletionResult(
    content="这是一个模拟的 Agent 回答，用于测试流程是否走通。",
    tool_calls=[],
    finish_reason="stop",
    usage=Usage(prompt_tokens=20, completion_tokens=30, total_tokens=50),
)


async def main() -> None:
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        async with app.router.lifespan_context(app):

            # ── 1. No API key -> 502 llm_error ────────────────────────────
            resp = await client.post(
                "/api/v1/chat", json={"message": "你好，测试一下"}
            )
            assert resp.status_code == 502, f"Expected 502, got {resp.status_code}: {resp.text}"
            err = resp.json()["error"]
            assert err["code"] == "llm_error", f"Expected llm_error, got {err}"
            print("[OK] No API key -> 502 llm_error")

            # ── 2. Mocked LLM -> full pipeline ────────────────────────────
            with patch(
                "app.agent.nodes.llm_call.chat_complete",
                new=AsyncMock(return_value=MOCK_RESULT),
            ):
                resp = await client.post(
                    "/api/v1/chat",
                    json={"message": "如何解决 GitLab SSH 连接超时？"},
                )
                assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
                data = resp.json()
                cid = data["conversation_id"]
                mid = data["message_id"]
                assert data["answer"] == MOCK_RESULT.content
                assert data["token_usage"]["total_tokens"] == 50
                print(f"[OK] Chat OK  cid={cid[:8]}... mid={mid[:8]}...")
                print(f"  title={data['title']!r}")

                # ── 3. Second turn in same conversation ───────────────────
                resp2 = await client.post(
                    "/api/v1/chat",
                    json={
                        "message": "还是连不上，端口 22 被封了",
                        "conversation_id": cid,
                    },
                )
                assert resp2.status_code == 200, f"Second turn failed: {resp2.text}"
                print(f"[OK] Second turn OK  mid={resp2.json()['message_id'][:8]}...")

                # ── 4. Verify messages stored in DB ───────────────────────
                detail = await client.get(f"/api/v1/conversations/{cid}")
                assert detail.status_code == 200
                msgs = detail.json()["messages"]
                # 2 user + 2 assistant = 4 messages
                assert len(msgs) == 4, f"Expected 4 messages, got {len(msgs)}: {msgs}"
                roles = [m["role"] for m in msgs]
                assert roles == ["user", "assistant", "user", "assistant"], roles
                print(f"[OK] DB has {len(msgs)} messages  roles={roles}")

                # ── 5. Close conversation ─────────────────────────────────
                close = await client.post(f"/api/v1/conversations/{cid}/close")
                assert close.status_code == 200
                assert close.json()["status"] == "closed"
                print("[OK] Conversation closed")

                # ── 6. Sending to closed conversation -> 502 ───────────────
                resp3 = await client.post(
                    "/api/v1/chat",
                    json={"message": "再发一条", "conversation_id": cid},
                )
                assert resp3.status_code == 502, f"Expected 502, got {resp3.status_code}"
                print("[OK] Closed conversation -> 502 llm_error")

    print("\n[PASS] Phase 2 all tests passed")


if __name__ == "__main__":
    asyncio.run(main())
