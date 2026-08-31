"""Chat mode use cases: builtins, custom CRUD, resolve for a turn."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat_modes.catalog import (
    COMPANION,
    TOOL_LIGHT,
    TUTOR,
    WORKBENCH,
    builtin_specs,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.database.models.chat_mode import ChatMode
from app.repositories.chat_mode_repo import ChatModeRepository

logger = get_logger(__name__)


class ChatModeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ChatModeRepository(session)

    async def list_for_user(self, user_id: str) -> list[ChatMode]:
        await ensure_builtin_modes(self.session)
        return await self.repo.list_for_user(user_id)

    async def get_for_user(self, mode_id: str, *, user_id: str) -> ChatMode:
        mode = await self.repo.get(mode_id)
        if mode is None:
            raise NotFoundError("Chat mode not found.", details={"mode_id": mode_id})
        if not mode.is_builtin and mode.user_id != user_id:
            raise NotFoundError("Chat mode not found.", details={"mode_id": mode_id})
        return mode

    async def resolve(
        self, *, user_id: str, mode_id: str | None
    ) -> ChatMode:
        await ensure_builtin_modes(self.session)
        if mode_id:
            return await self.get_for_user(mode_id, user_id=user_id)
        workbench = await self.repo.get_by_key(WORKBENCH)
        if workbench is None:
            raise NotFoundError("Default workbench mode is missing.")
        return workbench

    async def create_custom(
        self,
        *,
        user_id: str,
        name: str,
        system_prompt: str,
        use_long_term_memory: bool = False,
        use_knowledge_memory: bool = False,
        description: str = "",
    ) -> ChatMode:
        title = name.strip()
        if not title:
            raise ValidationError("Mode name is required.")
        prompt = system_prompt.strip()
        if not prompt:
            raise ValidationError("System prompt is required.")
        if len(prompt) > 16000:
            raise ValidationError("System prompt is too long.")
        key = f"c_{uuid.uuid4().hex[:12]}"
        mode = ChatMode(
            user_id=user_id,
            key=key,
            name=title[:80],
            description=(description or "").strip()[:400],
            system_prompt=prompt,
            tool_policy=TOOL_LIGHT,
            use_long_term_memory=bool(use_long_term_memory),
            use_knowledge_memory=bool(use_knowledge_memory),
            is_builtin=False,
            sort_order=100,
        )
        await self.repo.add(mode)
        await self.session.commit()
        await self.session.refresh(mode)
        logger.info("chat_mode_created", mode_id=mode.id, user_id=user_id)
        return mode

    async def update_custom(
        self,
        mode_id: str,
        *,
        user_id: str,
        name: str | None = None,
        system_prompt: str | None = None,
        use_long_term_memory: bool | None = None,
        use_knowledge_memory: bool | None = None,
        description: str | None = None,
    ) -> ChatMode:
        mode = await self.get_for_user(mode_id, user_id=user_id)
        if mode.is_builtin:
            if mode.key not in {TUTOR, COMPANION}:
                raise ValidationError("Built-in modes cannot be edited.")
            extras = [
                name is not None,
                system_prompt is not None,
                use_long_term_memory is not None,
                description is not None,
            ]
            if any(extras):
                raise ValidationError(
                    "Only the knowledge-background toggle can be changed on built-in tutor and companion modes."
                )
            if use_knowledge_memory is None:
                return mode
            mode.use_knowledge_memory = bool(use_knowledge_memory)
            await self.session.commit()
            await self.session.refresh(mode)
            return mode
        if name is not None:
            title = name.strip()
            if not title:
                raise ValidationError("Mode name is required.")
            mode.name = title[:80]
        if system_prompt is not None:
            prompt = system_prompt.strip()
            if not prompt:
                raise ValidationError("System prompt is required.")
            if len(prompt) > 16000:
                raise ValidationError("System prompt is too long.")
            mode.system_prompt = prompt
        if use_long_term_memory is not None:
            mode.use_long_term_memory = bool(use_long_term_memory)
        if use_knowledge_memory is not None:
            mode.use_knowledge_memory = bool(use_knowledge_memory)
        if description is not None:
            mode.description = description.strip()[:400]
        await self.session.commit()
        await self.session.refresh(mode)
        return mode

    async def delete_custom(self, mode_id: str, *, user_id: str) -> None:
        mode = await self.get_for_user(mode_id, user_id=user_id)
        if mode.is_builtin:
            raise ValidationError("Built-in modes cannot be deleted.")
        await self.repo.delete(mode)
        await self.session.commit()
        logger.info("chat_mode_deleted", mode_id=mode_id, user_id=user_id)


async def ensure_builtin_modes(session: AsyncSession) -> None:
    """Idempotent seed so prompt-file edits win on the next process start."""
    for spec in builtin_specs():
        result = await session.execute(
            select(ChatMode).where(ChatMode.key == spec["key"])
        )
        row = result.scalar_one_or_none()
        if row is None:
            session.add(
                ChatMode(
                    user_id=None,
                    key=spec["key"],
                    name=spec["name"],
                    description=spec["description"],
                    system_prompt="",
                    tool_policy=spec["tool_policy"],
                    use_long_term_memory=spec["use_long_term_memory"],
                    use_knowledge_memory=bool(spec.get("use_knowledge_memory", False)),
                    is_builtin=True,
                    sort_order=spec["sort_order"],
                )
            )
            continue
        row.name = spec["name"]
        row.description = spec["description"]
        row.tool_policy = spec["tool_policy"]
        row.use_long_term_memory = spec["use_long_term_memory"]
        row.is_builtin = True
        row.sort_order = spec["sort_order"]
        row.system_prompt = ""
        # Do not overwrite tutor.use_knowledge_memory — that toggle is the user's.
    await session.execute(
        update(ChatMode)
        .where(ChatMode.is_builtin.is_(False), ChatMode.tool_policy == "none")
        .values(tool_policy=TOOL_LIGHT)
    )
    await session.commit()
