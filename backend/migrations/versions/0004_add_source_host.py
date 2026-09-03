"""Add provider host metadata to ACE job sources.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004"

down_revision: str | None = "0003"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist provider host/region routing metadata."""

    op.add_column(
        "job_sources",
        sa.Column(
            "source_host",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove provider host metadata."""

    op.drop_column(
        "job_sources",
        "source_host",
    )