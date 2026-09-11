"""Record whether a title announces a new-graduate role.

is_early_career already existed and is deliberately wider: junior,
associate, entry level, rotational and "Engineer I" all set it, and
none of them says new grad. The user asks the two questions
separately -- "early career and new grad are important for me" -- and
could only ask one of them.

Stored rather than matched in SQL at read time so the patterns live in
one place, in Python, beside the rules that already read titles. The
alternative was a second copy of them as a Postgres regex, which is
the drift the company-tier work already learned to avoid, and which
the SQLite test database could not run at all.

Revision ID: 0028
Revises: 0027
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0028"
down_revision: str | Sequence[str] | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the column and the index the filter reads."""

    op.add_column(
        "job_evaluations",
        sa.Column(
            "is_new_grad",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    op.create_index(
        "ix_job_evaluations_new_grad",
        "job_evaluations",
        ["is_new_grad"],
    )


def downgrade() -> None:
    """Drop both again."""

    op.drop_index(
        "ix_job_evaluations_new_grad",
        table_name="job_evaluations",
    )

    op.drop_column(
        "job_evaluations",
        "is_new_grad",
    )
