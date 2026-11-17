"""Add the daily score against the test lists (REC-01).

Revision ID: 0052
Revises: 0051

Additive only: one new table, and no existing row or column is touched.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recall_runs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("missed", sa.JSON(), nullable=False),
        sa.UniqueConstraint("day", name="uq_recall_runs_day"),
    )


def downgrade() -> None:
    # Derived data: the next day's check rebuilds it, and nothing else reads it.
    op.drop_table("recall_runs")
