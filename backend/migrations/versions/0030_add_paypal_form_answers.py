"""Add the questions a real application asked and the bank could not.

Every label here was a question on a live submission that ACE had no
row for, so it was left blank and filled by hand. Three of them blocked
the page, because the form required them.

Added empty, exactly as 0020 added its labels. The answers are the
user's own -- an immigration status, a set of personal declarations --
and they belong in the running instance, not in a migration in a public
repository. The editor is where they get filled in.

Only missing labels are added. A label the user already has keeps its
value, because the answers are theirs and a migration must never
overwrite them.

Revision ID: 0030
Revises: 0029
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0030"

down_revision: str | None = "0029"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


# Ordered the way the form asked them.
ADDED_LABELS = (
    # The conflict-of-interest block, which the form required in full.
    "Government official",
    "Related to a government official",
    "Referred by a merchant or third party",
    # The language block: five dropdowns, one stored level.
    "Language",
    "Language fluency",
    "Fluent in this language",
    # Asked straight after the sponsorship question, and required.
    "Visa type",
    "Experience with this tech stack",
    "Enterprise software experience",
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

    A label carrying an answer is left alone: the user filled it in, and
    a downgrade must not throw their work away.
    """

    op.get_bind().execute(
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
