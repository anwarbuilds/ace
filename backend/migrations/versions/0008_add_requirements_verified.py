"""Record whether a posting's requirements could be read.

False when the posting text was unavailable, so the rules that read
requirement text never ran. Such jobs remain in the web application but
are not emailed as ready to apply.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008"

down_revision: str | None = "0007"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the requirements-verified flag and its index."""

    op.add_column(
        "job_evaluations",
        sa.Column(
            "requirements_verified",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )

    op.create_index(
        "ix_job_evaluations_verified",
        "job_evaluations",
        [
            "requirements_verified",
        ],
    )


def downgrade() -> None:
    """Remove the requirements-verified flag."""

    op.drop_index(
        "ix_job_evaluations_verified",
        table_name="job_evaluations",
    )

    op.drop_column(
        "job_evaluations",
        "requirements_verified",
    )
