"""Record whether a posting is explicitly early-career.

The flag orders the queue so labelled new-grad roles lead. It never
excludes: an unlabelled posting is frequently open to a graduate, and
silence has always meant unknown in ACE rather than rejection.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007"

down_revision: str | None = "0006"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the early-career flag and its index."""

    op.add_column(
        "job_evaluations",
        sa.Column(
            "is_early_career",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )

    op.create_index(
        "ix_job_evaluations_early_career",
        "job_evaluations",
        [
            "is_early_career",
        ],
    )


def downgrade() -> None:
    """Remove the early-career flag."""

    op.drop_index(
        "ix_job_evaluations_early_career",
        table_name="job_evaluations",
    )

    op.drop_column(
        "job_evaluations",
        "is_early_career",
    )
