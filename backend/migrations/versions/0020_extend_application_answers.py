"""Add the questions real forms ask that the first seed missed.

The original sixteen covered identity, links and authorisation. Sitting
with actual Greenhouse, Ashby and Lever forms shows what they also ask
on nearly every submission: a split first and last name, a postal
address, and the four voluntary disclosure questions. Those last four
never change and are pure repetition, which makes them the most
valuable thing in the bank.

Only missing labels are added. A label the user already has keeps its
value, because the answers are theirs and a migration must never
overwrite them.

Revision ID: 0020
Revises: 0019
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0020"

down_revision: str | None = "0019"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


# Ordered as a form usually asks them, so the editor reads top to bottom
# the way an application does.
ADDED_LABELS = (
    "First name",
    "Last name",
    "Pronouns",
    "Address",
    "City",
    "State",
    "Postcode",
    "Country",
    "Years of experience",
    "How did you hear about us",
    "Gender",
    "Race or ethnicity",
    "Veteran status",
    "Disability status",
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
    """Remove the added labels, keeping anything the user wrote.

    A label carrying an answer is left alone: the user typed it, and a
    downgrade must not throw away their work.
    """

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
