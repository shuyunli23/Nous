"""Two-lane memory: knowledge for tutor, persona for companion (no LLM)."""

from __future__ import annotations

from types import SimpleNamespace

from app.chat_modes.catalog import (
    COMPANION,
    KNOWLEDGE_PLACEHOLDER,
    PERSONA_PLACEHOLDER,
    TUTOR,
    WORKBENCH,
    resolve_system_prompt,
)
from app.memory.facts import (
    FieldOp,
    MemoryFact,
    MemoryField,
    MemoryOp,
    apply_field_ops,
    apply_ops,
    format_extract_context,
    is_ephemeral_memory,
    prune_ephemeral,
    render_profile,
    select_for_prompt,
    tidy_profile,
)
from app.services.memory_service import (
    render_knowledge,
    render_persona,
    wants_knowledge,
    wants_persona,
    writes_knowledge,
    writes_persona,
)


def _mode(**kwargs: object) -> SimpleNamespace:
    data = {
        "key": "c_custom",
        "use_long_term_memory": False,
        "use_knowledge_memory": False,
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_lanes_never_cross_on_builtins() -> None:
    assert wants_persona(_mode(key=COMPANION)) is True
    assert wants_knowledge(_mode(key=COMPANION, use_knowledge_memory=True)) is True
    assert wants_knowledge(_mode(key=COMPANION, use_knowledge_memory=False)) is False
    assert wants_persona(_mode(key=TUTOR, use_long_term_memory=True)) is False
    assert wants_knowledge(_mode(key=TUTOR, use_knowledge_memory=True)) is True
    assert wants_knowledge(_mode(key=TUTOR, use_knowledge_memory=False)) is False
    assert writes_knowledge(_mode(key=TUTOR, use_knowledge_memory=True)) is True
    assert writes_knowledge(_mode(key=TUTOR, use_knowledge_memory=False)) is True
    assert writes_knowledge(_mode(key=COMPANION, use_knowledge_memory=True)) is False
    assert writes_persona(_mode(key=COMPANION)) is True
    assert writes_persona(_mode(key=TUTOR, use_long_term_memory=True)) is False
    assert writes_persona(_mode(use_long_term_memory=True, use_knowledge_memory=True)) is False
    assert writes_knowledge(_mode(use_long_term_memory=True, use_knowledge_memory=True)) is False
    assert wants_persona(_mode(key=WORKBENCH, use_long_term_memory=True)) is False
    assert wants_knowledge(_mode(key=WORKBENCH, use_knowledge_memory=True)) is False


def test_custom_mode_honors_both_toggles() -> None:
    both = _mode(use_long_term_memory=True, use_knowledge_memory=True)
    assert wants_persona(both) is True
    assert wants_knowledge(both) is True
    assert writes_persona(both) is False
    assert writes_knowledge(both) is False


def test_render_knowledge_has_no_social_life() -> None:
    text = render_knowledge(
        {
            "known": [
                {"topic": "线性代数", "level": "intermediate", "note": "会矩阵乘法"}
            ],
            "gaps": ["特征值"],
            "learning_prefs": "先例子再公式",
            "languages": ["中文"],
        }
    )
    assert "线性代数" in text
    assert "知识基础" in text
    assert "心情" not in text
    assert "在意的人" not in text
    assert "恋爱" not in text
    assert "小李" not in text


def test_render_persona_has_no_curriculum() -> None:
    text = render_persona(
        {
            "habits": ["晚上才有空"],
            "people": [{"name": "小李", "note": "同事"}],
            "mood_recent": "有点累",
            "speaking_prefs": "短句",
            "notes": [],
        }
    )
    assert "相处档案" in text
    assert "小李" in text
    assert "已经会" not in text
    assert "知识点" not in text
    assert "线性代数" not in text


def test_empty_renders_are_blank() -> None:
    assert render_persona({}) == ""
    assert render_knowledge({}) == ""


def test_tutor_knowledge_inject_uses_profile_not_persona() -> None:
    prompt = resolve_system_prompt(
        key=TUTOR,
        use_knowledge_memory=True,
        knowledge_block=render_knowledge(
            {"known": [{"topic": "Python", "level": "advanced", "note": ""}]}
        ),
    )
    assert "Python" in prompt
    assert "知识基础" in prompt
    assert "相处档案" not in prompt
    assert "在意的人" not in prompt
    assert PERSONA_PLACEHOLDER not in prompt


def test_tutor_empty_knowledge_uses_placeholder() -> None:
    prompt = resolve_system_prompt(key=TUTOR, use_knowledge_memory=True)
    assert KNOWLEDGE_PLACEHOLDER in prompt
    assert "情感" in prompt or "人际关系" in prompt
    assert PERSONA_PLACEHOLDER not in prompt


def test_companion_filled_persona_skips_knowledge() -> None:
    prompt = resolve_system_prompt(
        key=COMPANION,
        use_long_term_memory=True,
        persona_block=render_persona(
            {"habits": ["早起"], "people": [], "mood_recent": "还行"}
        ),
    )
    assert "早起" in prompt
    assert "相处档案" in prompt
    assert "知识点清单" not in prompt
    assert "已经会" not in prompt
    assert KNOWLEDGE_PLACEHOLDER not in prompt


def test_companion_can_inject_knowledge_with_persona() -> None:
    companion = _mode(key=COMPANION, use_knowledge_memory=True)
    assert wants_knowledge(companion) is True
    assert writes_knowledge(companion) is False
    prompt = resolve_system_prompt(
        key=COMPANION,
        use_long_term_memory=True,
        use_knowledge_memory=True,
        persona_block=render_persona({"habits": ["晚睡"], "mood_recent": "还行"}),
        knowledge_block=render_knowledge(
            {"known": [{"topic": "Python", "level": "advanced", "note": ""}]}
        ),
    )
    assert "晚睡" in prompt
    assert "Python" in prompt
    assert "相处档案" in prompt
    assert "知识基础" in prompt


def test_address_preference_does_not_drop_surname() -> None:
    existing = [
        MemoryFact(
            lane="persona",
            category="identity",
            item_key="identity.surname",
            title="姓氏",
            value="李",
            pinned=True,
        ),
        MemoryFact(
            lane="persona",
            category="identity",
            item_key="identity.given_name",
            title="名",
            value="书云",
            pinned=True,
        ),
    ]
    merged = apply_ops(
        existing,
        [
            MemoryOp(
                op="add",
                category="preference",
                key="address_as",
                title="希望怎么称呼",
                value="请叫书云，不要带姓",
            )
        ],
        lane="persona",
    )
    values = {fact.item_key: fact.value for fact in merged}
    assert values["identity.surname"] == "李"
    assert values["identity.given_name"] == "书云"
    assert "书云" in values["preference.address_as"]
    assert "不要带姓" in values["preference.address_as"]


def test_omitted_keys_stay_when_delta_updates_one_field() -> None:
    existing = [
        MemoryFact(
            lane="persona",
            category="habit",
            item_key="habit.night",
            title="",
            value="晚上才有空",
        ),
        MemoryFact(
            lane="persona",
            category="mood",
            item_key="mood.recent",
            title="近期心情",
            value="有点累",
        ),
    ]
    merged = apply_ops(
        existing,
        [MemoryOp(op="update", category="mood", key="recent", title="近期心情", value="好多了")],
        lane="persona",
    )
    values = {fact.item_key: fact.value for fact in merged}
    assert values["habit.night"] == "晚上才有空"
    assert values["mood.recent"] == "好多了"


def test_inject_shows_catalog_and_expands_only_related_fields() -> None:
    fields = [
        MemoryField(lane="persona", field_key="identity", name="身份", description="姓与名"),
        MemoryField(lane="persona", field_key="habit", name="习惯", description="作息"),
        MemoryField(
            lane="persona",
            field_key="relationship.xiaoli",
            name="小李",
            description="同事",
        ),
    ]
    facts = [
        MemoryFact(
            lane="persona",
            field_key="identity",
            item_key="identity.surname",
            title="姓氏",
            value="李",
            pinned=True,
        ),
        MemoryFact(
            lane="persona",
            field_key="habit",
            item_key="habit.night",
            title="",
            value="晚上才有空",
        ),
        MemoryFact(
            lane="persona",
            field_key="relationship.xiaoli",
            item_key="relationship.xiaoli.job",
            title="工作",
            value="同事，最近在换工作",
        ),
    ]
    chosen = select_for_prompt(facts, "小李最近怎么样", fields=fields)
    keys = {fact.item_key for fact in chosen}
    assert "relationship.xiaoli.job" in keys
    assert "habit.night" not in keys
    assert "identity.surname" not in keys
    text = render_profile(
        "persona",
        summary="李书云，身边有同事小李",
        fields=fields,
        items=chosen,
    )
    assert "字段目录" in text
    assert "身份" in text
    assert "习惯" in text
    assert "本轮展开" in text
    assert "最近在换工作" in text
    assert "晚上才有空" not in text


def test_open_field_can_be_added_without_walking_others() -> None:
    fields = [
        MemoryField(lane="persona", field_key="identity", name="身份", description="姓李"),
        MemoryField(lane="persona", field_key="habit", name="习惯", description="晚上才有空"),
    ]
    items = [
        MemoryFact(
            lane="persona",
            field_key="identity",
            item_key="identity.surname",
            title="姓氏",
            value="李",
        ),
        MemoryFact(
            lane="persona",
            field_key="habit",
            item_key="habit.night",
            title="",
            value="晚上才有空",
        ),
    ]
    new_fields = apply_field_ops(
        fields,
        [
            FieldOp(
                op="add",
                key="emotion.family",
                name="对家人的情感",
                description="最近有点牵挂",
            )
        ],
        lane="persona",
    )
    new_items = apply_ops(
        items,
        [
            MemoryOp(
                op="add",
                field="emotion.family",
                key="worry",
                title="牵挂",
                value="担心母亲的身体",
            )
        ],
        lane="persona",
    )
    by_field = {item.field_key: item for item in new_fields}
    assert "emotion.family" in by_field
    assert by_field["identity"].description == "姓李"
    assert by_field["habit"].description == "晚上才有空"
    values = {fact.item_key: fact.value for fact in new_items}
    assert values["identity.surname"] == "李"
    assert values["habit.night"] == "晚上才有空"
    assert "母亲" in values["emotion.family.worry"]


def test_field_delta_does_not_rewrite_unrelated_fields() -> None:
    fields = [
        MemoryField(lane="persona", field_key="identity", name="身份", description="姓李"),
        MemoryField(lane="persona", field_key="habit", name="习惯", description="晚上才有空"),
    ]
    updated = apply_field_ops(
        fields,
        [FieldOp(op="update", key="habit", description="周末也晚睡")],
        lane="persona",
    )
    by_field = {item.field_key: item for item in updated}
    assert by_field["identity"].name == "身份"
    assert by_field["identity"].description == "姓李"
    assert "晚睡" in by_field["habit"].description


def test_knowledge_open_field_update_keeps_siblings() -> None:
    fields = [
        MemoryField(
            lane="knowledge",
            field_key="topic.python",
            name="Python",
            description="已经比较熟",
        ),
        MemoryField(
            lane="knowledge",
            field_key="topic.linear_algebra",
            name="线性代数",
            description="刚开始",
        ),
    ]
    existing = [
        MemoryFact(
            lane="knowledge",
            field_key="topic.python",
            item_key="topic.python.level",
            title="程度",
            value="advanced",
        ),
        MemoryFact(
            lane="knowledge",
            field_key="topic.linear_algebra",
            item_key="topic.linear_algebra.level",
            title="程度",
            value="beginner",
        ),
    ]
    new_fields = apply_field_ops(
        fields,
        [
            FieldOp(
                op="update",
                key="topic.linear_algebra",
                description="中等；会矩阵乘法",
            )
        ],
        lane="knowledge",
    )
    merged = apply_ops(
        existing,
        [
            MemoryOp(
                op="update",
                field="topic.linear_algebra",
                key="level",
                title="程度",
                value="intermediate；会矩阵乘法",
            )
        ],
        lane="knowledge",
    )
    by_field = {item.field_key: item for item in new_fields}
    assert by_field["topic.python"].description == "已经比较熟"
    assert "矩阵乘法" in by_field["topic.linear_algebra"].description
    values = {fact.item_key: fact.value for fact in merged}
    chosen = select_for_prompt(merged, "矩阵乘法我是不是还会", fields=new_fields)
    keys = {fact.item_key for fact in chosen}
    assert "topic.linear_algebra.level" in keys
    assert "topic.python.level" not in keys
    assert values["topic.python.level"] == "advanced"
    assert "intermediate" in values["topic.linear_algebra.level"]


def test_extract_context_lists_all_items_so_duplicates_are_visible() -> None:
    fields = [
        MemoryField(lane="persona", field_key="habit", name="习惯", description="作息"),
        MemoryField(
            lane="persona",
            field_key="emotion.family",
            name="对家人的情感",
            description="最近有点牵挂",
        ),
    ]
    items = [
        MemoryFact(
            lane="persona",
            field_key="habit",
            item_key="habit.night",
            title="",
            value="晚上才有空",
        ),
        MemoryFact(
            lane="persona",
            field_key="emotion.family",
            item_key="emotion.family.worry",
            title="牵挂",
            value="担心母亲的身体",
        ),
    ]
    text = format_extract_context(
        summary="最近有点惦记家里",
        fields=fields,
        items=items,
        related_keys=["emotion.family"],
    )
    assert "习惯" in text
    assert "对家人的情感" in text
    assert "担心母亲的身体" in text
    assert "晚上才有空" in text
    assert "不要再拆新字段" in text


def test_ephemeral_confirmation_is_not_kept() -> None:
    assert is_ephemeral_memory(name="关系确认", value="用户问你真的不知道吗")
    assert is_ephemeral_memory(title="了解程度", value="解释了未知即未知")
    assert is_ephemeral_memory(value="档案里没有恋爱记录，不要猜测")
    assert not is_ephemeral_memory(name="家庭", title="父母工作地", value="在浙江工作")

    fields = [
        MemoryField(lane="persona", field_key="family", name="家庭", description="父母与弟弟"),
        MemoryField(
            lane="persona",
            field_key="relationship.confirm",
            name="关系确认",
            description="对方在确认我是否知道",
        ),
    ]
    items = [
        MemoryFact(
            lane="persona",
            field_key="family",
            item_key="family.parents",
            title="父母工作地",
            value="在浙江工作",
        ),
        MemoryFact(
            lane="persona",
            field_key="relationship.confirm",
            item_key="relationship.confirm.ask",
            title="追问",
            value="用户问你真的不知道吗，档案里没有就不要猜测",
        ),
    ]
    kept_fields, kept_items = prune_ephemeral(fields, items)
    assert [item.field_key for item in kept_fields] == ["family"]
    assert [fact.item_key for fact in kept_items] == ["family.parents"]

    merged = apply_ops(
        kept_items,
        [
            MemoryOp(
                op="add",
                field="relationship.status",
                key="unknown",
                title="关系状况",
                value="尚未提供恋爱信息，档案中没有记录",
            )
        ],
        lane="persona",
    )
    assert all("尚未提供" not in fact.value for fact in merged)


def test_tidy_drops_duplicate_partner_and_splits_other() -> None:
    fields = [
        MemoryField(lane="persona", field_key="partner", name="感情关系", description="对象的情况"),
        MemoryField(
            lane="persona",
            field_key="other",
            name="其他",
            description="小名与英文名、工作、爱好、从贵州到广州",
        ),
    ]
    items = [
        MemoryFact(
            lane="persona",
            field_key="partner",
            item_key="partner.status",
            title="对象现状",
            value="在广州找工作，为了能在一起",
        ),
        MemoryFact(
            lane="persona",
            field_key="partner",
            item_key="partner.move",
            title="工作调动",
            value="正在广州找工作，为了能在一起",
        ),
        MemoryFact(
            lane="persona",
            field_key="partner",
            item_key="partner.status2",
            title="对象现状",
            value="在广州找工作，为了能在一起",
        ),
        MemoryFact(
            lane="persona",
            field_key="other",
            item_key="other.names",
            title="小名与英文名",
            value="小名九月，英文名 June / Shuey",
        ),
        MemoryFact(
            lane="persona",
            field_key="other",
            item_key="other.job",
            title="其他",
            value="AI算法工程师（联通软研院）",
        ),
        MemoryFact(
            lane="persona",
            field_key="other",
            item_key="other.sport",
            title="其他",
            value="羽毛球、乒乓球都接触过",
        ),
    ]
    new_fields, new_items = tidy_profile(fields, items, lane="persona")
    partner = [fact for fact in new_items if fact.field_key == "partner"]
    assert len(partner) == 1
    assert "广州找工作" in partner[0].value
    keys = {fact.field_key for fact in new_items}
    assert "other" not in keys
    assert any("九月" in fact.value or "Shuey" in fact.value for fact in new_items)
    assert any("工程师" in fact.value for fact in new_items)
    names = {item.name for item in new_fields}
    assert "其他" not in names
