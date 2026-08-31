"""Dynamic memory fields + per-field items. Open vocabulary, delta writes, catalog recall."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from app.llm.embeddings import _tokenize

LANE_PERSONA = "persona"
LANE_KNOWLEDGE = "knowledge"

# Only used when migrating old blobs / labeling leftover keys.
LEGACY_FIELD_NAMES = {
    "identity": "身份",
    "habit": "习惯",
    "preference": "偏好",
    "relationship": "关系",
    "mood": "心情",
    "speaking": "说话",
    "other": "其他",
    "topic": "已经会",
    "gap": "还薄弱",
    "learning_pref": "讲解偏好",
    "language": "用语",
}

_SLUG_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff._-]+")

MAX_ITEMS_PER_LANE = 400
MAX_FIELDS = 120
MAX_EXPAND_FIELDS = 8
MAX_ITEMS_PER_FIELD = 16
MAX_SUMMARY = 800

# Process talk and "unknown" are not facts. Field names like 关系确认 match first;
# values about the archive or the agent's guessing policy match second.
_EPHEMERAL_FIELD = re.compile(r"(确认|了解程度)")
_EPHEMERAL_VALUE = re.compile(
    r"(尚未提供|还没有提供|还没告诉|档案中没有|档案里没有|不要猜测|"
    r"不作假设|不作揣测|未知即未知|你真的不|没有具体信息)"
)

_GENERIC_FIELD_KEYS = frozenset({"other", "其他", "misc", "field", "item"})
_GENERIC_TITLES = frozenset({"", "other", "其他", "item", "misc", "条目", "field"})
_VALUE_FIELD_RULES = (
    (re.compile(r"小名|英文名|称呼|叫我|名叫"), "identity.names", "称呼"),
    (re.compile(r"工程师|职业|软研|算法工程师"), "work", "工作"),
    (re.compile(r"羽毛球|乒乓球|跑步|运动|体育|篮球"), "hobby", "爱好"),
    (re.compile(r"搬家|迁居|从贵州|到广州"), "life.move", "迁居"),
    (re.compile(r"自卑|多维|参与生活"), "self.view", "自我"),
)


@dataclass
class MemoryField:
    lane: str
    field_key: str
    name: str
    description: str = ""


@dataclass
class MemoryFact:
    """One specific item under a field. ``category`` is an alias of ``field_key``."""

    lane: str
    item_key: str
    title: str
    value: str
    field_key: str = ""
    category: str = ""
    pinned: bool = False

    def __post_init__(self) -> None:
        key = (self.field_key or self.category or "").strip()
        self.field_key = key
        self.category = key


@dataclass
class MemoryOp:
    op: str  # add | update | retract
    category: str = ""
    key: str = ""
    title: str = ""
    value: str = ""
    pinned: bool = False
    field: str = ""

    def resolved_field(self) -> str:
        return (self.field or self.category or "").strip()


@dataclass
class FieldOp:
    op: str  # add | update | retract
    key: str
    name: str = ""
    description: str = ""


@dataclass
class MemoryProfile:
    summary: str = ""
    fields: list[MemoryField] = field(default_factory=list)
    items: list[MemoryFact] = field(default_factory=list)


def _slug(text: str) -> str:
    return _SLUG_RE.sub("", (text or "").strip().lower().replace(" ", ""))[:48]


def is_ephemeral_memory(
    *,
    key: str = "",
    name: str = "",
    title: str = "",
    value: str = "",
) -> bool:
    """True for confirmation / 'I don't know' / archive-about-itself rows."""
    heading = f"{key} {name} {title}"
    if _EPHEMERAL_FIELD.search(heading):
        return True
    body = f"{title} {value}"
    return bool(_EPHEMERAL_VALUE.search(body))


def prune_ephemeral(
    fields: Sequence[MemoryField],
    items: Sequence[MemoryFact],
) -> tuple[list[MemoryField], list[MemoryFact]]:
    """Drop meta rows so they cannot keep accumulating across captures."""
    kept_items = [
        fact
        for fact in items
        if not is_ephemeral_memory(
            key=fact.item_key, title=fact.title, value=fact.value
        )
    ]
    occupied = {fact.field_key for fact in kept_items}
    kept_fields: list[MemoryField] = []
    for item in fields:
        if is_ephemeral_memory(
            key=item.field_key, name=item.name, value=item.description
        ):
            continue
        if item.field_key not in occupied:
            continue
        kept_fields.append(item)
    return kept_fields, kept_items


