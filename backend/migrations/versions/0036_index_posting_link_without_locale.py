"""Index the posting link without its Workday locale.

The queue hides a feed's copy of a posting ACE reads directly by
matching links. The feed's Workday links carry "/en-US/" where the
board's own do not, so every RELX and LexisNexis role was shown twice.
The link is now compared without that segment, and this replaces 0034's
index with one on the new expression, so the planner can still use it.

Revision ID: 0036
Revises: 0035
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0036"

down_revision: str | None = "0035"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_jobs_posting_link_key"
    )

    op.execute(
        "CREATE INDEX ix_jobs_posting_link_key "
        "ON jobs (replace(replace(replace(lower(official_url), "
        "'://www.', '://'), 'http://', 'https://'), '/en-us/', '/'))"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_jobs_posting_link_key"
    )

    op.execute(
        "CREATE INDEX ix_jobs_posting_link_key "
        "ON jobs (replace(replace(lower(official_url), "
        "'://www.', '://'), 'http://', 'https://'))"
    )
