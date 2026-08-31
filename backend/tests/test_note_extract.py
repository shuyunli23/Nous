"""Tutor note drafts and pending-import routing (no LLM)."""

from __future__ import annotations

from app.nexusmind.models.knowledge import KnowledgeSource
from app.nexusmind.services.knowledge_service import (
    CHAT_DRAFT,
    conversation_source_filename,
    searchable_clause,
)
from app.services.note_extract_service import NoteDraft, NotesLLMResult


def test_chat_draft_is_not_searchable_source() -> None:
    assert CHAT_DRAFT == "chat_draft"
    assert KnowledgeSource.CHAT_DRAFT.value == "chat_draft"
    assert KnowledgeSource.CHAT.value == "chat"
    clause = searchable_clause()
    assert "source_type" in str(clause)


def test_conversation_draft_filename() -> None:
    assert conversation_source_filename("abc") == "conversation:abc"


def test_notes_schema_accepts_llm_shape() -> None:
    parsed = NotesLLMResult.model_validate(
        {
            "worth_saving": True,
            "reason": "讲清了向量检索",
            "notes": [
                {
                    "title": "向量检索",
                    "summary": "用距离找相近文本",
                    "markdown": "# 向量检索\n\n把句子变成向量。",
                    "category": "学习",
                }
            ],
        }
    )
    assert parsed.worth_saving
    assert parsed.notes[0].title == "向量检索"
    empty = NotesLLMResult.model_validate({"worth_saving": False, "notes": []})
    assert empty.notes == []
    draft = NoteDraft(title="x", markdown="# x")
    assert draft.category == "学习"
