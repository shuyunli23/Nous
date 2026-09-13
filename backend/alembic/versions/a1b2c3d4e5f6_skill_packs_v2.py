"""skill packs v2 (nous-pack/2)

Revision ID: a1b2c3d4e5f6
Revises: fe1df9979a40
Create Date: 2026-08-10 23:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "fe1df9979a40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def JSONType() -> sa.types.TypeEngine:
    """Fresh JSON type per column (JSONB on Postgres).

    A factory, not a module-level instance: ``with_variant`` returns a type
    *object*, and calling it (``JSONType()`` below) raised
    ``TypeError: 'JSON' object is not callable``, so this revision could never
    run. Keeping the call sites intact means one fix instead of six.
    """
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "skill_packs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("pack_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("permissions", JSONType(), nullable=False),
        sa.Column("permissions_requested", JSONType(), nullable=False),
        sa.Column("tags", JSONType(), nullable=False),
        sa.Column("author", sa.String(length=200), nullable=True),
        sa.Column("license", sa.String(length=64), nullable=True),
        sa.Column("min_nous", sa.String(length=32), nullable=True),
        sa.Column("install_path", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("manifest", JSONType(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "pack_id", "version", name="uq_skill_packs_user_pack_ver"
        ),
    )
    with op.batch_alter_table("skill_packs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_skill_packs_user_status", ["user_id", "status"], unique=False
        )
        batch_op.create_index(
            "ix_skill_packs_user_pack_id", ["user_id", "pack_id"], unique=False
        )

    with op.batch_alter_table("skills", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pack_row_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column("pack_skill_key", sa.String(length=128), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_skills_pack_row_id",
            "skill_packs",
            ["pack_row_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_skills_pack_row", ["pack_row_id"], unique=False)

    op.create_table(
        "skill_pack_tools",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pack_row_id", sa.String(length=36), nullable=False),
        sa.Column("skill_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("exposed_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("parameters", JSONType(), nullable=False),
        sa.Column("runner", JSONType(), nullable=False),
        sa.Column("skill_key", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pack_row_id"], ["skill_packs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "pack_row_id", "name", name="uq_skill_pack_tools_pack_name"
        ),
    )
    with op.batch_alter_table("skill_pack_tools", schema=None) as batch_op:
        batch_op.create_index(
            "ix_skill_pack_tools_exposed", ["exposed_name"], unique=False
        )


def downgrade() -> None:
    op.drop_table("skill_pack_tools")
    with op.batch_alter_table("skills", schema=None) as batch_op:
        batch_op.drop_index("ix_skills_pack_row")
        batch_op.drop_constraint("fk_skills_pack_row_id", type_="foreignkey")
        batch_op.drop_column("pack_skill_key")
        batch_op.drop_column("pack_row_id")
    op.drop_table("skill_packs")
