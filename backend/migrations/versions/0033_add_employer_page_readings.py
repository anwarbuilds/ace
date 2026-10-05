"""Remember what each employer's own posting page said.

The curated feed carries no job description, so the rules that read
requirements -- clearance, citizenship, sponsorship, years of
experience -- never ran on its postings. An audit on 2026-10-04 read the
employer's own page for 85 feed postings that had passed: 50 should
have been rejected, 43 of them for a security clearance. That was the
clearance noise the user kept seeing.

Feed postings are now judged on the employer's own page. A reading is
kept per posting URL so a page is fetched once a week at most, not on
every change to the feed, and so the next feed poll does not put the
placeholder back.

Revision ID: 0033
Revises: 0032
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0033"

down_revision: str | None = "0032"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employer_page_readings",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "url",
            sa.Text(),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table(
        "employer_page_readings"
    )
