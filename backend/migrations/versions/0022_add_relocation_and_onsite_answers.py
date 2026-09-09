"""Add the relocation and onsite-work questions a real form asked.

Found on a live Handshake application: "Are you willing to relocate
for this position if required?" and "This role is onsite and in
person. Are you willing to work from our local office Monday-Friday?"
Neither had a row in the bank, so the extension had nothing to offer
even once it could recognise the question.

Appended after whatever is already there, in the order 0021 already
established. Seeded blank like every other addition: the questions are
predictable, the answers are the user's.

Revision ID: 0022
Revises: 0021
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0022"

down_revision: str | None = "0021"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


ADDED_LABELS = (
    "Willing to relocate",
    "Willing to work onsite",
)


def upgrade() -> None:
    """Add any of the labels above that are not already present."""

    bind = op.get_bind()

    existing = {
        row[0]
        for row in bind.execute(
            sa.text(
                "SELECT label FROM"
                " application_answers"
            )
        )
    }

    start = (
        bind.execute(
            sa.text(
                "SELECT"
                " COALESCE(MAX(sort_order),"
                " -1) + 1 FROM"
                " application_answers"
            )
        ).scalar()
        or 0
    )

    missing = [
        label
        for label in ADDED_LABELS
        if label not in existing
    ]

    if not missing:
        return

    for offset, label in enumerate(
        missing
    ):
        bind.execute(
            sa.text(
                "INSERT INTO"
                " application_answers"
                " (label, value, sort_order,"
                " updated_at)"
                " VALUES (:label, '',"
                " :sort_order, NOW())"
            ),
            {
                "label": label,
                "sort_order": start + offset,
            },
        )


def downgrade() -> None:
    """Remove the added labels, keeping anything the user wrote."""

    bind = op.get_bind()

    bind.execute(
        sa.text(
            "DELETE FROM application_answers"
            " WHERE label = ANY(:labels)"
            " AND value = ''"
        ),
        {
            "labels": list(
                ADDED_LABELS
            ),
        },
    )
