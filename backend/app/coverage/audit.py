"""ACE's own daily account of what it caught late, and what it cannot see.

The user kept finding roles ACE had missed -- Microsoft, Two Sigma,
Chewy -- and asked for the mistakes to be found and corrected every day,
not one report at a time. A miss is visible in ACE's own data: the
curated feed lists a role, and either ACE never reads that employer's
board, or it read the board and saw the role later than the feed did.

Two lists, both restricted to roles that pass the gate:

- **Caught late.** A role the feed listed before ACE first saw it on the
  employer's own board. Each says why: the board was only added after
  the feed listed the role (a coverage gap, which the half-hourly
  feed-link registration closes), or ACE was already reading the board
  and saw the role late (a slow cadence, or a reader that missed it --
  Amazon's capped reader, Duolingo's daily cadence).
- **Feed only.** Companies whose passing roles reach ACE only through a
  feed: the places direct coverage is still missing.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import sqlalchemy as sa
from sqlalchemy.orm import (
    Session,
    aliased,
)

from backend.app.api.queries import (
    posting_link_key,
)
from backend.app.coverage.benchmark import (
    normalise_company,
)
from backend.app.coverage.companies import (
    MULTI_EMPLOYER_SOURCES,
)
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
)


# Later than this counts as caught late. Below it, the feed and ACE saw
# the role in the same quarter hour, which is not a miss.
LATE_AFTER = timedelta(
    minutes=30,
)

WINDOW = timedelta(
    days=14,
)

BOARD_ADDED_LATER = "board added after the feed listed it"

SEEN_LATE = "board already read; role seen late"

# The employer published the posting -- or published it again -- after
# the feed listed it, and ACE saw it within the half hour. Stripe's
# "Software Engineer" was listed by the feed on 2026-09-18, published on
# Stripe's board on 2026-10-02 at 18:52, and read by ACE at 18:55: not a
# miss, and counting it as one would hide the real ones.
REPUBLISHED = "republished after the feed listed it"


def _as_utc(
    moment: datetime,
) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(
            tzinfo=timezone.utc,
        )

    return moment


def caught_late(
    session: Session,
    *,
    now: datetime | None = None,
    limit: int = 50,
) -> dict:
    """Passing roles a feed listed before ACE saw them at the source."""

    moment = now or datetime.now(
        timezone.utc
    )

    feeds = sorted(
        MULTI_EMPLOYER_SOURCES
    )

    feed = aliased(
        JobRecord
    )

    direct = aliased(
        JobRecord
    )

    board = aliased(
        JobSourceRecord
    )

    same_posting = sa.or_(
        posting_link_key(
            feed.official_url
        )
        == posting_link_key(
            direct.official_url
        ),
        sa.and_(
            sa.func.lower(sa.func.trim(feed.company))
            == sa.func.lower(sa.func.trim(direct.company)),
            sa.func.lower(sa.func.trim(feed.title))
            == sa.func.lower(sa.func.trim(direct.title)),
        ),
    )

    rows = session.execute(
        sa.select(
            direct.id,
            direct.company,
            direct.title,
            direct.official_url,
            direct.first_seen_at,
            sa.func.min(
                feed.first_seen_at
            ),
            board.created_at,
            direct.posted_at,
        )
        .join(
            feed,
            same_posting,
        )
        .join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id == direct.id,
        )
        .outerjoin(
            board,
            sa.and_(
                board.source_type == direct.source,
                board.source_account == direct.source_account,
            ),
        )
        .where(
            direct.source.notin_(feeds),
            feed.source.in_(feeds),
            JobEvaluationRecord.eligibility_status == "PASS",
            direct.first_seen_at >= moment - WINDOW,
        )
        .group_by(
            direct.id,
            direct.company,
            direct.title,
            direct.official_url,
            direct.first_seen_at,
            board.created_at,
            direct.posted_at,
        )
    ).all()

    late: list[dict] = []

    for (
        _job_id,
        company,
        title,
        url,
        direct_seen,
        feed_seen,
        board_added,
        posted_at,
    ) in rows:
        direct_seen = _as_utc(
            direct_seen
        )

        feed_seen = _as_utc(
            feed_seen
        )

        lag = direct_seen - feed_seen

        if lag <= LATE_AFTER:
            continue

        if board_added is not None and _as_utc(
            board_added
        ) > feed_seen:
            cause = BOARD_ADDED_LATER

        elif posted_at is not None and (
            _as_utc(posted_at) > feed_seen
            and direct_seen - _as_utc(posted_at) <= LATE_AFTER
        ):
            cause = REPUBLISHED

        else:
            cause = SEEN_LATE

        late.append(
            {
                "company": company,
                "title": title,
                "official_url": url,
                "feed_seen_at": feed_seen.isoformat(),
                "direct_seen_at": direct_seen.isoformat(),
                "lag_hours": round(
                    lag.total_seconds() / 3600,
                    1,
                ),
                "cause": cause,
            }
        )

    late.sort(
        key=lambda row: row["direct_seen_at"],
        reverse=True,
    )

    return {
        "count": len(late),
        "board_added_later": sum(
            1
            for row in late
            if row["cause"] == BOARD_ADDED_LATER
        ),
        "seen_late": sum(
            1
            for row in late
            if row["cause"] == SEEN_LATE
        ),
        "republished": sum(
            1
            for row in late
            if row["cause"] == REPUBLISHED
        ),
        "rows": late[:limit],
    }


def feed_only(
    session: Session,
    *,
    limit: int = 30,
) -> list[dict]:
    """Companies whose passing roles reach ACE only through a feed.

    A feed role with an active direct copy -- the same link, or the
    same company and title -- is not feed-only; it is the duplicate the
    queue already hides. Ordered by how many passing roles each has.
    """

    feeds = sorted(
        MULTI_EMPLOYER_SOURCES
    )

    feed = aliased(
        JobRecord
    )

    direct = aliased(
        JobRecord
    )

    has_direct_copy = (
        sa.select(
            direct.id,
        )
        .where(
            direct.is_active.is_(True),
            direct.source.notin_(feeds),
            sa.or_(
                posting_link_key(
                    direct.official_url
                )
                == posting_link_key(
                    feed.official_url
                ),
                sa.and_(
                    sa.func.lower(sa.func.trim(direct.company))
                    == sa.func.lower(sa.func.trim(feed.company)),
                    sa.func.lower(sa.func.trim(direct.title))
                    == sa.func.lower(sa.func.trim(feed.title)),
                ),
            ),
        )
        .exists()
    )

    rows = session.execute(
        sa.select(
            feed.company,
            sa.func.count(),
        )
        .join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id == feed.id,
        )
        .where(
            feed.source.in_(feeds),
            feed.is_active.is_(True),
            JobEvaluationRecord.eligibility_status == "PASS",
            ~has_direct_copy,
        )
        .group_by(
            feed.company,
        )
    ).all()

    read_directly = {
        normalise_company(
            name
        )
        for (name,) in session.execute(
            sa.select(
                JobSourceRecord.company_name,
            ).where(
                JobSourceRecord.enabled.is_(True),
                JobSourceRecord.source_type.notin_(feeds),
            )
        ).all()
    }

    merged: dict[str, dict] = {}

    for company, passing in rows:
        key = normalise_company(
            company
        )

        entry = merged.setdefault(
            key,
            {
                "company": company,
                "passing": 0,
                # A board is read but the role is not on it: the
                # reader's miss, not a coverage gap.
                "board_read": key in read_directly,
            },
        )

        entry["passing"] += int(
            passing
        )

    return sorted(
        merged.values(),
        key=lambda entry: (
            -entry["passing"],
            entry["company"].lower(),
        ),
    )[:limit]
