"""Data access for open-vocabulary memory fields."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.memory_field import MemoryFieldRecord
from app.memory.facts import MemoryField


class MemoryFieldRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_lane(self, user_id: str, lane: str) -> list[MemoryFieldRecord]:
        stmt = (
            select(MemoryFieldRecord)
            .where(MemoryFieldRecord.user_id == user_id, MemoryFieldRecord.lane == lane)
            .order_by(MemoryFieldRecord.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_lane(
        self, user_id: str, lane: str, fields: list[MemoryField]
    ) -> list[MemoryFieldRecord]:
        existing = await self.list_lane(user_id, lane)
        by_key = {row.field_key: row for row in existing}
        keep = {item.field_key for item in fields}
        for row in existing:
            if row.field_key not in keep:
                await self.session.delete(row)
        rows: list[MemoryFieldRecord] = []
        for item in fields:
            row = by_key.get(item.field_key)
            if row is None:
                row = MemoryFieldRecord(
                    user_id=user_id,
                    lane=lane,
                    field_key=item.field_key,
                    name=item.name,
                    description=item.description,
                )
                self.session.add(row)
            else:
                row.name = item.name
                row.description = item.description
            rows.append(row)
        await self.session.flush()
        return rows

    async def delete_lane(self, user_id: str, lane: str) -> None:
        await self.session.execute(
            delete(MemoryFieldRecord).where(
                MemoryFieldRecord.user_id == user_id,
                MemoryFieldRecord.lane == lane,
            )
        )
        await self.session.flush()
