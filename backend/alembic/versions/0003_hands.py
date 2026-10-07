"""hands, import batches and tournament results

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FACT_INT_COLUMNS = [
    "allin_adjusted",
    "vpip",
    "pfr",
    "threebet_opp",
    "threebet",
    "fold3b_opp",
    "fold3b",
    "cbet_flop_opp",
    "cbet_flop",
    "cbet_turn_opp",
    "cbet_turn",
    "fold_cbet_opp",
    "fold_cbet",
    "saw_flop",
    "wtsd",
    "wsd",
    "agg_bets",
    "agg_calls",
    "agg_folds",
]


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("files", sa.Integer(), nullable=False),
        sa.Column("hands_found", sa.Integer(), nullable=False),
        sa.Column("imported", sa.Integer(), nullable=False),
        sa.Column("duplicates", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
    )
    op.create_table(
        "hands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site", sa.String(length=32), nullable=False),
        sa.Column("hand_id", sa.String(length=64), nullable=False),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("game_type", sa.String(length=16), nullable=False),
        sa.Column("tournament_id", sa.String(length=64), nullable=True),
        sa.Column("bb", sa.Float(), nullable=False),
        sa.Column(
            "import_id",
            sa.Integer(),
            sa.ForeignKey("import_batches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("record", sa.JSON(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("has_hero", sa.Integer(), nullable=False),
        sa.Column("hero", sa.String(length=64), nullable=True),
        sa.Column("hero_cards", sa.String(length=4), nullable=True),
        sa.Column("hand_class", sa.String(length=3), nullable=True),
        sa.Column("position", sa.String(length=8), nullable=True),
        sa.Column("table_size", sa.Integer(), nullable=False),
        sa.Column("stack_bb", sa.Float(), nullable=False),
        sa.Column("net_chips", sa.Float(), nullable=False),
        sa.Column("net_bb", sa.Float(), nullable=False),
        sa.Column("allin_adj_bb", sa.Float(), nullable=False),
        sa.Column("showdown_bb", sa.Float(), nullable=False),
        sa.Column("non_showdown_bb", sa.Float(), nullable=False),
        *[sa.Column(name, sa.Integer(), nullable=False) for name in FACT_INT_COLUMNS],
        sa.UniqueConstraint("site", "hand_id", name="uq_hands_site_hand_id"),
    )
    op.create_index("ix_hands_played_at", "hands", ["played_at"])
    op.create_index("ix_hands_filters", "hands", ["game_type", "position", "table_size"])
    op.create_table(
        "tournament_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site", sa.String(length=32), nullable=False),
        sa.Column("tournament_id", sa.String(length=64), nullable=False),
        sa.Column("game_type", sa.String(length=16), nullable=False),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("buy_in", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column("prize", sa.Float(), nullable=False),
        sa.Column("finish", sa.Integer(), nullable=True),
        sa.Column("entrants", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.UniqueConstraint("site", "tournament_id", name="uq_tournament_results"),
    )


def downgrade() -> None:
    op.drop_table("tournament_results")
    op.drop_index("ix_hands_filters", table_name="hands")
    op.drop_index("ix_hands_played_at", table_name="hands")
    op.drop_table("hands")
    op.drop_table("import_batches")
