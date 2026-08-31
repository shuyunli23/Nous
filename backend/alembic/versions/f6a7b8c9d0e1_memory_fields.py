"""Add memory_fields, summaries, and item.field_key.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_memories",
        sa.Column("persona_summary", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "user_memories",
        sa.Column("knowledge_summary", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "memory_items",
        sa.Column("field_key", sa.String(length=80), nullable=False, server_default=""),
    )
    op.execute("UPDATE memory_items SET field_key = category WHERE field_key = '' OR field_key IS NULL")
    op.create_table(
        "memory_fields",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("lane", sa.String(length=16), nullable=False),
        sa.Column("field_key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "lane", "field_key", name="uq_memory_fields_user_lane_key"),
    )
    op.create_index("ix_memory_fields_user_lane", "memory_fields", ["user_id", "lane"])


def downgrade() -> None:
    op.drop_index("ix_memory_fields_user_lane", table_name="memory_fields")
    op.drop_table("memory_fields")
    op.drop_column("memory_items", "field_key")
    op.drop_column("user_memories", "knowledge_summary")
    op.drop_column("user_memories", "persona_summary")
