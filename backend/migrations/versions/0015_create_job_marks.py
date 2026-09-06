"""Make saved, reviewed and dismissed durable.

These marks first shipped in browser localStorage, which had two
consequences. They did not survive a different browser or device, and
the server could not query them, so the Saved and Archive pages filtered
whatever page of results happened to be loaded. A job saved at position
400 of 777 simply did not appear.

One row per job. review_state is a single column rather than two
booleans because reviewed and dismissed are mutually exclusive: both
mean "handled", and a row that claimed to be each at once would have no
correct rendering.

applied_at is included now, unused by this migration's feature, so that
application tracking does not need a second migration over the same
table.

Single user today, so there is no owner column. Adding authentication
(roadmap item 8) means adding one and scoping every query by it.

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0015"

down_revision: str | None = "0014"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the durable mark table."""

    op.create_table(
        "job_marks",
        sa.Column(
            "job_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "jobs.id",
                ondelete="CASCADE",
            ),
            primary_key=True,
            autoincrement=False,
        ),
        sa.Column(
            "is_saved",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "review_state",
            sa.String(
                length=16,
            ),
            nullable=True,
        ),
        sa.Column(
            "applied_at",
            sa.DateTime(
                timezone=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(
                timezone=True,
            ),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "review_state IS NULL OR "
            "review_state IN "
            "('reviewed', 'dismissed')",
            name=(
                "ck_job_marks_"
                "review_state_valid"
            ),
        ),
    )

    # Saved and Archive both filter on these, so the index carries the
    # columns those pages actually select by.
    op.create_index(
        "ix_job_marks_saved",
        "job_marks",
        [
            "is_saved",
        ],
    )

    op.create_index(
        "ix_job_marks_review_state",
        "job_marks",
        [
            "review_state",
        ],
    )


def downgrade() -> None:
    """Drop the mark table.

    Destructive: these marks are entered by hand and cannot be rebuilt
    from any other source, unlike scores or evaluations.
    """

    op.drop_index(
        "ix_job_marks_review_state",
        table_name="job_marks",
    )

    op.drop_index(
        "ix_job_marks_saved",
        table_name="job_marks",
    )

    op.drop_table(
        "job_marks",
    )
