"""Postings the user already applied to, listed again under a new id.

Employers close a posting and open it again: Microsoft re-listed
"Software Engineer" in Redmond under new ids days after the ones the
user had applied to closed, and the same role also arrives from a feed
and from the employer's own board. Each listing is its own job, so the
mark sits on the old one and the new one looks unapplied.

The mark is never copied across. Whether a re-listing is the same
opening is something only the user can know (an employer can have six
open requisitions with one title), and earlier attempts to guess an
identity went wrong. What is derived instead is a notice: this job
resembles one the user applied to, with the date, so the user decides.
It is computed when a page is read and never written, so the applied
list, the counts and the export are unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    JobMarkRecord,
    JobRecord,
)


# Places that name a country rather than a city. A listing that says only
# "US" can be any city, so it is compatible with a specific one.
COUNTRY_ONLY = frozenset(
    {
        "us",
        "usa",
        "u.s.",
        "u.s.a.",
        "united states",
        "united states of america",
    }
)


@dataclass(
    frozen=True,
    slots=True,
)
class AppliedBefore:
    """The most recent earlier application that resembles a job."""

    job_id: int

    title: str

    location: str | None

    applied_at: datetime

    is_active: bool

    # The employer's own number for the opening, when it states one. Two
    # listings with different numbers may be two openings; the same
    # number is the same opening listed again.
    requisition_id: str | None

    # How many earlier applications resemble the job, this one included.
    count: int


def _words(
    text: str | None,
) -> str:
    """Lower case with runs of whitespace collapsed."""

    return re.sub(
        r"\s+",
        " ",
        (text or "").strip().lower(),
    )


def _primary_place(
    location: str | None,
) -> str:
    """The first place named: the city in "Redmond, WA, United States"."""

    return _words(
        re.split(
            r"[,;|]",
            location or "",
            maxsplit=1,
        )[0]
    )


def same_place(
    first: str | None,
    second: str | None,
) -> bool:
    """Whether two locations could be the same opening.

    The same first place, or one of them naming only a country. A remote
    listing and a city listing are different openings, and the same
    title in two cities is two applications, so neither matches.
    """

    one = _primary_place(first)
    two = _primary_place(second)

    if one == two:
        return True

    return (
        one in COUNTRY_ONLY
        or two in COUNTRY_ONLY
    )


def _as_utc(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc,
        )

    return value.astimezone(
        timezone.utc,
    )


def find_applied_before(
    session: Session,
    jobs: Iterable[
        tuple[int, str, str, str | None]
    ],
) -> dict[int, AppliedBefore]:
    """Map job id to the earlier application it resembles, if any.

    ``jobs`` are ``(id, company, title, location)`` for rows the user
    has not marked applied themselves. Matching is exact on company and
    title (ignoring case and spacing) and loose on place, so a looser
    title never produces a false "you applied to this".
    """

    wanted = [
        (
            job_id,
            _words(company),
            _words(title),
            location,
        )
        for job_id, company, title, location in jobs
    ]

    if not wanted:
        return {}

    companies = {
        company
        for _id, company, _title, _loc in wanted
    }

    rows = session.execute(
        select(
            JobRecord.id,
            JobRecord.company,
            JobRecord.title,
            JobRecord.location,
            JobRecord.is_active,
            JobRecord.requisition_id,
            JobMarkRecord.applied_at,
        )
        .join(
            JobMarkRecord,
            JobMarkRecord.job_id
            == JobRecord.id,
        )
        .where(
            JobMarkRecord.applied_at.is_not(
                None
            ),
            func.lower(
                JobRecord.company
            ).in_(
                companies
            ),
        )
    ).all()

    earlier: dict[
        tuple[str, str],
        list,
    ] = {}

    for row in rows:
        earlier.setdefault(
            (
                _words(row.company),
                _words(row.title),
            ),
            [],
        ).append(
            row
        )

    found: dict[
        int,
        AppliedBefore,
    ] = {}

    for job_id, company, title, location in wanted:
        matches = [
            row
            for row in earlier.get(
                (
                    company,
                    title,
                ),
                (),
            )
            if row.id != job_id
            and same_place(
                location,
                row.location,
            )
        ]

        if not matches:
            continue

        latest = max(
            matches,
            key=lambda row: _as_utc(
                row.applied_at
            ),
        )

        found[job_id] = AppliedBefore(
            job_id=latest.id,
            title=latest.title,
            location=latest.location,
            applied_at=_as_utc(
                latest.applied_at
            ),
            is_active=bool(
                latest.is_active
            ),
            requisition_id=latest.requisition_id,
            count=len(
                matches
            ),
        )

    return found
