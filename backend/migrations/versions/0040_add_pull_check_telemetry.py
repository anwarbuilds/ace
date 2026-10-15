"""What each fifteen minute pull attempted, not only what succeeded.

poll_sessions already held boards_checked (distinct boards read
successfully in the window) and postings_checked (what they held). A
failed or refused poll was recorded nowhere, so a window where half the
sources failed looked the same as a healthy one, and "sources checked"
could not be told apart from "sources that answered".

Three nullable counts, filled by the scheduler from now on. Null means
not recorded: every row written before this migration stays null and
the interface says so, rather than backfilling a guess.

Purely additive.

Revision ID: 0040
Revises: 0039
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0040"

down_revision: str | None = "0039"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


COLUMNS = (
    "sources_attempted",
    "poll_attempts",
    "failed_checks",
)


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column(
            "poll_sessions",
            sa.Column(
                name,
                sa.Integer(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    for name in reversed(COLUMNS):
        op.drop_column(
            "poll_sessions",
            name,
        )
