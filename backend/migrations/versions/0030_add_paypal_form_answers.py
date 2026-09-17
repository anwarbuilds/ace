"""Add the questions a real PayPal application asked and ACE could not.

Every question on this list was left blank on a live submission and
filled by hand. Three of them blocked the page outright, because the
form required them.

Two kinds of change, and they are different in an important way.

The additions are new labels carrying the answers the user gave on that
form. A migration must never overwrite an answer the user wrote, and
this does not: a label that is not there has nothing to overwrite. The
values are the user's own, read off the submission they made.

The Degree change *is* an edit to a stored value, and it needs the
reason stated. A degree dropdown asks for the level, never the subject.
The bank held "Masters in Computer Science" -- the two run together --
which matched no option on a form offering "Masters Degree or
Equivalent", so a required field stayed empty and stopped the
application. The subject is not lost: "Field of study" already holds
Computer Science, which is where a form asks for it separately. The
downgrade puts the old wording back.

Written out longhand rather than imported from the catalogue, for the
same reason 0025 was: a migration has to keep meaning what it meant
when it ran, and the catalogue is free to change.

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


# (label, value). Ordered the way the form asked them.
ADDED = (
    # The conflict-of-interest block, which PayPal requires in full.
    (
        "Government official",
        "No",
    ),
    (
        "Related to a government official",
        "No",
    ),
    (
        "Referred by a merchant or third party",
        "No",
    ),
    # The language block: five dropdowns, one level.
    (
        "Language",
        "English",
    ),
    (
        "Language fluency",
        "Fluent",
    ),
    (
        "Fluent in this language",
        "Yes",
    ),
    # Asked straight after the sponsorship question, and required.
    (
        "Visa type",
        "F-1 CPT",
    ),
    (
        "Experience with this tech stack",
        "Yes",
    ),
    (
        "Enterprise software experience",
        "Yes",
    ),
)


DEGREE_WAS = "Masters in Computer Science"

DEGREE_NOW = "Masters"


def upgrade() -> None:
    """Add the missing labels; put Degree onto the level alone."""

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
        (label, value)
        for label, value in ADDED
        if label not in existing
    ]

    for offset, (
        label,
        value,
    ) in enumerate(
        missing
    ):
        bind.execute(
            sa.text(
                "INSERT INTO"
                " application_answers"
                " (label, value, sort_order,"
                " updated_at)"
                " VALUES (:label, :value,"
                " :sort_order, NOW())"
            ),
            {
                "label": label,
                "value": value,
                "sort_order": start + offset,
            },
        )

    # Guarded on the exact old value, so a Degree the user has since
    # changed themselves is left exactly as they left it.
    bind.execute(
        sa.text(
            "UPDATE application_answers"
            " SET value = :now,"
            " updated_at = NOW()"
            " WHERE label = 'Degree'"
            " AND value = :was"
        ),
        {
            "was": DEGREE_WAS,
            "now": DEGREE_NOW,
        },
    )


def downgrade() -> None:
    """Remove the added labels and restore the old Degree wording.

    A label whose answer has been changed since is left alone: that is
    the user's own edit, and a downgrade must not throw it away.
    """

    bind = op.get_bind()

    for label, value in ADDED:
        bind.execute(
            sa.text(
                "DELETE FROM"
                " application_answers"
                " WHERE label = :label"
                " AND value = :value"
            ),
            {
                "label": label,
                "value": value,
            },
        )

    bind.execute(
        sa.text(
            "UPDATE application_answers"
            " SET value = :was,"
            " updated_at = NOW()"
            " WHERE label = 'Degree'"
            " AND value = :now"
        ),
        {
            "was": DEGREE_WAS,
            "now": DEGREE_NOW,
        },
    )
