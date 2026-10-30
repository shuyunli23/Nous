"""Node: load conversation history from the database."""

from __future__ import annotations

from typing import Any

from app.agent.state import AgentState
from app.core.logging import get_logger
from app.memory.conversation_memory import load_history
from app.repositories.conversation_repo import ConversationRepository
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


def material_context(rows) -> dict[str, Any]:
    """Restore the latest authored plan and output references, not old reviews."""
    plan = None
    files: dict[str, str] = {}
    drafts: dict[str, dict[str, Any]] = {}
    for row in rows:
        for step in getattr(row, "execution_trace", None) or []:
            if step.get("status") == "error":
                continue
            if isinstance(step.get("material_plan"), dict):
                incoming = step["material_plan"]
                if not plan or incoming.get("plan_id") != plan.get("plan_id"):
                    drafts = {}
                    files = {}
                plan = incoming
            if isinstance(step.get("material_draft"), dict):
                draft = step["material_draft"]
                if plan and draft.get("plan_id") == plan.get("plan_id"):
                    drafts[draft["kind"]] = draft
            item = step.get("inspect") or {}
            if item.get("kind") in {"pptx", "pdf"} and item.get("file"):
                from app.agent.tools.export_urls import export_download_url

                files[item["kind"]] = export_download_url(item["file"])
    return {"material_plan": plan, "material_plan_id": plan.get("plan_id") if plan else None,
            "material_files": files, "material_drafts": drafts}


async def load_memory_node(state: AgentState, *, session: AsyncSession) -> AgentState:
    conversation_id = state["conversation_id"]
    conversation = await ConversationRepository(session).get(conversation_id)
    todos = list(conversation.todos or []) if conversation else []
    history = await load_history(
        session,
        conversation_id,
        existing_summary=conversation.summary if conversation else None,
    )
    rows = await ConversationRepository(session).list_messages(conversation_id, limit=30)
    materials = material_context(rows)
    logger.debug(
        "memory_loaded",
        conversation_id=conversation_id,
        turns=len(history),
        todos=len(todos),
    )
    return {**state, "history": history, "todos": todos, **materials}
