"""Poll a board as often as what it has produced deserves.

Boards found in bulk -- trackers, the corpus, the long tail of discovery
-- were registered daily, because polling thousands of boards every few
minutes is neither possible nor polite. That was right for a board that
had never produced anything. It stayed the rule after a board started
producing exactly the roles the user wants: an audit on 2026-10-04
found 59 daily boards that had produced passing roles, among them
Amazon, Clera (73), Nuro, Neuralink, Twitch, Discord, Plaid, Replit,
IMC and Jump Trading. A role opened at any of them could wait a day.

A board that has ever produced a role passing the gate is polled at its
provider's registration cadence -- fifteen minutes, or an hour for
Eightfold -- from then on. So is every board on a provider that returns
a whole board in one request (Greenhouse, Ashby, Lever,
SmartRecruiters), productive or not: there a fifteen-minute poll costs
four requests an hour, and waiting for a first passing role meant that
first role waited a day. Duolingo's reached the feed a day before ACE
read it on Duolingo's own board.

Promotion only: a board is never slowed down here, so a cadence someone
set by hand -- Starbucks and Arcadis on Eightfold, every six hours -- is
never undone.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.companies import (
    MULTI_EMPLOYER_SOURCES,
    SINGLE_REQUEST_PROVIDERS,
    productive_interval,
    registration_interval,
)
from backend.app.db.models import (
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
)


@dataclass(
    frozen=True,
    slots=True,
)
class Promotion:
    """One board moved to a faster cadence."""

    source_type: str

    source_account: str

    company_name: str

    old_interval: int

    new_interval: int

    passing_roles: int


def promote_productive_sources(
    session: Session,
) -> list[Promotion]:
    """Speed up every slow board that has produced a passing role.

    The caller owns the transaction.
    """

    productive = (
        sa.select(
            JobRecord.source,
            JobRecord.source_account,
            sa.func.count().label("passing"),
        )
        .join(
            JobEvaluationRecord,
            JobEvaluationRecord.job_id == JobRecord.id,
        )
        .where(
            JobEvaluationRecord.eligibility_status == "PASS",
        )
        .group_by(
            JobRecord.source,
            JobRecord.source_account,
        )
        .subquery()
    )

    rows = session.execute(
        sa.select(
            JobSourceRecord,
            productive.c.passing,
        )
        .outerjoin(
            productive,
            sa.and_(
                productive.c.source
                == JobSourceRecord.source_type,
                productive.c.source_account
                == JobSourceRecord.source_account,
            ),
        )
        .where(
            JobSourceRecord.enabled.is_(True),
            # A feed carries many employers; its cadence is its own.
            JobSourceRecord.source_type.notin_(
                sorted(MULTI_EMPLOYER_SOURCES)
            ),
        )
    ).all()

    promotions: list[Promotion] = []

    for record, passing in rows:
        if passing:
            target = productive_interval(
                record.source_type
            )

        elif (
            record.source_type
            in SINGLE_REQUEST_PROVIDERS
        ):
            target = registration_interval(
                record.source_type
            )

        else:
            continue

        if record.poll_interval_seconds <= target:
            continue

        promotions.append(
            Promotion(
                source_type=record.source_type,
                source_account=record.source_account,
                company_name=record.company_name,
                old_interval=record.poll_interval_seconds,
                new_interval=target,
                passing_roles=int(passing or 0),
            )
        )

        record.poll_interval_seconds = target

    session.flush()

    return promotions
