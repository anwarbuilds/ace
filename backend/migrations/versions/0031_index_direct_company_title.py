"""Index the lookup that hides a feed's copy of a direct role.

The queue now suppresses a curated feed's posting when ACE already reads
the same role -- same company, same title -- from the employer's own
board. That is a correlated lookup against every active posting, and
without an index it turned a 0.05 s queue load into 1.32 s. The queue
loads on every visit, so fixing a duplicate would have made the whole
page visibly slow.

The first version of this index was partial -- WHERE is_active AND
source NOT IN ('simplify', 'ripplematch'), matching the lookup exactly
-- and was never used. Measured by hand with literal values it brought
the query to under 8 ms, which is why it looked right. But the
application sends that NOT IN as bound parameters, and Postgres cannot
prove a partial index's condition against a parameter, so the planner
ignored it: idx_scan did not move across three queue loads. A plain
expression index on the two columns the lookup compares is usable
whatever the rest of the condition is, and brings the load to 0.03 s.

Proved by timing rather than by idx_scan: with the index the queue
loads in 0.03 s and with it dropped 1.1-1.3 s, measured both ways on
the live table. idx_scan read 0 throughout, because the application's
pooled connections do not flush their statistics promptly -- trusting
that counter alone would have concluded the index did nothing and
thrown away the fix.

Revision ID: 0031
Revises: 0030
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0031"

down_revision: str | None = "0030"

branch_labels: str | Sequence[str] | None = None

depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The partial version may already exist from before this was
    # corrected; it is never used, so it is replaced rather than kept.
    op.execute(
        "DROP INDEX IF EXISTS ix_jobs_direct_company_title"
    )

    op.execute(
        "CREATE INDEX ix_jobs_direct_company_title "
        "ON jobs (lower(trim(company)), lower(trim(title)))"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_jobs_direct_company_title"
    )
