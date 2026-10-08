"""hero preflop decisions per hand

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hand_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hand_id", sa.Integer(), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("game_format", sa.String(length=16), nullable=False),
        sa.Column("table_size", sa.Integer(), nullable=False),
        sa.Column("position", sa.String(length=8), nullable=False),
        sa.Column("situation", sa.String(length=16), nullable=False),
        sa.Column("vs_position", sa.String(length=8), nullable=True),
        sa.Column("hand_class", sa.String(length=3), nullable=False),
        sa.Column("stack_bb", sa.Float(), nullable=False),
        sa.Column("action", sa.String(length=8), nullable=False),
        sa.Column("spot", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["hand_id"], ["hands.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_hand_decisions_hand_id", "hand_decisions", ["hand_id"])
    op.create_index(
        "ix_hand_decisions_spot", "hand_decisions", ["game_format", "position", "situation"]
    )


def downgrade() -> None:
    op.drop_index("ix_hand_decisions_spot", table_name="hand_decisions")
    op.drop_index("ix_hand_decisions_hand_id", table_name="hand_decisions")
    op.drop_table("hand_decisions")
