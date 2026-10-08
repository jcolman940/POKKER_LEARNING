"""trainer sessions, cards, attempts and payout structures

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BUILTIN_PAYOUTS = {
    "Mesa final 9 (100)": [30, 20, 14, 10, 8, 6.5, 5, 3.75, 2.75],
    "Burbuja SNG 4 de 3 premios": [50, 30, 20],
}


def upgrade() -> None:
    op.create_table(
        "trainer_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("relearn", sa.JSON(), nullable=False),
        sa.Column("spots_served", sa.Integer(), nullable=False),
    )
    op.create_table(
        "trainer_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("scenario", sa.JSON(), nullable=False),
        sa.Column("ease", sa.Float(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("lapses", sa.Integer(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("key", name="uq_trainer_cards_key"),
    )
    op.create_table(
        "trainer_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spot_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("scenario", sa.JSON(), nullable=False),
        sa.Column("offered", sa.JSON(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=True),
        sa.Column("reference", sa.JSON(), nullable=False),
        sa.Column("loss", sa.Float(), nullable=True),
        sa.Column("loss_unit", sa.String(length=16), nullable=True),
        sa.Column("verdict", sa.String(length=16), nullable=True),
        sa.Column("approximate", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["trainer_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["trainer_cards.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("spot_id", name="uq_trainer_attempts_spot_id"),
    )
    op.create_index("ix_trainer_attempts_session_id", "trainer_attempts", ["session_id"])
    op.create_index("ix_trainer_attempts_card_id", "trainer_attempts", ["card_id"])
    payouts = op.create_table(
        "payout_structures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("payouts", sa.JSON(), nullable=False),
        sa.Column("builtin", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("name", name="uq_payout_structures_name"),
    )
    op.bulk_insert(
        payouts,
        [{"name": n, "payouts": p, "builtin": True} for n, p in BUILTIN_PAYOUTS.items()],
    )


def downgrade() -> None:
    op.drop_table("payout_structures")
    op.drop_index("ix_trainer_attempts_card_id", table_name="trainer_attempts")
    op.drop_index("ix_trainer_attempts_session_id", table_name="trainer_attempts")
    op.drop_table("trainer_attempts")
    op.drop_table("trainer_cards")
    op.drop_table("trainer_sessions")
