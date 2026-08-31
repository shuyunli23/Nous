"""Data access for structured memory facts."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.memory_item import MemoryItem
from app.memory.facts import MemoryFact


class MemoryItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_lane(self, user_id: str, lane: str) -> list[MemoryItem]:
        stmt = (
            select(MemoryItem)
            .where(MemoryItem.user_id == user_id, MemoryItem.lane == lane)
            .order_by(MemoryItem.pinned.desc(), MemoryItem.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_lane(
        self,
        user_id: str,
        lane: str,
        facts: list[MemoryFact],
        *,
        source_conversation_id: str | None = None,
    ) -> list[MemoryItem]:
        existing = await self.list_lane(user_id, lane)
        by_key = {row.item_key: row for row in existing}
        keep = {fact.item_key for fact in facts}
        for row in existing:
            if row.item_key not in keep:
                await self.session.delete(row)
        rows: list[MemoryItem] = []
        for fact in facts:
            row = by_key.get(fact.item_key)
            if row is None:
                row = MemoryItem(
                    user_id=user_id,
                    lane=lane,
                    category=fact.field_key or fact.category,
                    field_key=fact.field_key or fact.category,
                    item_key=fact.item_key,
                    title=fact.title,
                    value=fact.value,
                    pinned=fact.pinned,
                    source_conversation_id=source_conversation_id,
                )
                self.session.add(row)
            else:
                row.category = fact.field_key or fact.category
                row.field_key = fact.field_key or fact.category
                row.title = fact.title
                row.value = fact.value
                row.pinned = fact.pinned
                if source_conversation_id:
                    row.source_conversation_id = source_conversation_id
            rows.append(row)
        await self.session.flush()
        return rows

    async def delete_lane(self, user_id: str, lane: str) -> None:
        await self.session.execute(
            delete(MemoryItem).where(
                MemoryItem.user_id == user_id, MemoryItem.lane == lane
            )
        )
        await self.session.flush()
