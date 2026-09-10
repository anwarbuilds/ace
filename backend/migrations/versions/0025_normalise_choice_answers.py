"""Put stored choice answers onto the wording ACE now offers.

The answer bank used to be text boxes, so a choice answer was whatever
the user typed. Now that ACE offers the options and ships the synonyms
for them, a stored value has to be one of those options or the editor
cannot show it as selected and the extension has no aliases to match
with.

One value in the real bank drifted: "Job Portal", typed when the box
was free text, against an offered "Job board". It is the same concept,
which is exactly the point -- knowing that is ACE's job, and the
synonyms now live in the catalogue rather than in what the user
remembered to type.

Written out longhand rather than imported from the catalogue. A
migration has to keep meaning what it meant when it ran, and the
catalogue is free to change.

Revision ID: 0025
Revises: 0024
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0025"

down_revision: str | None = "0024"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


# (label, value as typed, value as now offered)
RENAMES = (
    (
        "How did you hear about us",
        "Job Portal",
        "Job board",
    ),
)


def upgrade() -> None:
    """Rewrite each drifted value, leaving anything else alone."""

    bind = op.get_bind()

    for label, was, now in RENAMES:
        bind.execute(
            sa.text(
                "UPDATE application_answers"
                " SET value = :now,"
                " updated_at = NOW()"
                " WHERE label = :label"
                " AND value = :was"
            ),
            {
                "label": label,
                "was": was,
                "now": now,
            },
        )


def downgrade() -> None:
    """Put the typed wording back."""

    bind = op.get_bind()

    for label, was, now in RENAMES:
        bind.execute(
            sa.text(
                "UPDATE application_answers"
                " SET value = :was,"
                " updated_at = NOW()"
                " WHERE label = :label"
                " AND value = :now"
            ),
            {
                "label": label,
                "was": was,
                "now": now,
            },
        )
