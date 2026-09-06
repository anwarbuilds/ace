"""Widen job identity columns for long provider paths.

Workday uses the posting's URL path as its durable identity, and those
paths embed both the location and the full job title:

    /job/100-Perimeter-Center-Pl-AtlantaGA-30346-1204/Seasonal--Guest-...

One Target posting exceeded the 255-character limit and failed the whole
poll with StringDataRightTruncation. 512 leaves comfortable headroom
while staying far inside the btree index limit for the unique
constraint that covers this column.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0011"

down_revision: str | None = "0010"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Widen external_id and requisition_id."""

    op.alter_column(
        "jobs",
        "external_id",
        existing_type=sa.String(length=255),
        type_=sa.String(length=512),
        existing_nullable=False,
    )

    op.alter_column(
        "jobs",
        "requisition_id",
        existing_type=sa.String(length=255),
        type_=sa.String(length=512),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Narrow the identity columns again.

    Rows whose identity exceeds the old limit would be truncated, so
    this refuses rather than corrupting identity silently.
    """

    connection = op.get_bind()

    too_long = connection.execute(
        sa.text(
            "SELECT count(*) FROM jobs "
            "WHERE length(external_id) > 255 "
            "OR length(requisition_id) > 255"
        )
    ).scalar()

    if too_long:
        raise RuntimeError(
            (
                f"{too_long} job(s) have an identity longer than 255 "
                "characters. Narrowing would corrupt them; delete or "
                "re-key those rows first."
            )
        )

    op.alter_column(
        "jobs",
        "requisition_id",
        existing_type=sa.String(length=512),
        type_=sa.String(length=255),
        existing_nullable=True,
    )

    op.alter_column(
        "jobs",
        "external_id",
        existing_type=sa.String(length=512),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