def _is_generic_field(key: str, name: str = "") -> bool:
    return normalize_field_key(key) in _GENERIC_FIELD_KEYS or (name or "").strip() in {
        "其他",
        "Other",
    }


def _is_generic_title(title: str, field_key: str = "", field_name: str = "") -> bool:
    text = (title or "").strip()
    if text.lower() in _GENERIC_TITLES or text in _GENERIC_TITLES:
        return True
    return bool(text) and text in {field_key, field_name}


def _compact(text: str) -> str:
    return re.sub(r"[\s，。、“”\"'：:；;！!？?、]+", "", text or "").lower()


def similar_values(left: str, right: str) -> bool:
    """Same fact written twice (e.g. 对象现状 vs 工作调动)."""
    a, b = _compact(left), _compact(right)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 8 and shorter in longer:
        return True
    query = left if len(a) <= len(b) else right
    blob = right if len(a) <= len(b) else left
    return score_text(query, blob) >= 0.7 and score_text(blob, query) >= 0.45


def _guess_field(title: str, value: str) -> tuple[str, str] | None:
    blob = f"{title} {value}"
    for pattern, key, name in _VALUE_FIELD_RULES:
        if pattern.search(blob):
            return key, name
    return None


def rehome_generic_items(
    items: Sequence[MemoryFact], *, lane: str
) -> list[MemoryFact]:
    """Pull named facts out of the 其他 junk drawer."""
    moved: list[MemoryFact] = []
    for fact in items:
        if not _is_generic_field(fact.field_key):
            moved.append(fact)
            continue
        title = (fact.title or "").strip()
        if not _is_generic_title(title, fact.field_key):
            field_key = normalize_field_key(title)
            item_key = normalize_item_key(field_key, fact.item_key.split(".")[-1] or title)
            moved.append(
                MemoryFact(
                    lane=lane,
                    field_key=field_key,
                    category=field_key,
                    item_key=item_key,
                    title=title[:80],
                    value=fact.value,
                    pinned=fact.pinned,
                )
            )
            continue
        guessed = _guess_field(title, fact.value)
        if guessed is None:
            moved.append(fact)
            continue
        field_key, name = guessed
        item_key = normalize_item_key(field_key, fact.item_key.split(".")[-1] or name)
        moved.append(
            MemoryFact(
                lane=lane,
                field_key=field_key,
                category=field_key,
                item_key=item_key,
                title=name if _is_generic_title(title, fact.field_key) else title,
                value=fact.value,
                pinned=fact.pinned,
            )
        )
    return moved


def dedupe_similar_items(items: Sequence[MemoryFact]) -> list[MemoryFact]:
    """Keep the richer row when two items in a field say the same thing."""
    grouped: dict[str, list[MemoryFact]] = {}
    for fact in items:
        grouped.setdefault(fact.field_key, []).append(fact)
    kept: list[MemoryFact] = []
    for bucket in grouped.values():
        winners: list[MemoryFact] = []
        for fact in sorted(bucket, key=lambda item: (-len(item.value), item.item_key)):
            if any(similar_values(fact.value, other.value) for other in winners):
                continue
            winners.append(fact)
        kept.extend(winners)
    return kept


def _trim_copied_descriptions(
    fields: Sequence[MemoryField], items: Sequence[MemoryFact]
) -> list[MemoryField]:
    values: dict[str, str] = {}
    for fact in items:
        values[fact.field_key] = (values.get(fact.field_key, "") + " " + fact.value).strip()
    trimmed: list[MemoryField] = []
    for item in fields:
        desc = (item.description or "").strip()
        blob = values.get(item.field_key, "")
        if desc and blob and similar_values(desc, blob):
            item = MemoryField(
                lane=item.lane,
                field_key=item.field_key,
                name=item.name,
                description="",
            )
        trimmed.append(item)
    return trimmed


def tidy_profile(
    fields: Sequence[MemoryField],
    items: Sequence[MemoryFact],
    *,
    lane: str,
) -> tuple[list[MemoryField], list[MemoryFact]]:
    fields, items = prune_ephemeral(fields, items)
    items = rehome_generic_items(items, lane=lane)
    items = dedupe_similar_items(items)
    fields = ensure_fields_for_items(fields, items, lane=lane)
    occupied = {fact.field_key for fact in items}
    fields = [item for item in fields if item.field_key in occupied]
    fields = _trim_copied_descriptions(fields, items)
    return fields, items


