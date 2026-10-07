"""solver results and jobs

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "solver_results",
        sa.Column("hash", sa.String(length=64), primary_key=True),
        sa.Column("spot", sa.JSON(), nullable=False),
        sa.Column("tree", sa.LargeBinary(), nullable=False),
        sa.Column("exploitability", sa.Float(), nullable=True),
        sa.Column("iterations", sa.Integer(), nullable=False),
        sa.Column("solve_seconds", sa.Float(), nullable=False),
        sa.Column("solver_version", sa.String(length=32), nullable=False),
        sa.Column("preset", sa.String(length=32), nullable=False),
        sa.Column("library_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_solver_results_library_key", "solver_results", ["library_key"])
    op.create_table(
        "solver_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spot_hash", sa.String(length=64), nullable=False),
        sa.Column("spot", sa.JSON(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("exploitability", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("library_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_solver_jobs_pick", "solver_jobs", ["status", "priority", "id"])
    op.create_index("ix_solver_jobs_spot_hash", "solver_jobs", ["spot_hash"])
    op.create_index("ix_solver_jobs_library_key", "solver_jobs", ["library_key"])


def downgrade() -> None:
    op.drop_index("ix_solver_jobs_library_key", table_name="solver_jobs")
    op.drop_index("ix_solver_jobs_spot_hash", table_name="solver_jobs")
    op.drop_index("ix_solver_jobs_pick", table_name="solver_jobs")
    op.drop_table("solver_jobs")
    op.drop_index("ix_solver_results_library_key", table_name="solver_results")
    op.drop_table("solver_results")
