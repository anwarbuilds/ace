"""Group newly discovered jobs into readable discovery runs.

A scheduler cycle is the wrong grouping to show a person: measured over
25 minutes, 38 of roughly 65 cycles polled a single source, so
one-session-per-cycle would produce dozens of runs holding one job each.

A session is instead a *discovery run*: a cycle that found new jobs,
merged with the previous one when they happen close together. That
yields the grouping a person actually means -- "the 9am pull found 25
jobs" -- without inventing a fixed schedule the scheduler does not have.

Cycles that discover nothing create no session at all, so the list stays
meaningful rather than filling with empty rows.

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0013"

down_revision: str | None = "0012"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create discovery runs and link jobs to the run that found them."""

    op.create_table(
        "poll_sessions",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "jobs_discovered",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "qualifying_discovered",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_poll_sessions",
        ),
    )

    op.create_index(
        "ix_poll_sessions_started",
        "poll_sessions",
        [
            "started_at",
        ],
    )

    op.add_column(
        "jobs",
        sa.Column(
            "first_seen_session_id",
            sa.BigInteger(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_jobs_first_seen_session",
        "jobs",
        "poll_sessions",
        [
            "first_seen_session_id",
        ],
        [
            "id",
        ],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_jobs_first_seen_session",
        "jobs",
        [
            "first_seen_session_id",
        ],
    )


def downgrade() -> None:
    """Remove discovery runs."""

    op.drop_index(
        "ix_jobs_first_seen_session",
        table_name="jobs",
    )

    op.drop_constraint(
        "fk_jobs_first_seen_session",
        "jobs",
        type_="foreignkey",
    )

    op.drop_column(
        "jobs",
        "first_seen_session_id",
    )

    op.drop_index(
        "ix_poll_sessions_started",
        table_name="poll_sessions",
    )

    op.drop_table(
        "poll_sessions"
    )
