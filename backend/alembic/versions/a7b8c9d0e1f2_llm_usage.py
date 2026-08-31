"""Token usage ledger.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("provider_id", sa.String(length=36), nullable=True),
        sa.Column("provider_label", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_llm_usage_user_created", "llm_usage_events", ["user_id", "created_at"]
    )
    op.create_index("ix_llm_usage_conversation", "llm_usage_events", ["conversation_id"])
    op.create_index(
        "ix_llm_usage_purpose_created", "llm_usage_events", ["purpose", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_llm_usage_purpose_created", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_conversation", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_user_created", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
