"""Track what happened after applying, not just that you applied.

An application has a life after it is sent. Revisiting a posting and
seeing only "Applied Sep 3" leaves the most useful question unanswered:
did anything come of it. Without somewhere to record a rejection, a
closed loop looks identical to one still open, and the same dead lead
gets re-read every week.

Status is separate from applied_at. applied_at is when the application
was sent and never changes; status is where it stands now and moves
several times over a posting's life. Collapsing them would make a
rejection overwrite the date it was applied.

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0017"

down_revision: str | None = "0016"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add application status and the time it last moved."""

    op.add_column(
        "job_marks",
        sa.Column(
            "application_status",
            sa.String(
                length=24,
            ),
            nullable=True,
        ),
    )

    op.add_column(
        "job_marks",
        sa.Column(
            "status_changed_at",
            sa.DateTime(
                timezone=True,
            ),
            nullable=True,
        ),
    )

    op.add_column(
        "job_marks",
        sa.Column(
            "status_note",
            sa.Text(),
            nullable=True,
        ),
    )

    # Anything already marked applied is exactly that, and nothing more
    # is known about it. Stamped explicitly rather than left null so
    # "applied, no news" is distinguishable from "never applied".
    op.execute(
        "UPDATE job_marks "
        "SET application_status = 'applied', "
        "    status_changed_at = applied_at "
        "WHERE applied_at IS NOT NULL "
        "  AND application_status IS NULL"
    )

    op.create_index(
        "ix_job_marks_application_status",
        "job_marks",
        [
            "application_status",
        ],
    )


def downgrade() -> None:
    """Drop the status columns.

    Destructive: an application outcome is entered by hand and cannot
    be recovered from any other source.
    """

    op.drop_index(
        "ix_job_marks_application_status",
        table_name="job_marks",
    )

    op.drop_column(
        "job_marks",
        "status_note",
    )

    op.drop_column(
        "job_marks",
        "status_changed_at",
    )

    op.drop_column(
        "job_marks",
        "application_status",
    )
