"""String enums shared by ORM models and API schemas.

Stored as plain VARCHAR instead of native DB enums: adding a new value stays a
code change rather than a schema migration, and it keeps SQLite/Postgres
behaviour identical.
"""

from __future__ import annotations

from enum import StrEnum


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class SkillStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"


class SkillSource(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
    IMPORTED = "imported"


class SkillPackStatus(StrEnum):
    """Lifecycle for an installed nous-pack/2 archive."""

    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    DISABLED = "disabled"


class FeedbackValue(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
