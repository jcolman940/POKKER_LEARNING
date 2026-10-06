"""initial schema: app_meta

Revision ID: 0001
Revises:
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_meta",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.String(length=1024), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_meta")
