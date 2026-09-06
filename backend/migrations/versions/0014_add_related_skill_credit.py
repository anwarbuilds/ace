"""Record partial-credit matches and the algorithm that produced a score.

Matching v1 recognised exact skill names only, so a posting asking for
"scalability" and a resume evidencing "distributed systems" scored as a
total miss. v2 gives such a pair partial credit, which needs somewhere
to record *which* requirements were earned that way -- a score the user
cannot see the reasoning behind is a number they have to trust.

``algorithm_version`` exists because scores are derived data with no
other staleness signal. Rows written by v1 are indistinguishable from v2
rows without it, so a stored score could silently reflect a scoring rule
that no longer exists. Existing rows are stamped as v1 rather than
deleted, so the corpus keeps working until a re-score replaces them.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0014"

down_revision: str | None = "0013"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


JSON_PAYLOAD = postgresql.JSONB(
    none_as_null=True,
).with_variant(
    sa.JSON(
        none_as_null=True,
    ),
    "sqlite",
)


def upgrade() -> None:
    """Add partial-credit skills and the scoring algorithm version."""

    op.add_column(
        "job_resume_scores",
        sa.Column(
            "related_skills",
            JSON_PAYLOAD,
            nullable=True,
        ),
    )

    op.add_column(
        "job_resume_scores",
        sa.Column(
            "algorithm_version",
            sa.String(
                length=32,
            ),
            nullable=True,
        ),
    )

    # Everything already stored predates partial credit. Stamping it is
    # what makes the next re-score able to tell old rows from new.
    op.execute(
        "UPDATE job_resume_scores "
        "SET algorithm_version = 'v1-exact' "
        "WHERE algorithm_version IS NULL"
    )


def downgrade() -> None:
    """Drop partial-credit columns.

    Safe to reverse: both columns are derived, and the scores beside
    them remain valid under v1 semantics.
    """

    op.drop_column(
        "job_resume_scores",
        "algorithm_version",
    )

    op.drop_column(
        "job_resume_scores",
        "related_skills",
    )
