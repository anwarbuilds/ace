"""Give the stored phone number its country code.

The bank held "+ 555 010 0100": a plus sign, and then a US number with
no country code behind it. A leading "+" says the number that follows
is international and begins with a country code, and this one does not,
so the "+" was making a promise the digits did not keep.

This is the real cause of a symptom I misread. A live form showed Phone
as "+5550100100" and I recorded that as a phone widget eating the dial
code. It was not: strip the spaces from what was stored and that is
exactly the string, character for character. The widget reproduced the
bank faithfully. Nothing was eaten, because there was no "1" there to
eat.

The separate bug -- a widget resetting the number to "+1" when its
country is chosen -- was real, was reported, and is fixed by filling
the country first. This is the other half, and no amount of extension
code could have fixed it, because the value was wrong before it left
ACE.

Guarded on the exact old string, so a number the user has since
corrected themselves is left alone.

Revision ID: 0031
Revises: 0030
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0031"

down_revision: str | None = "0030"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


WAS = "+ 555 010 0100"

NOW = "+1 555 010 0100"


def upgrade() -> None:
    """Put the country code in front of the number."""

    op.get_bind().execute(
        sa.text(
            "UPDATE application_answers"
            " SET value = :now,"
            " updated_at = NOW()"
            " WHERE label = 'Phone'"
            " AND value = :was"
        ),
        {
            "was": WAS,
            "now": NOW,
        },
    )


def downgrade() -> None:
    """Put the original string back, exactly as it was."""

    op.get_bind().execute(
        sa.text(
            "UPDATE application_answers"
            " SET value = :was,"
            " updated_at = NOW()"
            " WHERE label = 'Phone'"
            " AND value = :now"
        ),
        {
            "was": WAS,
            "now": NOW,
        },
    )
