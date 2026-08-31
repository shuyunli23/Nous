"""GET /api/v1/memory — two-lane structured long-term facts (not NexusMind)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.memory.facts import LANE_KNOWLEDGE, LANE_PERSONA, render_profile
from app.schemas.memory import (
    MemoryClearRequest,
    MemoryFieldRead,
    MemoryItemRead,
    MemoryLaneRead,
    UserMemoryRead,
)
from app.services.memory_service import UserMemoryService

router = APIRouter(prefix="/memory", tags=["memory"])


def _item_read(fact, item_id: str) -> MemoryItemRead:
    return MemoryItemRead(
        id=item_id,
        field_key=fact.field_key,
        category=fact.field_key or fact.category,
        item_key=fact.item_key,
        title=fact.title,
        value=fact.value,
        pinned=fact.pinned,
    )


async def _lane(svc: UserMemoryService, user_id: str, lane: str) -> MemoryLaneRead:
    profile = await svc.profile_for_lane(user_id, lane)
    rows = await svc.items.list_lane(user_id, lane)
    by_key = {row.item_key: row.id for row in rows}
    items = [_item_read(fact, by_key.get(fact.item_key, "")) for fact in profile.items]
    grouped_items: dict[str, list[MemoryItemRead]] = {}
    for item in items:
        grouped_items.setdefault(item.field_key or item.category, []).append(item)
    fields = [
        MemoryFieldRead(
            field_key=field.field_key,
            name=field.name,
            description=field.description,
            items=grouped_items.get(field.field_key, []),
        )
        for field in profile.fields
    ]
    leftover_keys = set(grouped_items) - {field.field_key for field in fields}
    for key in leftover_keys:
        bucket = grouped_items[key]
        fields.append(
            MemoryFieldRead(
                field_key=key,
                name=bucket[0].title or key if bucket else key,
                description="",
                items=bucket,
            )
        )
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(item.field_key or item.category, []).append(
            {"title": item.title, "value": item.value, "key": item.item_key}
        )
    empty = not profile.summary.strip() and not fields and not items
    return MemoryLaneRead(
        empty=empty,
        rendered=render_profile(
            lane,
            summary=profile.summary,
            fields=profile.fields,
            items=profile.items,
        ),
        summary=profile.summary,
        fields=fields,
        items=items,
        data=grouped,
    )


@router.get("", response_model=UserMemoryRead, summary="Read persona and knowledge profiles")
async def get_memory(session: SessionDep, user: CurrentUser) -> UserMemoryRead:
    svc = UserMemoryService(session)
    await svc.get_or_create(user.id)
    return UserMemoryRead(
        persona=await _lane(svc, user.id, LANE_PERSONA),
        knowledge=await _lane(svc, user.id, LANE_KNOWLEDGE),
    )


@router.post("", response_model=UserMemoryRead, summary="Clear one memory lane or both")
async def clear_memory(
    payload: MemoryClearRequest,
    session: SessionDep,
    user: CurrentUser,
) -> UserMemoryRead:
    svc = UserMemoryService(session)
    await svc.clear(user.id, lane=payload.lane)
    return UserMemoryRead(
        persona=await _lane(svc, user.id, LANE_PERSONA),
        knowledge=await _lane(svc, user.id, LANE_KNOWLEDGE),
    )
