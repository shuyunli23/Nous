"""Add conversations.todos for the session-owned todo_write list.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    col_type = postgresql.JSONB() if bind.dialect.name == "postgresql" else sa.JSON()
    op.add_column("conversations", sa.Column("todos", col_type, nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "todos")
