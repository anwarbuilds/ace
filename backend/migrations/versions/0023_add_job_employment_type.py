"""Add employment_type, so a job's contract-vs-permanent status
survives being stored.

Adzuna reports this as real, structured data on a fraction of its
postings. Two real ones -- Vestwell and T-Mobile -- stated "contract"
explicitly, with nothing in the title or description saying so, and
the eligibility gate had no field to read it from: the value was
normalized onto CanonicalJob and then silently dropped the moment it
reached storage, because JobRecord had no matching column.

Most sources never populate this at all, so the column is nullable
throughout, and None means "the source did not say" -- never "assumed
full-time" and never "assumed contract" either.

Revision ID: 0023
Revises: 0022
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0023"

down_revision: str | None = "0022"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the column, nullable, no backfill.

    Existing rows genuinely do not have this information -- it was
    never read from them in the first place -- so NULL is the honest
    value rather than a guess. The next poll of each source refreshes
    it for real.
    """

    op.add_column(
        "jobs",
        sa.Column(
            "employment_type",
            sa.String(
                length=50,
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Drop the column. Nothing else depended on it existing."""

    op.drop_column(
        "jobs",
        "employment_type",
    )
