"""Add the standard questions real applications keep asking.

One Dell application, on Oracle's Candidate Experience, asked
twenty-two questions and the bank had an answer for three of them.
None of the twenty-two was unusual: work authorisation restated three
different ways, prior government employment, a non-compete, a consent
to be kept on file, whether the candidate is over eighteen. The same
questions recur across Workday, Greenhouse and Ashby forms in slightly
different words.

Recognising them was the extension's problem and is fixed there. This
is the other half: a question ACE can name but has no answer for is
still a question the user has to type by hand every time.

Seeded blank, like every addition before it. The questions are
predictable; the answers are the user's, and several of them
(a criminal conviction, an involuntary discharge, a relative's
business) are ones ACE has no business inferring. Filling them once
is the whole cost.

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0024"

down_revision: str | None = "0023"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


# Grouped the way they are asked, so the answers page reads in the same
# order a form does rather than alphabetically.
ADDED_LABELS = (
    # Work authorisation, beyond the three already stored.
    "On a temporary work visa",
    "US citizen or permanent resident",
    "Citizen of an embargoed country",
    # Background and clearance.
    "Security clearance",
    "Employed by the federal government",
    "Employed by state or local government",
    "Involuntarily discharged from a job",
    "Criminal conviction",
    "Bound by a non-compete",
    "Previously employed by this company",
    "Related to an employee here",
    # Conflict of interest.
    "Employer relationship with this company",
    "Relative owns a competing business",
    # Consent.
    "Consent to keep my application on file",
    "Agree to the terms shown",
    # Education.
    "Field of study",
    "GPA",
    "Recent graduate",
    # Logistics.
    "Preferred contact method",
    "At least 18 years old",
    "Role is located in the US",
    "Willing to travel",
    "Driving licence",
    # Voluntary self-identification, asked separately from gender.
    "Transgender",
    "Sexual orientation",
    "Needs an accommodation",
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
