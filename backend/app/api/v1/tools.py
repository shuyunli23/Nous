"""List built-in agent tools."""

from __future__ import annotations

from fastapi import APIRouter

from app.agent.tools import list_tool_catalog

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", summary="List available agent tools")
async def list_tools() -> dict:
    items = list_tool_catalog()
    return {"items": items, "total": len(items)}
