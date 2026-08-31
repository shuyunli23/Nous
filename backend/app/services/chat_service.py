"""Chat use case: create/resume conversation, run agent, return answer."""

from __future__ import annotations

from app.agent.graph import run_agent
from app.chat_modes.catalog import WORKBENCH
from app.core.exceptions import LLMError, ValidationError
from app.core.logging import get_logger
from app.database.models.enums import ConversationStatus
from app.repositories.conversation_repo import ConversationRepository
from app.schemas.chat import ChatModeRef, ChatResponse, SkillUsedInfo
from app.services.chat_attachments import build_attachment_query, process_chat_uploads
from app.services.chat_mode_service import ChatModeService
from app.services.conversation_service import ConversationService
from app.services.memory_service import (
    UserMemoryService,
    wants_knowledge,
    wants_persona,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conv_svc = ConversationService(session)
        self.repo = ConversationRepository(session)
        self.modes = ChatModeService(session)

    async def chat(
        self,
        *,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
        files: list[tuple[str, bytes, str]] | None = None,
        mode_id: str | None = None,
        provider_id: str | None = None,
    ) -> ChatResponse:
        # ── 1. resolve or create conversation ──────────────────────────────
        if conversation_id:
            conversation = await self.conv_svc.get_or_404(
                conversation_id, user_id=user_id
            )
            if conversation.status == ConversationStatus.CLOSED:
                raise LLMError(
                    "This conversation is closed. Start a new one.",
                    details={"conversation_id": conversation_id},
                )
            mode = conversation.mode
            if mode is None:
                mode = await self.modes.resolve(user_id=user_id, mode_id=None)
        else:
            mode = await self.modes.resolve(user_id=user_id, mode_id=mode_id)
            conversation = await self.conv_svc.create(
                user_id=user_id, mode_id=mode.id
            )

        cid = conversation.id
        logger.info("chat_start", conversation_id=cid, user_id=user_id)
        from app.agent.progress import emit
        from app.llm.usage import PURPOSE_CHAT, usage_scope

        chosen_provider = (provider_id or "").strip() or None
        if chosen_provider:
            from app.llm.provider_store import get_provider_store

            get_provider_store().get(chosen_provider)

        emit({"type": "start", "conversation_id": cid})
        if (mode.tool_policy or "full") == "full":
            emit(
                {
                    "type": "step_start",
                    "node": "prepare",
                    "kind": "think",
                    "title": "准备中",
                    "status": "running",
                }
            )

        processed = process_chat_uploads(files or [])
        query, vision_parts, title_source = build_attachment_query(
            message, processed
        )
        if not query.strip():
            raise ValidationError("Message or files are required.")

        persona_on = wants_persona(mode)
        knowledge_on = wants_knowledge(mode)
        persona_block = knowledge_block = ""
        if persona_on or knowledge_on:
            persona_block, knowledge_block = await UserMemoryService(
                self.session
            ).blocks_for_mode(user_id, mode, query=query)

        # ── 2. run agent graph ─────────────────────────────────────────────
        with usage_scope(
            purpose=PURPOSE_CHAT,
            user_id=user_id,
            conversation_id=cid,
            provider_id=chosen_provider,
            session=self.session,
        ):
            final_state = await run_agent(
                session=self.session,
                user_id=user_id,
                conversation_id=cid,
                query=query,
                title_source=title_source,
                vision_parts=vision_parts,
                mode_key=mode.key or WORKBENCH,
                tool_policy=mode.tool_policy or "full",
                use_long_term_memory=persona_on,
                use_knowledge_memory=knowledge_on,
                persona_block=persona_block,
                knowledge_block=knowledge_block,
                mode_system_prompt=mode.system_prompt or "",
            )

        # ── 3. build response ──────────────────────────────────────────────
        # Reload conversation to get the updated title.
        updated_conv = await self.repo.get(cid)
        title = updated_conv.title if updated_conv else None

        # Surface which skills shaped the answer so the UI can show provenance
        # and let the user give per-skill feedback.
        retrieved = final_state.get("retrieved_skills") or []
        used_skills = [
            SkillUsedInfo(
                id=item.get("id", ""),
                name=item.get("name", ""),
                similarity=item.get("similarity"),
            )
            for item in retrieved
            if item.get("id")
        ]

        return ChatResponse(
            conversation_id=cid,
            message_id=final_state.get("assistant_message_id", ""),
            answer=final_state.get("response", ""),
            used_skills=used_skills,
            token_usage=final_state.get("usage"),
            title=title,
            execution_trace=final_state.get("execution_trace") or None,
            mode=ChatModeRef(
                id=mode.id,
                key=mode.key,
                name=mode.name,
                tool_policy=mode.tool_policy,
                use_long_term_memory=persona_on,
                use_knowledge_memory=knowledge_on,
            ),
        )
