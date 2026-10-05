"""Record how much each pull checked, not only what was new.

The Activity page showed "31 postings seen" for a quarter hour, and the
user reasonably read it as ACE having looked at 31 postings. It was the
number of postings that were *new*. In that same window ACE read 483
boards holding about 63,000 postings. Nothing on the page said so, so
a quiet quarter hour looked like a scheduler barely searching.

Each pull now records how many boards were checked during it and how
many postings those boards held.

Revision ID: 0035
Revises: 0034
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0035"

down_revision: str | None = "0034"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "poll_sessions",
        sa.Column(
            "boards_checked",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "poll_sessions",
        sa.Column(
            "postings_checked",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "poll_sessions",
        "postings_checked",
    )

    op.drop_column(
        "poll_sessions",
        "boards_checked",
    )
