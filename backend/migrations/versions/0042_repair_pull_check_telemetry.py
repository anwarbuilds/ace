"""Repair restored databases that were stamped past pull telemetry.

The production restore can legitimately contain an Alembic revision newer
than the physical schema when it came from an older branch that reused the
same revision number.  Migration 0040 added three nullable telemetry columns,
but a restored database was already stamped 0040 and therefore skipped that
upgrade.  Add only the columns that are actually absent.

This migration is additive and preserves every existing poll session.

Revision ID: 0042
Revises: 0041
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0042"

down_revision: str | None = "0041"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


COLUMNS = (
    "sources_attempted",
    "poll_attempts",
    "failed_checks",
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    present = {column["name"] for column in inspector.get_columns("poll_sessions")}
    for name in COLUMNS:
        if name not in present:
            op.add_column(
                "poll_sessions",
                sa.Column(name, sa.Integer(), nullable=True),
            )


def downgrade() -> None:
    # Revision 0041 already expects these columns to exist.  Dropping them
    # while stepping back to 0041 would recreate the broken schema this
    # migration repairs, so the downgrade intentionally keeps them.
    pass
