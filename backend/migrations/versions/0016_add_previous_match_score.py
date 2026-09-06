"""Remember the score a posting had before the last re-score.

A re-score silently reshuffles the ranking. Matching v2 moved 12 of the
top 20, and nothing on screen said so, which leaves the user unable to
tell whether ACE improved or drifted.

Storing the previous score lets a row say "MEDIUM to HIGH" once, so the
system's own learning is visible rather than something the user has to
take on trust.

Nullable, because the first score a posting ever receives has no
predecessor. That is different from a score that did not move, and the
interface must not confuse the two.

Revision ID: 0016
Revises: 0015
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0016"

down_revision: str | None = "0015"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the previous score column."""

    op.add_column(
        "job_resume_scores",
        sa.Column(
            "previous_score",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Drop it. Derived data, rebuilt by the next re-score."""

    op.drop_column(
        "job_resume_scores",
        "previous_score",
    )
