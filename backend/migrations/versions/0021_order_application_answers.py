"""Put the answer bank in the order a form asks its questions.

0020 appended its fourteen labels after the original sixteen, so First
name and Last name landed seventeenth and eighteenth, far below Full
name at the top. The user read the editor, saw Full name alone, and
reasonably concluded the split fields were missing.

Ordering is data rather than presentation here: the editor saves the
bank in the order it displays, so a sensible stored order is what makes
the list stay sensible after the next save.

A label not listed below keeps its position at the end, in its existing
order, because it is one the user added themselves.

Revision ID: 0021
Revises: 0020
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0021"

down_revision: str | None = "0020"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


# Grouped the way the client panel groups them, so the editor and the
# panel read alike.
CANONICAL_ORDER = (
    # You
    "First name",
    "Last name",
    "Full name",
    "Email",
    "Phone",
    "Pronouns",
    # Address
    "Location",
    "Address",
    "City",
    "State",
    "Postcode",
    "Country",
    # Links
    "LinkedIn",
    "GitHub",
    "Portfolio",
    # Work authorisation
    "Work authorisation",
    "Need sponsorship now",
    "Need sponsorship in future",
    "Earliest start date",
    # Education
    "University",
    "Degree",
    "Graduation date",
    "Years of experience",
    # Voluntary disclosures
    "Gender",
    "Race or ethnicity",
    "Veteran status",
    "Disability status",
    # Written answers
    "Salary expectation",
    "How did you hear about us",
    "Why this company",
)


def upgrade() -> None:
    """Renumber sort_order, leaving the user's own questions at the end."""

    bind = op.get_bind()

    for position, label in enumerate(
        CANONICAL_ORDER
    ):
        bind.execute(
            sa.text(
                "UPDATE application_answers"
                " SET sort_order = :position"
                " WHERE label = :label"
            ),
            {
                "position": position,
                "label": label,
            },
        )

    # Anything unrecognised follows, keeping the order it already had.
    rows = bind.execute(
        sa.text(
            "SELECT id FROM application_answers"
            " WHERE label <> ALL(:known)"
            " ORDER BY sort_order, id"
        ),
        {
            "known": list(
                CANONICAL_ORDER
            ),
        },
    ).fetchall()

    for offset, row in enumerate(
        rows
    ):
        bind.execute(
            sa.text(
                "UPDATE application_answers"
                " SET sort_order = :position"
                " WHERE id = :id"
            ),
            {
                "position": len(
                    CANONICAL_ORDER
                )
                + offset,
                "id": row[0],
            },
        )


def downgrade() -> None:
    """Ordering carries no information worth restoring."""
