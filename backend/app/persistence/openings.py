"""When a posting opened, judged by the best evidence ACE has.

The user does not want openings that have been up for a month: by then
the role has had its applicants. On 2026-10-06 the pulls were full of
them -- onsemi from June, Trimble from April, QuEra from 2025 -- because
ACE had just started reading those boards, and the first read of a board
brings in everything already on it. ACE shows when it first saw a
posting, so a four-month-old role looked brand new.

Two kinds of evidence, in order of strength:

- **ACE watched it appear.** A posting first seen after ACE's first read
  of its board was not there before; it opened, or reopened, when ACE
  saw it. The employer's own date does not overrule that: Greenhouse
  keeps a reopened role's first publication date, so Anthropic's
  "Product Engineer, Computer Use", back on its board on 2026-09-28,
  says June.
- **The employer's date.** For a board's first read and for the feeds,
  which list other employers' roles, the employer's posted date is all
  there is. A posting with no date at all counts from when ACE first saw
  it: never claimed to be old without evidence.

Measured before applying: 20% of what a first read brings in is already
a month old; of what appears on a board after that, 1%.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
)

from sqlalchemy import (
    and_,
    exists,
    func,
    or_,
)

from backend.app.coverage.companies import (
    MULTI_EMPLOYER_SOURCES,
)
from backend.app.db.models import (
    JobRecord,
    SourceState,
)


# Openings older than this are noise, never deleted: hidden from the
# queue and the pulls, and not counted as arrivals.
OLD_OPENING_DAYS = 30


def opened_within(
    days: int,
    *,
    now: datetime,
):
    """A SQL condition: the posting opened less than ``days`` ago.

    Correlated on ``JobRecord``, so it belongs in a query over jobs.
    """

    cutoff = now - timedelta(
        days=days
    )

    watched_appear = exists().where(
        SourceState.source
        == JobRecord.source,
        SourceState.source_account
        == JobRecord.source_account,
        JobRecord.first_seen_at
        > SourceState.initialized_at,
    )

    return or_(
        func.coalesce(
            JobRecord.posted_at,
            JobRecord.first_seen_at,
        )
        > cutoff,
        and_(
            JobRecord.first_seen_at
            > cutoff,
            JobRecord.source.not_in(
                MULTI_EMPLOYER_SOURCES
            ),
            watched_appear,
        ),
    )
