"""Record what happened to each pull's alert.

notified_at was set whether or not the email left, so a pull alerted
with no mail provider configured looked exactly like one delivered.
Additive and nullable: existing rows keep their meaning (attempted at
notified_at, outcome unknown).

Revision ID: 0037
Revises: 0036
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0037"

down_revision: str | None = "0036"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "poll_sessions",
        sa.Column(
            "alert_status",
            sa.String(length=20),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "poll_sessions",
        "alert_status",
    )
