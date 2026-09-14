"""Record when a pull's alert was sent.

Alerts are one email per pull, and the scheduler decides what to send
on every cycle -- which runs every few seconds. Without a marker the
same pull would be emailed on every cycle for as long as it stayed the
most recent one.

A timestamp rather than a boolean, so "sent at 08:14" and "never sent"
are distinguishable from each other and from a send that failed.

Revision ID: 0029
Revises: 0028
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the column and the index the sweep reads."""

    op.add_column(
        "poll_sessions",
        sa.Column(
            "notified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # The sweep asks for unnotified pulls, which is a small set against
    # a table that grows by 96 rows a day.
    op.create_index(
        "ix_poll_sessions_unnotified",
        "poll_sessions",
        ["notified_at"],
    )

    # Everything that already exists is treated as sent. Deploying this
    # must not email a backlog of every pull ACE has ever recorded.
    op.execute(
        "UPDATE poll_sessions SET notified_at = now()",
    )


def downgrade() -> None:
    """Drop it."""

    op.drop_index(
        "ix_poll_sessions_unnotified",
        table_name="poll_sessions",
    )

    op.drop_column(
        "poll_sessions",
        "notified_at",
    )