def normalize_field_key(key: str) -> str:
    raw = _slug(key) or "field"
    return raw[:80]


def normalize_item_key(category: str, key: str) -> str:
    field_key = normalize_field_key(category)
    raw = _slug(key) or "item"
    if raw.startswith(f"{field_key}."):
        return raw[:80]
    return f"{field_key}.{raw}"[:80]


def apply_field_ops(
    existing: Sequence[MemoryField],
    ops: Sequence[FieldOp],
    *,
    lane: str,
) -> list[MemoryField]:
    """Only the listed fields are touched. Everyone else stays."""
    by_key: dict[str, MemoryField] = {item.field_key: item for item in existing}
    for raw in ops:
        field_key = normalize_field_key(raw.key)
        action = (raw.op or "add").strip().lower()
        if action == "retract":
            by_key.pop(field_key, None)
            continue
        name = (raw.name or "").strip()
        description = (raw.description or "").strip()
        if is_ephemeral_memory(key=field_key, name=name, value=description):
            continue
        current = by_key.get(field_key)
        if current is None:
            by_key[field_key] = MemoryField(
                lane=lane,
                field_key=field_key,
                name=(name or field_key)[:80],
                description=description[:400],
            )
            continue
        if name:
            current.name = name[:80]
        if description:
            current.description = description[:400]
    fields = list(by_key.values())
    return fields[:MAX_FIELDS]


def ensure_fields_for_items(
    fields: Sequence[MemoryField],
    items: Sequence[MemoryFact],
    *,
    lane: str,
) -> list[MemoryField]:
    """If an item lands on a new field_key, add a catalog row so recall can see it."""
    by_key: dict[str, MemoryField] = {item.field_key: item for item in fields}
    for fact in items:
        key = fact.field_key
        if not key or key in by_key:
            continue
        by_key[key] = MemoryField(
            lane=lane,
            field_key=key,
            name=(fact.title or key)[:80],
            description="",
        )
    return list(by_key.values())[:MAX_FIELDS]


def drop_items_for_fields(
    items: Sequence[MemoryFact], field_keys: Iterable[str]
) -> list[MemoryFact]:
    dropped = {normalize_field_key(key) for key in field_keys if key}
    if not dropped:
        return list(items)
    return [fact for fact in items if fact.field_key not in dropped]


def apply_ops(
    existing: Sequence[MemoryFact],
    ops: Sequence[MemoryOp],
    *,
    lane: str,
) -> list[MemoryFact]:
    """Merge a delta of items. Unmentioned keys stay as they are."""
    by_key: dict[str, MemoryFact] = {fact.item_key: fact for fact in existing}
    for raw in ops:
        title = (raw.title or "").strip()
        if _is_generic_title(title):
            title = ""
        field_raw = raw.resolved_field()
        if _is_generic_field(field_raw) and title:
            field_raw = title
        elif not field_raw:
            field_raw = title or "other"
        field_key = normalize_field_key(field_raw)
        item_key = normalize_item_key(field_key, raw.key)
        action = (raw.op or "add").strip().lower()
        if action == "retract":
            by_key.pop(item_key, None)
            continue
        value = (raw.value or "").strip()
        if not value:
            continue
        if is_ephemeral_memory(
            key=item_key, name=title, title=title, value=value
        ):
            continue
        current = by_key.get(item_key)
        if current is None:
            if any(
                fact.field_key == field_key and similar_values(value, fact.value)
                for fact in by_key.values()
            ):
                continue
            by_key[item_key] = MemoryFact(
                lane=lane,
                field_key=field_key,
                item_key=item_key,
                title=title[:80],
                value=value[:800],
            )
            continue
        current.value = value[:800]
        if title:
            current.title = title[:80]
        current.field_key = field_key
        current.category = field_key
    facts = list(by_key.values())
    if len(facts) <= MAX_ITEMS_PER_LANE:
        return facts
    return facts[:MAX_ITEMS_PER_LANE]


