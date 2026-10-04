"""Let a job's location be as long as the posting's list of sites.

Eightfold boards list every site a role is open in, and the adapter
writes each one in full. Arcadis posts roles open in dozens of offices;
stored with two-letter country codes its longest location was already
487 characters. Once the codes were written out as country names --
so an Indian state code could no longer be read as a US one -- some of
those passed 500, and the 500-character limit failed the whole poll
with StringDataRightTruncation: every Arcadis role went unread because
of one long row. Applied Materials and Eaton had never stored a job at
all for the same reason.

Truncating instead would be worse than failing loudly: the US site in a
long list can be the last one, and a location cut before it reads as a
role outside the US, which the gate rejects without a word. TEXT holds
the whole list. Changing varchar to text is a catalogue change in
Postgres, not a rewrite of the table.

Revision ID: 0032
Revises: 0031
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0032"

down_revision: str | None = "0031"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Widen jobs.location to TEXT."""

    op.alter_column(
        "jobs",
        "location",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Narrow jobs.location again.

    A location longer than the old limit would be cut, and a cut list
    can lose its only US site, so this refuses rather than silently
    turning US roles into foreign ones.
    """

    connection = op.get_bind()

    too_long = connection.execute(
        sa.text(
            "SELECT count(*) FROM jobs "
            "WHERE length(location) > 500"
        )
    ).scalar()

    if too_long:
        raise RuntimeError(
            (
                f"{too_long} job(s) have a location longer than 500 "
                "characters. Narrowing would cut them; delete those "
                "rows first."
            )
        )

    op.alter_column(
        "jobs",
        "location",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=False,
    )
