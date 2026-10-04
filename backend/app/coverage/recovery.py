"""Notice a board that stopped answering, and find where its company went.

A company that moves its jobs to another ATS leaves its old board
answering 404, or answering with nothing. The scheduler logged each
failure and carried on, and nothing else looked: Postman's Greenhouse
board had been gone seventeen days, and Amplitude, Wayve and Iterable
had all moved to Ashby, before anyone noticed. Their new postings were
never read, and their old ones stayed "active" -- so the Coverage page
went on counting all four as reached.

A source is dark once it has gone a day without a successful poll (or
three of its own intervals, for the slow ones). Each dark source's
company is diagnosed again, exactly as the coverage probe does it. If
the company is now on a different board, that board is registered and
the dead one retired, its leftover postings closed so they cannot sit
beside the live copies. If nothing better is found the source is left
alone -- a board answering nothing may be a company with no openings --
and it is listed as dark, which is the part that was missing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.companies import (
    SOURCE_HOSTS,
    registration_interval,
)
from backend.app.coverage.diagnosis import (
    Diagnosis,
    diagnose,
)
from backend.app.db.models import (
    JobSourceRecord,
    SourceState,
)
from backend.app.persistence.repository import (
    JobRepository,
)


DARK_AFTER = timedelta(
    hours=24,
)


# A daily source a few hours late is not dark.
DARK_AFTER_INTERVALS = 3


@dataclass(
    frozen=True,
    slots=True,
)
class DarkSource:
    """An enabled source with no successful poll for too long."""

    source_type: str

    source_account: str

    company_name: str

    # None when it has never once succeeded.
    last_success_at: datetime | None

    dark_since: datetime


@dataclass(
    frozen=True,
    slots=True,
)
class Recovery:
    """What one dark source's diagnosis turned up, and what was done."""

    dark: DarkSource

    diagnosis: Diagnosis

    # The board registered in its place, when the company had moved.
    replaced_by: tuple[str, str] | None

    closed_jobs: int


def _as_utc(
    moment: datetime,
) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(
            tzinfo=timezone.utc,
        )

    return moment


def dark_sources(
    session: Session,
    *,
    now: datetime | None = None,
) -> list[DarkSource]:
    """Enabled sources that have gone too long without answering.

    A source that has never succeeded is counted from when it was
    added, so a board registered an hour ago is not dark yet.
    """

    moment = now or datetime.now(
        timezone.utc,
    )

    rows = session.execute(
        sa.select(
            JobSourceRecord,
            SourceState.last_success_at,
        )
        .outerjoin(
            SourceState,
            sa.and_(
                SourceState.source
                == JobSourceRecord.source_type,
                SourceState.source_account
                == JobSourceRecord.source_account,
            ),
        )
        .where(
            JobSourceRecord.enabled.is_(True),
        )
        .order_by(
            JobSourceRecord.company_name,
        )
    ).all()

    dark: list[DarkSource] = []

    for record, last_success_at in rows:
        since = _as_utc(
            last_success_at
            or record.created_at
        )

        allowed = max(
            DARK_AFTER,
            timedelta(
                seconds=(
                    record.poll_interval_seconds
                    * DARK_AFTER_INTERVALS
                ),
            ),
        )

        if moment - since < allowed:
            continue

        dark.append(
            DarkSource(
                source_type=record.source_type,
                source_account=record.source_account,
                company_name=record.company_name,
                last_success_at=(
                    _as_utc(
                        last_success_at
                    )
                    if last_success_at
                    else None
                ),
                dark_since=since,
            )
        )

    return dark


def _same_board(
    dark: DarkSource,
    source_type: str,
    source_account: str,
) -> bool:
    # Accounts differ in case between lists ("Lightfield" and
    # "lightfield"); the providers do not care, so neither does this.
    return (
        dark.source_type == source_type
        and dark.source_account.lower()
        == source_account.lower()
    )


def recover_dark_sources(
    session: Session,
    *,
    now: datetime | None = None,
    diagnose: Callable[
        [str],
        Diagnosis,
    ] = diagnose,
) -> list[Recovery]:
    """Diagnose every dark source again, and follow any that moved.

    The caller owns the transaction. Nothing here fetches more than the
    coverage probe would for the same company.
    """

    moment = now or datetime.now(
        timezone.utc,
    )

    recoveries: list[Recovery] = []

    for dark in dark_sources(
        session,
        now=moment,
    ):
        diagnosis = diagnose(
            dark.company_name
        )

        candidate = diagnosis.candidate

        if candidate is None or _same_board(
            dark,
            candidate.source_type,
            candidate.source_account,
        ):
            recoveries.append(
                Recovery(
                    dark=dark,
                    diagnosis=diagnosis,
                    replaced_by=None,
                    closed_jobs=0,
                )
            )

            continue

        retired = session.scalar(
            sa.select(
                JobSourceRecord,
            ).where(
                JobSourceRecord.source_type
                == dark.source_type,
                JobSourceRecord.source_account
                == dark.source_account,
            )
        )

        replacement = session.scalar(
            sa.select(
                JobSourceRecord,
            ).where(
                JobSourceRecord.source_type
                == candidate.source_type,
                sa.func.lower(
                    JobSourceRecord.source_account
                )
                == candidate.source_account.lower(),
            )
        )

        if replacement is None:
            session.add(
                JobSourceRecord(
                    source_type=(
                        candidate.source_type
                    ),
                    source_account=(
                        candidate.source_account
                    ),
                    # The name the user already knows this company by,
                    # not whatever the new board calls itself.
                    company_name=(
                        dark.company_name
                    ),
                    source_host=(
                        candidate.source_host
                        or SOURCE_HOSTS.get(
                            candidate.source_type
                        )
                    ),
                    enabled=True,
                    # The old board's cadence, unless the new board's
                    # provider asks for less: a company that moved to
                    # Eightfold is polled as Eightfold boards are.
                    poll_interval_seconds=max(
                        retired.poll_interval_seconds,
                        registration_interval(
                            candidate.source_type
                        ),
                    ),
                    discovery_source=(
                        "dark_source_recovery"
                    ),
                    last_verified_at=moment,
                )
            )

        elif not replacement.enabled:
            replacement.enabled = True

        retired.enabled = False

        # Its postings now arrive from the new board. Left open, each
        # would sit in the queue beside its live copy, pointing at a
        # page that no longer exists.
        closed = JobRepository(
            session,
        ).mark_missing_jobs_inactive(
            source=dark.source_type,
            source_account=dark.source_account,
            observed_external_ids=[],
            observed_at=moment,
        )

        recoveries.append(
            Recovery(
                dark=dark,
                diagnosis=diagnosis,
                replaced_by=(
                    candidate.source_type,
                    candidate.source_account,
                ),
                closed_jobs=closed,
            )
        )

    session.flush()

    return recoveries
