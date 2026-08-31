"""Add messages.execution_trace for chat UI step timeline.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("execution_trace", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "execution_trace")