def fields_from_facts(facts: Sequence[MemoryFact], *, lane: str) -> list[MemoryField]:
    grouped: dict[str, list[MemoryFact]] = {}
    for fact in facts:
        grouped.setdefault(fact.field_key or "other", []).append(fact)
    result: list[MemoryField] = []
    for key, items in grouped.items():
        name = LEGACY_FIELD_NAMES.get(key) or (items[0].title if len(items) == 1 else key)
        bits = []
        for item in items[:4]:
            if item.title and item.title not in {item.value, name}:
                bits.append(f"{item.title}：{item.value}")
            elif item.value:
                bits.append(item.value)
        result.append(
            MemoryField(
                lane=lane,
                field_key=key,
                name=str(name)[:80],
                description="；".join(bits)[:400],
            )
        )
    return result


def score_text(query: str, blob: str) -> float:
    query_tokens = set(_tokenize(query or ""))
    tokens = set(_tokenize(blob or ""))
    if not query_tokens or not tokens:
        return 0.0
    return len(query_tokens & tokens) / max(len(query_tokens), 1)


def select_field_keys(
    fields: Sequence[MemoryField],
    query: str,
    *,
    limit: int = MAX_EXPAND_FIELDS,
) -> list[str]:
    """Pick fields whose name/description overlap this turn. Catalog stays separate."""
    scored: list[tuple[float, str]] = []
    for item in fields:
        blob = f"{item.field_key} {item.name} {item.description}"
        score = score_text(query, blob)
        if score > 0:
            scored.append((score, item.field_key))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [key for _score, key in scored[:limit]]


def select_for_prompt(
    facts: Sequence[MemoryFact],
    query: str,
    fields: Sequence[MemoryField] | None = None,
) -> list[MemoryFact]:
    """Expand specific items only for fields that match the query."""
    if not facts:
        return []
    lane = facts[0].lane
    catalog = list(fields) if fields is not None else fields_from_facts(facts, lane=lane)
    keys = set(select_field_keys(catalog, query))
    if not keys:
        return []
    chosen = [fact for fact in facts if fact.field_key in keys]
    by_field: dict[str, list[MemoryFact]] = {}
    for fact in chosen:
        bucket = by_field.setdefault(fact.field_key, [])
        if len(bucket) < MAX_ITEMS_PER_FIELD:
            bucket.append(fact)
    return [item for key in keys for item in by_field.get(key, [])]


def render_profile(
    lane: str,
    *,
    summary: str = "",
    fields: Sequence[MemoryField] = (),
    items: Sequence[MemoryFact] = (),
) -> str:
    heading = "相处档案" if lane == LANE_PERSONA else "知识基础"
    lines = [f"## 关于我（{heading}）"]
    summary_text = (summary or "").strip()
    if summary_text:
        lines.append("### 概要")
        lines.append(summary_text[:MAX_SUMMARY])
    if fields:
        lines.append("### 字段目录")
        lines.append("下面是已有字段和一句描述。具体条目只在「本轮展开」里，不要当作已经读过全部细节。")
        for item in fields:
            desc = (item.description or "").strip()
            label = item.name or item.field_key
            if desc:
                lines.append(f"- {label}（{item.field_key}）：{desc}")
            else:
                lines.append(f"- {label}（{item.field_key}）")
    if items:
        lines.append("### 本轮展开的具体条目")
        grouped: dict[str, list[MemoryFact]] = {}
        for fact in items:
            grouped.setdefault(fact.field_key, []).append(fact)
        field_names = {item.field_key: item.name for item in fields}
        for field_key, bucket in grouped.items():
            label = field_names.get(field_key) or LEGACY_FIELD_NAMES.get(field_key) or field_key
            lines.append(f"#### {label}")
            for fact in bucket:
                if not fact.value:
                    continue
                if fact.title and fact.title not in {fact.value, label}:
                    lines.append(f"- {fact.title}：{fact.value}")
                else:
                    lines.append(f"- {fact.value}")
    if len(lines) == 1:
        return ""
    if lane == LANE_PERSONA:
        lines.append("字段可按需要新增。没展开的细节不要编。不要把这些写进知识库。")
    else:
        lines.append("按已展开的基础讲；没展开的主题不要假装已经了解。不要写入情感或人际关系。")
    return "\n".join(lines)


def render_facts(lane: str, facts: Sequence[MemoryFact], *, partial: bool = False) -> str:
    fields = fields_from_facts(facts, lane=lane)
    items = facts if not partial else facts
    return render_profile(lane, fields=fields, items=items)


