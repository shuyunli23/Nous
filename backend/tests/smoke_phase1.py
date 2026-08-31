"""Phase 1 smoke check: conversation CRUD over the real ASGI app."""

from __future__ import annotations

import asyncio

import httpx

from app.main import app


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        # lifespan must run so init_database() executes
        async with app.router.lifespan_context(app):
            health = await client.get("/api/v1/health")
            print("health", health.status_code, health.json())

            created = await client.post("/api/v1/conversations", json={})
            print("create", created.status_code, created.json())
            cid = created.json()["id"]

            listed = await client.get("/api/v1/conversations?limit=5")
            print("list", listed.status_code, "total=", listed.json()["total"])

            detail = await client.get(f"/api/v1/conversations/{cid}")
            print("detail", detail.status_code, detail.json()["messages"])

            renamed = await client.patch(
                f"/api/v1/conversations/{cid}", json={"title": "GitLab SSH 排查"}
            )
            print("rename", renamed.status_code, renamed.json()["title"])

            closed = await client.post(f"/api/v1/conversations/{cid}/close")
            print("close", closed.status_code, closed.json())

            missing = await client.get("/api/v1/conversations/does-not-exist")
            print("404", missing.status_code, missing.json())

            deleted = await client.delete(f"/api/v1/conversations/{cid}")
            print("delete", deleted.status_code)

            gone = await client.get(f"/api/v1/conversations/{cid}")
            print("after delete", gone.status_code)


if __name__ == "__main__":
    asyncio.run(main())
