"""Two-lane user memory: open fields, delta writes, catalog + selective recall."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat_modes.catalog import COMPANION, TUTOR, WORKBENCH
from app.core.logging import get_logger
from app.database.models.chat_mode import ChatMode
from app.database.models.memory_field import MemoryFieldRecord
from app.database.models.memory_item import MemoryItem
from app.database.models.user_memory import UserMemory
from app.llm.client import structured_complete
from app.llm.prompts.extraction import format_conversation
from app.llm.prompts.knowledge_memory_extraction import (
    KNOWLEDGE_EXTRACT_SYSTEM,
    KNOWLEDGE_EXTRACT_USER,
)
from app.llm.prompts.persona_extraction import PERSONA_EXTRACT_SYSTEM, PERSONA_EXTRACT_USER
from app.memory.facts import (
    LANE_KNOWLEDGE,
    LANE_PERSONA,
    FieldOp,
    MemoryFact,
    MemoryField,
    MemoryOp,
    MemoryProfile,
    apply_field_ops,
    apply_ops,
    drop_items_for_fields,
    facts_from_knowledge_blob,
    facts_from_persona_blob,
    fields_from_facts,
    format_extract_context,
    merge_summary,
    render_profile,
    tidy_profile,
    select_field_keys,
    select_for_prompt,
)
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.memory_field_repo import MemoryFieldRepository
from app.repositories.memory_item_repo import MemoryItemRepository

logger = get_logger(__name__)


class ExtractedField(BaseModel):
    op: str = "add"
    key: str = ""
    name: str = ""
    description: str = ""


class ExtractedItem(BaseModel):
    op: str = "add"
    field: str = ""
    category: str = ""
    key: str = ""
    title: str = ""
    value: str = ""
    pinned: bool = False


class ProfileDelta(BaseModel):
    summary: str = ""
    summary_changed: bool = True
    fields: list[ExtractedField] = Field(default_factory=list)
    items: list[ExtractedItem] = Field(default_factory=list)
    facts: list[ExtractedItem] = Field(default_factory=list)


def render_persona(data: dict[str, Any] | None) -> str:
    facts = facts_from_persona_blob(data)
    return render_profile(
        LANE_PERSONA, fields=fields_from_facts(facts, lane=LANE_PERSONA), items=facts
    )


def render_knowledge(data: dict[str, Any] | None) -> str:
    facts = facts_from_knowledge_blob(data)
    return render_profile(
        LANE_KNOWLEDGE, fields=fields_from_facts(facts, lane=LANE_KNOWLEDGE), items=facts
    )


def wants_persona(mode: ChatMode | None) -> bool:
    if mode is None:
        return False
    if mode.key == COMPANION:
        return True
    if mode.key in {WORKBENCH, TUTOR}:
        return False
    return bool(mode.use_long_term_memory)


def wants_knowledge(mode: ChatMode | None) -> bool:
    """Whether to inject the knowledge-background block into this turn."""
    if mode is None or mode.key == WORKBENCH:
        return False
    return bool(getattr(mode, "use_knowledge_memory", False))


def writes_persona(mode: ChatMode | None) -> bool:
    """Only companion chats write the persona lane. Custom may read, not write."""
    return mode is not None and mode.key == COMPANION


def writes_knowledge(mode: ChatMode | None) -> bool:
    """Only tutor chats write the knowledge lane. Companion may read, not write."""
    return mode is not None and mode.key == TUTOR


def _row_to_fact(row: MemoryItem) -> MemoryFact:
    key = (row.field_key or row.category or "").strip()
    return MemoryFact(
        lane=row.lane,
        field_key=key,
        category=key,
        item_key=row.item_key,
        title=row.title,
        value=row.value,
        pinned=bool(row.pinned),
    )


def _row_to_field(row: MemoryFieldRecord) -> MemoryField:
    return MemoryField(
        lane=row.lane,
        field_key=row.field_key,
        name=row.name,
        description=row.description,
    )


class UserMemoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.items = MemoryItemRepository(session)
        self.fields = MemoryFieldRepository(session)

    async def get_or_create(self, user_id: str) -> UserMemory:
        result = await self.session.execute(
            select(UserMemory).where(UserMemory.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = UserMemory(user_id=user_id, persona_data={}, knowledge_data={})
            self.session.add(row)
            await self.session.flush()
        await self._migrate_if_needed(user_id, row)
        return row

    async def _migrate_if_needed(self, user_id: str, row: UserMemory) -> None:
        for lane, blob, from_blob in (
            (LANE_PERSONA, row.persona_data, facts_from_persona_blob),
            (LANE_KNOWLEDGE, row.knowledge_data, facts_from_knowledge_blob),
        ):
            item_rows = await self.items.list_lane(user_id, lane)
            field_rows = await self.fields.list_lane(user_id, lane)
            facts: list[MemoryFact]
            if not item_rows and blob:
                facts = from_blob(blob)
                await self.items.upsert_lane(user_id, lane, facts)
            else:
                facts = [_row_to_fact(item) for item in item_rows]
                dirty = False
                for item in item_rows:
                    if not (item.field_key or "").strip():
                        item.field_key = item.category
                        dirty = True
                if dirty:
                    await self.session.flush()
                    facts = [_row_to_fact(item) for item in item_rows]
            if facts and not field_rows:
                await self.fields.upsert_lane(
                    user_id, lane, fields_from_facts(facts, lane=lane)
                )

    async def profile_for_lane(self, user_id: str, lane: str) -> MemoryProfile:
        row = await self.get_or_create(user_id)
        item_rows = await self.items.list_lane(user_id, lane)
        field_rows = await self.fields.list_lane(user_id, lane)
        items = [_row_to_fact(item) for item in item_rows]
        fields = [_row_to_field(item) for item in field_rows]
        if items and not fields:
            fields = fields_from_facts(items, lane=lane)
        fields, items = tidy_profile(fields, items, lane=lane)
        dirty = {fact.item_key for fact in items} != {
            row.item_key for row in item_rows
        } or {item.field_key: item.description for item in fields} != {
            row.field_key: row.description for row in field_rows
        }
        if dirty:
            await self.fields.upsert_lane(user_id, lane, fields)
            await self.items.upsert_lane(user_id, lane, items)
        summary = (
            row.persona_summary if lane == LANE_PERSONA else row.knowledge_summary
        ) or ""
        return MemoryProfile(summary=summary, fields=fields, items=items)

    async def facts_for_lane(self, user_id: str, lane: str) -> list[MemoryFact]:
        profile = await self.profile_for_lane(user_id, lane)
        return profile.items

    async def blocks_for_mode(
        self,
        user_id: str,
        mode: ChatMode | None,
        query: str = "",
    ) -> tuple[str, str]:
        persona = knowledge = ""
        if not wants_persona(mode) and not wants_knowledge(mode):
            return persona, knowledge
        if wants_persona(mode):
            persona = await self._render_block(user_id, LANE_PERSONA, query)
        if wants_knowledge(mode):
            knowledge = await self._render_block(user_id, LANE_KNOWLEDGE, query)
        return persona, knowledge

    async def _render_block(self, user_id: str, lane: str, query: str) -> str:
        profile = await self.profile_for_lane(user_id, lane)
        chosen = select_for_prompt(profile.items, query, fields=profile.fields)
        return render_profile(
            lane,
            summary=profile.summary,
            fields=profile.fields,
            items=chosen,
        )

    async def clear(self, user_id: str, *, lane: str) -> UserMemory:
        row = await self.get_or_create(user_id)
        if lane in {LANE_PERSONA, "all"}:
            row.persona_data = {}
            row.persona_summary = ""
            await self.items.delete_lane(user_id, LANE_PERSONA)
            await self.fields.delete_lane(user_id, LANE_PERSONA)
        if lane in {LANE_KNOWLEDGE, "all"}:
            row.knowledge_data = {}
            row.knowledge_summary = ""
            await self.items.delete_lane(user_id, LANE_KNOWLEDGE)
            await self.fields.delete_lane(user_id, LANE_KNOWLEDGE)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def update_from_conversation(
        self,
        *,
        user_id: str,
        conversation_id: str,
        lane: str,
    ) -> bool:
        repo = ConversationRepository(self.session)
        messages = await repo.list_messages(conversation_id)
        turns = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in {"user", "assistant"} and (m.content or "").strip()
        ]
        if len(turns) < 2:
            return False
        text = format_conversation(turns[-20:])
        profile = await self.profile_for_lane(user_id, lane)
        related = select_field_keys(profile.fields, text)
        current = format_extract_context(
            summary=profile.summary,
            fields=profile.fields,
            items=profile.items,
            related_keys=related,
        )
        if lane == LANE_PERSONA:
            system, user_tmpl = PERSONA_EXTRACT_SYSTEM, PERSONA_EXTRACT_USER
        elif lane == LANE_KNOWLEDGE:
            system, user_tmpl = KNOWLEDGE_EXTRACT_SYSTEM, KNOWLEDGE_EXTRACT_USER
        else:
            return False
        try:
            from app.llm.usage import PURPOSE_MEMORY, usage_scope

            with usage_scope(
                purpose=PURPOSE_MEMORY,
                user_id=user_id,
                conversation_id=conversation_id,
                session=self.session,
            ):
                parsed = await structured_complete(
                    [
                        {"role": "system", "content": system},
                        {
                            "role": "user",
                            "content": user_tmpl.format(
                                current=current, conversation_text=text
                            ),
                        },
                    ],
                    ProfileDelta,
                )
            assert isinstance(parsed, ProfileDelta)
            field_ops = [
                FieldOp(
                    op=item.op,
                    key=item.key,
                    name=item.name,
                    description=item.description,
                )
                for item in parsed.fields
                if item.key.strip()
            ]
            raw_items = parsed.items or parsed.facts
            item_ops = [
                MemoryOp(
                    op=item.op,
                    field=item.field or item.category,
                    category=item.field or item.category,
                    key=item.key,
                    title=item.title,
                    value=item.value,
                    pinned=item.pinned,
                )
                for item in raw_items
                if (item.key or item.value or item.op == "retract")
            ]
            new_summary = merge_summary(
                profile.summary, parsed.summary, changed=parsed.summary_changed
            )
            if not field_ops and not item_ops and new_summary == (profile.summary or "").strip():
                return False
            retracted = {
                op.key for op in field_ops if (op.op or "").strip().lower() == "retract"
            }
            fields = apply_field_ops(profile.fields, field_ops, lane=lane)
            existing_items = drop_items_for_fields(profile.items, retracted)
            items = apply_ops(existing_items, item_ops, lane=lane)
            fields, items = tidy_profile(fields, items, lane=lane)
            await self.fields.upsert_lane(user_id, lane, fields)
            await self.items.upsert_lane(
                user_id,
                lane,
                items,
                source_conversation_id=conversation_id,
            )
            row = await self.get_or_create(user_id)
            snapshot = {
                fact.item_key: {
                    "title": fact.title,
                    "value": fact.value,
                    "category": fact.field_key,
                }
                for fact in items
            }
            if lane == LANE_PERSONA:
                row.persona_data = snapshot
                row.persona_summary = new_summary
            else:
                row.knowledge_data = snapshot
                row.knowledge_summary = new_summary
        except Exception:
            logger.exception(
                "user_memory_extract_failed",
                user_id=user_id,
                conversation_id=conversation_id,
                lane=lane,
            )
            return False
        await self.session.commit()
        logger.info(
            "user_memory_updated",
            user_id=user_id,
            lane=lane,
            fields=len(fields),
            facts=len(items),
            field_delta=len(field_ops),
            item_delta=len(item_ops),
        )
        return True


async def refresh_memory_for_conversation(
    session: AsyncSession,
    *,
    user_id: str,
    conversation_id: str,
    mode: ChatMode | None,
    force: bool = False,
) -> list[str]:
    """Update the lanes this mode is allowed to touch. Returns lanes written."""
    repo = ConversationRepository(session)
    count = await repo.count_messages(conversation_id)
    if not force and (count < 6 or count % 6 != 0):
        return []
    svc = UserMemoryService(session)
    written: list[str] = []
    if writes_persona(mode):
        if await svc.update_from_conversation(
            user_id=user_id, conversation_id=conversation_id, lane=LANE_PERSONA
        ):
            written.append(LANE_PERSONA)
    if writes_knowledge(mode):
        if await svc.update_from_conversation(
            user_id=user_id, conversation_id=conversation_id, lane=LANE_KNOWLEDGE
        ):
            written.append(LANE_KNOWLEDGE)
    return written


async def run_memory_refresh_task(
    user_id: str,
    conversation_id: str,
    mode_id: str | None,
    force: bool = False,
) -> None:
    """Background extract using a fresh DB session (after the request commits)."""
    from app.database.session import session_scope

    try:
        async with session_scope() as session:
            mode = None
            if mode_id:
                result = await session.execute(
                    select(ChatMode).where(ChatMode.id == mode_id)
                )
                mode = result.scalar_one_or_none()
            if not writes_persona(mode) and not writes_knowledge(mode):
                return
            await refresh_memory_for_conversation(
                session,
                user_id=user_id,
                conversation_id=conversation_id,
                mode=mode,
                force=force,
            )
    except Exception:
        logger.exception(
            "user_memory_refresh_failed",
            conversation_id=conversation_id,
            user_id=user_id,
        )
