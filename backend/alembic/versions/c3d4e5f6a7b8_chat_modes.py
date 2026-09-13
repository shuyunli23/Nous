"""Add chat_modes and conversations.mode_id.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_modes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=400), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("tool_policy", sa.String(length=16), nullable=False),
        sa.Column("use_long_term_memory", sa.Boolean(), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_modes_user", "chat_modes", ["user_id"])
    op.create_index("ix_chat_modes_key", "chat_modes", ["key"], unique=True)
    # Batch mode, not bare op.create_foreign_key: SQLite cannot ALTER a
    # constraint onto an existing table, so alembic has to copy-and-move.
    # Postgres ignores the batch wrapper and emits plain ALTERs.
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("mode_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_conversations_mode_id",
            "chat_modes",
            ["mode_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.drop_constraint("fk_conversations_mode_id", type_="foreignkey")
        batch.drop_column("mode_id")
    op.drop_index("ix_chat_modes_key", table_name="chat_modes")
    op.drop_index("ix_chat_modes_user", table_name="chat_modes")
    op.drop_table("chat_modes")
