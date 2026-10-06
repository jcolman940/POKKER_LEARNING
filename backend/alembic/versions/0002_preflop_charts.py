"""preflop charts

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "preflop_charts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("game_format", sa.String(length=16), nullable=False),
        sa.Column("players", sa.Integer(), nullable=False),
        sa.Column("position", sa.String(length=8), nullable=False),
        sa.Column("vs_position", sa.String(length=8), nullable=True),
        sa.Column("stack_bb", sa.Float(), nullable=False),
        sa.Column("situation", sa.String(length=16), nullable=False),
        sa.Column("open_size_bb", sa.Float(), nullable=True),
        sa.Column("rake", sa.String(length=200), nullable=True),
        sa.Column("ante_bb", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_preflop_charts_spot", "preflop_charts", ["situation", "position", "game_format"]
    )


def downgrade() -> None:
    op.drop_index("ix_preflop_charts_spot", table_name="preflop_charts")
    op.drop_table("preflop_charts")
