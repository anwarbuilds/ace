"""Record when each source was last fetched in full.

Conditional requests mean a source can answer 304 indefinitely. If a
provider ever returns a stale validator, ACE would keep believing
nothing had changed and would go quietly out of date -- which is this
system's worst failure mode, because silence produces no error.

Recording the last full fetch lets the scheduler force an unconditional
one periodically, bounding how long a bad validator can hide changes.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0012"

down_revision: str | None = "0011"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Track the last unconditional fetch per source."""

    op.add_column(
        "source_states",
        sa.Column(
            "last_full_fetch_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove the full-fetch marker."""

    op.drop_column(
        "source_states",
        "last_full_fetch_at",
    )
