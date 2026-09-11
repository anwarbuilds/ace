"""Record why a company's board could not be found.

Coverage reported 154 companies as unreachable and could not say why
any of them were. Auditing that list by hand found that most were not
unreachable at all: some sat on an ATS ACE can already read but never
probed, one was rejected because it writes its own name with its
domain attached, and one had a careers page slightly larger than the
buffer that read it.

None of that was visible. This table makes the next round of it
visible, by keeping what stood in the way of each company the last
time ACE looked.

Revision ID: 0027
Revises: 0026
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0027"

down_revision: str | None = "0026"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the probe-result table."""

    op.create_table(
        "source_probes",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "company_key",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "company_name",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            sa.String(40),
            nullable=False,
        ),
        sa.Column(
            "detail",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "source_type",
            sa.String(50),
            nullable=True,
        ),
        sa.Column(
            "source_account",
            sa.String(255),
            nullable=True,
        ),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "company_key",
            name="uq_source_probes_company",
        ),
    )


def downgrade() -> None:
    """Drop the probe-result table."""

    op.drop_table(
        "source_probes"
    )
