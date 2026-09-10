"""Add the repeating work and study blocks forms ask for.

The answer bank is one value per question. A work history is several
of the same question over again -- employer, title, dates, description,
then a Remove link and another identical block underneath -- and real
Workday and Oracle forms ask for three or four of them. There was
nowhere to put that, so the extension filled the questions around them
and left every block empty.

Work and study share one table because they share a shape. Dates are a
month and a year, not a date: that is what the dropdowns ask for, and a
real date would mean inventing a day nobody typed.

Revision ID: 0026
Revises: 0025
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0026"

down_revision: str | None = "0025"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the history table."""

    op.create_table(
        "history_entries",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "kind",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "employer",
            sa.String(255),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "job_title",
            sa.String(255),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "location",
            sa.String(255),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "start_month",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "start_year",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "end_month",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "end_year",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_history_entries_kind_order",
        "history_entries",
        [
            "kind",
            "sort_order",
        ],
    )


def downgrade() -> None:
    """Drop the history table."""

    op.drop_index(
        "ix_history_entries_kind_order",
        table_name="history_entries",
    )

    op.drop_table(
        "history_entries"
    )