def merge_summary(previous: str, incoming: str, *, changed: bool) -> str:
    text = (incoming or "").strip()
    if not changed and not text:
        return (previous or "").strip()[:MAX_SUMMARY]
    if not text:
        return (previous or "").strip()[:MAX_SUMMARY]
    return text[:MAX_SUMMARY]


def facts_from_persona_blob(data: dict | None) -> list[MemoryFact]:
    raw = data or {}
    if raw.get("habits") is None and raw.get("people") is None and any(
        isinstance(v, dict) and "category" in v for v in raw.values()
    ):
        ops = []
        for key, payload in raw.items():
            if not isinstance(payload, dict):
                continue
            ops.append(
                MemoryOp(
                    op="add",
                    category=str(payload.get("category") or "other"),
                    key=str(key),
                    title=str(payload.get("title") or ""),
                    value=str(payload.get("value") or ""),
                )
            )
        return apply_ops([], ops, lane=LANE_PERSONA)
    ops: list[MemoryOp] = []
    for habit in raw.get("habits") or []:
        if isinstance(habit, str) and habit.strip():
            ops.append(MemoryOp(op="add", category="habit", key=habit[:24], title="", value=habit))
    for person in raw.get("people") or []:
        if not isinstance(person, dict):
            continue
        name = str(person.get("name") or "").strip()
        if not name:
            continue
        note = str(person.get("note") or "").strip()
        ops.append(
            MemoryOp(
                op="add",
                category="relationship",
                field="relationship",
                key=name,
                title=name,
                value=note or name,
            )
        )
    mood = str(raw.get("mood_recent") or "").strip()
    if mood:
        ops.append(MemoryOp(op="add", category="mood", key="recent", title="近期心情", value=mood))
    speaking = str(raw.get("speaking_prefs") or "").strip()
    if speaking:
        ops.append(
            MemoryOp(op="add", category="speaking", key="style", title="说话偏好", value=speaking)
        )
    for note in raw.get("notes") or []:
        if isinstance(note, str) and note.strip():
            ops.append(MemoryOp(op="add", category="other", key=note[:24], title="", value=note))
    return apply_ops([], ops, lane=LANE_PERSONA)


def facts_from_knowledge_blob(data: dict | None) -> list[MemoryFact]:
    raw = data or {}
    ops: list[MemoryOp] = []
    for item in raw.get("known") or []:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        if not topic:
            continue
        level = str(item.get("level") or "beginner").strip()
        note = str(item.get("note") or "").strip()
        value = level if not note else f"{level}；{note}"
        ops.append(MemoryOp(op="add", category="topic", key=topic, title=topic, value=value))
    for gap in raw.get("gaps") or []:
        if isinstance(gap, str) and gap.strip():
            ops.append(MemoryOp(op="add", category="gap", key=gap[:24], title="", value=gap))
    prefs = str(raw.get("learning_prefs") or "").strip()
    if prefs:
        ops.append(
            MemoryOp(op="add", category="learning_pref", key="style", title="讲解偏好", value=prefs)
        )
    for lang in raw.get("languages") or []:
        if isinstance(lang, str) and lang.strip():
            ops.append(MemoryOp(op="add", category="language", key=lang, title="用语", value=lang))
    return apply_ops([], ops, lane=LANE_KNOWLEDGE)


def format_extract_context(
    *,
    summary: str,
    fields: Sequence[MemoryField],
    items: Sequence[MemoryFact],
    related_keys: Iterable[str],
) -> str:
    lines = [f"概要：{(summary or '').strip() or '（还没有）'}"]
    lines.append("字段目录（只改这次涉及到的；可新增字段）：")
    if not fields:
        lines.append("（还没有字段）")
    for item in fields:
        desc = (item.description or "").strip()
        extra = f"：{desc}" if desc else ""
        lines.append(f"- {item.field_key} | {item.name}{extra}")
    related = {normalize_field_key(key) for key in related_keys if key}
    lines.append("已有具体条目（不要再拆新字段重复写；确认/不知道类请 retract）：")
    if not items:
        lines.append("（还没有具体条目）")
    for fact in items:
        mark = " ←这轮可能相关" if fact.field_key in related else ""
        lines.append(f"- {fact.item_key} | {fact.title} | {fact.value}{mark}")
    return "\n".join(lines)
