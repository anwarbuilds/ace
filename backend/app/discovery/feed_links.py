"""Register the employer boards that feed postings link to.

A feed posting's link is the employer's own board, so every feed is
also a list of boards to read directly. Turning those links into
sources was a command someone had to remember to run, and nobody had
since early September.

Chewy is what that cost. Two Chewy postings had passed through the feed,
both linking to its Workday board; the coverage probe, trying to find
Chewy's careers site from the name alone, reported "no website
answered". The board was in ACE's own records and never read, and a
Chewy "Software Engineer I" posted on 2026-10-05 was seen by the user
before ACE ever looked.

This runs with the scheduler's maintenance. It collects every board
named by a feed link -- in today's listing and in every feed posting
ACE has ever stored -- and registers the ones ACE does not know at all.
A board is read once through the normal adapter before it is trusted.
A board already in the catalog is never touched, enabled or not: one
switched off by hand (a staffing agency) stays off, and a cadence set
by hand stays set.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
import logging
import re

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.companies import (
    MULTI_EMPLOYER_SOURCES,
    SOURCE_HOSTS,
    registration_interval,
)
from backend.app.db.models import (
    JobRecord,
    JobSourceRecord,
)
from backend.app.discovery.detector import (
    DetectedSourceIdentity,
    detect_source_from_url,
)
from backend.app.scheduling.types import (
    SourceDefinition,
)


LOGGER = logging.getLogger(
    "ace.discovery.feed_links",
)


# Each new board is read in full before it is trusted -- a Workday
# tenant is a hundred requests. Boards whose feed postings could pass for
# the user are all read on every run: Chewy's was 168th in a queue of
# 1,197, and a relevant board must not wait behind a thousand others. The
# rest are read at most this many a run, half an hour apart.
BOARDS_PER_RUN = 40

DISCOVERY_SOURCE = "feed_link"


# A board found through a feed link is not trusted to be an employer's.
# The first automatic run registered nine staffing agencies and job
# aggregators -- Atria Group, Infojini, DellFor, Saxon Global, SA
# Technologies, Testing Xperts, Miracle Software Systems, Proximate,
# Jobs for Humanity -- whose boards repost other companies' roles by the
# hundred, which is the noise the user keeps asking to have cut. All
# nine were on SmartRecruiters.

STAFFING_NAME = re.compile(
    r"\bstaff(?:ing)?\b|\brecruit|\btalent\b|\bconsult|\binfotech\b|"
    r"\bit\s+services\b|\bxperts?\b|\bjobs\s+for\b|\bsoftware\s+systems?\b|"
    r"\bplacement|\bmanpower\b|\bworkforce\b",
    re.IGNORECASE,
)

# Names that are ordinary for an employer but are how most agencies on
# SmartRecruiters style themselves.
SMARTRECRUITERS_AGENCY_NAME = re.compile(
    r"\bglobal\b|\btechnologies\b|\bsolutions\b|\bsystems\b|"
    r"\binc\.?\s*\d|\bllc\b",
    re.IGNORECASE,
)

# The template agencies post in: "Duration: 6-9 Months", "Rate: Open",
# "Client: Direct Client".
STAFFING_TEMPLATE = re.compile(
    r"\b(?:duration|rate|client|interview|end\s+client|contract\s+length)"
    r"\s*:\s|\bc2c\b|\bcorp[\s-]to[\s-]corp\b|\bw-?2\s+(?:only|contract)|"
    r"\bimplementation\s+partner\b|\b(?:our|direct|end)\s+client\b|"
    r"\bimmediate\s+need\b",
    re.IGNORECASE,
)

STAFFING_TEMPLATE_SHARE = 0.2

# Agencies post hundreds of client roles; employers that size have
# usually been found already, by name.
LARGE_SMARTRECRUITERS_BOARD = 300


def staffing_reason(
    board: "NamedBoard",
    jobs: Sequence,
) -> str | None:
    """Why a board looks like an agency's rather than an employer's."""

    name = board.company_name

    if STAFFING_NAME.search(
        name
    ):
        return f"agency name: {name!r}"

    described = [
        job
        for job in jobs
        if len(
            getattr(job, "description", "") or ""
        ) >= 300
    ]

    if len(described) >= 3:
        templated = sum(
            1
            for job in described
            if STAFFING_TEMPLATE.search(
                job.description
            )
        )

        if templated / len(described) >= STAFFING_TEMPLATE_SHARE:
            return (
                f"contract templates in {templated} of "
                f"{len(described)} described postings"
            )

    if board.detected.source_type.value == "smartrecruiters":
        if SMARTRECRUITERS_AGENCY_NAME.search(
            name
        ):
            return f"agency-style name on SmartRecruiters: {name!r}"

        # Size alone is no evidence: Bosch has 4,851 postings there and
        # Western Digital 331, and both were turned away by it. It
        # counts only when no description could be read to judge by.
        if (
            len(described) < 3
            and len(jobs) > LARGE_SMARTRECRUITERS_BOARD
        ):
            return (
                f"{len(jobs)} postings on a SmartRecruiters board, "
                "none described"
            )

    return None


def board_key(
    source_type: str,
    source_account: str,
) -> tuple[str, str]:
    """Two names for one board are one board.

    Accounts compare without case. An Oracle Recruiting tenant serves the
    same requisitions under every career-site number on its host -- BNY's
    CX_1001 and BNY-Careers both list the same 1,367, NOV's CX_4001 and
    CX_2001 the same 687 -- so its key is the host alone. Registering a
    second site of one tenant put every one of those roles in twice.
    """

    account = source_account.strip().lower()

    if source_type == "oracle_recruiting":
        account = account.split(
            "/",
            1,
        )[0]

    return (
        source_type,
        account,
    )


def existing_board(
    session: Session,
    source_type: str,
    source_account: str,
) -> JobSourceRecord | None:
    """The catalog row for this board, under any of its names."""

    wanted = board_key(
        source_type,
        source_account,
    )

    for row in session.scalars(
        sa.select(
            JobSourceRecord,
        ).where(
            JobSourceRecord.source_type == source_type,
        )
    ).all():
        if board_key(
            row.source_type,
            row.source_account,
        ) == wanted:
            return row

    return None


@dataclass(
    frozen=True,
    slots=True,
)
class NamedBoard:
    """A board a feed posting links to, and whose it is."""

    detected: DetectedSourceIdentity

    company_name: str

    @property
    def key(
        self,
    ) -> tuple[str, str]:
        return board_key(
            self.detected.source_type.value,
            self.detected.source_account,
        )


@dataclass(
    frozen=True,
    slots=True,
)
class BoardOutcome:
    """What happened to one board found in a feed link."""

    board: NamedBoard

    registered: bool

    job_count: int = 0

    error: str | None = None


def boards_named_in(
    links: Iterable[tuple[str, str]],
) -> list[NamedBoard]:
    """The distinct readable boards among (url, company) pairs.

    First company name wins, in the order given.
    """

    boards: dict[tuple[str, str], NamedBoard] = {}

    for url, company in links:
        detected = detect_source_from_url(
            url or ""
        )

        if detected is None:
            continue

        board = NamedBoard(
            detected=detected,
            company_name=(
                company or ""
            ).strip()
            or detected.source_account,
        )

        boards.setdefault(
            board.key,
            board,
        )

    return list(
        boards.values()
    )


def stored_feed_links(
    session: Session,
) -> list[tuple[str, str]]:
    """Every link a feed posting ACE has stored ever pointed at."""

    return [
        (
            url,
            company,
        )
        for url, company in session.execute(
            sa.select(
                JobRecord.official_url,
                JobRecord.company,
            )
            .where(
                JobRecord.source.in_(
                    sorted(MULTI_EMPLOYER_SOURCES)
                ),
            )
            .distinct()
        ).all()
    ]


def stored_feed_postings(
    session: Session,
) -> list[tuple[str, str, str]]:
    """(link, company, title) for every feed posting ever stored."""

    return [
        (
            url,
            company,
            title,
        )
        for url, company, title in session.execute(
            sa.select(
                JobRecord.official_url,
                JobRecord.company,
                JobRecord.title,
            )
            .where(
                JobRecord.source.in_(
                    sorted(MULTI_EMPLOYER_SOURCES)
                ),
            )
            .distinct()
        ).all()
    ]


def split_links(
    postings: Iterable[tuple[str, str, str]],
    *,
    could_pass: Callable[[str, str], bool],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Links whose posting could pass for the user, and the rest.

    The first are all read on every run; the rest a few at a time.
    ``could_pass`` takes a company and a title.
    """

    wanted: list[tuple[str, str]] = []

    rest: list[tuple[str, str]] = []

    for url, company, title in postings:
        (
            wanted
            if could_pass(company, title)
            else rest
        ).append(
            (
                url,
                company,
            )
        )

    return wanted, rest


def find_unregistered_boards(
    session: Session,
    links: Sequence[tuple[str, str]],
    *,
    limit: int = BOARDS_PER_RUN,
) -> list[NamedBoard]:
    """Boards feed links name that the catalog has never held.

    Compared without case, and against every row whether enabled or
    not: a board switched off by hand is a decision, not a gap.
    """

    known = _known_boards(
        session
    )

    return [
        board
        for board in boards_named_in(
            links
        )
        if board.key not in known
    ][
        :limit
    ]


def read_boards(
    boards: Sequence[NamedBoard],
    read_board: Callable[[SourceDefinition], Sequence],
) -> list[BoardOutcome]:
    """Read each candidate once through the normal adapter.

    No database session is held while the network is read. Only a board
    that reads, holds something, and does not look like an agency's
    counts as confirmed; the rest are recorded with the reason.
    """

    outcomes: list[BoardOutcome] = []

    for board in boards:
        try:
            jobs = list(
                read_board(
                    _definition(
                        board
                    )
                )
            )

        except Exception as exc:
            outcomes.append(
                BoardOutcome(
                    board=board,
                    registered=False,
                    error=(
                        f"unreadable: {type(exc).__name__}: {exc}"
                    )[:300],
                )
            )

            continue

        if not jobs:
            outcomes.append(
                BoardOutcome(
                    board=board,
                    registered=False,
                    error="empty: the board read, but holds nothing",
                )
            )

            continue

        reason = staffing_reason(
            board,
            jobs,
        )

        if reason is not None:
            outcomes.append(
                BoardOutcome(
                    board=board,
                    registered=False,
                    job_count=len(jobs),
                    error=f"staffing: {reason}",
                )
            )

            continue

        outcomes.append(
            BoardOutcome(
                board=board,
                registered=True,
                job_count=len(jobs),
            )
        )

    return outcomes


def register_confirmed_boards(
    session: Session,
    outcomes: Sequence[BoardOutcome],
    *,
    now: datetime | None = None,
) -> list[BoardOutcome]:
    """Add the read boards to the catalog. The caller commits.

    A confirmed board is added switched on. One that could not be read,
    held nothing, or looked like an agency is added switched off, its
    reason in ``discovery_source`` -- so it is not read again every half
    hour, cannot crowd new boards out of a run, and a person can see why
    and switch it on. Checked against the catalog again, since the
    boards were read outside any transaction.

    Returns the boards added switched on.
    """

    moment = now or datetime.now(
        timezone.utc
    )

    known = _known_boards(
        session
    )

    added: list[BoardOutcome] = []

    for outcome in outcomes:
        if outcome.board.key in known:
            continue

        definition = _definition(
            outcome.board
        )

        session.add(
            JobSourceRecord(
                source_type=definition.source_type.value,
                source_account=definition.source_account,
                company_name=definition.company_name,
                source_host=definition.source_host,
                enabled=outcome.registered,
                poll_interval_seconds=(
                    definition.poll_interval_seconds
                ),
                discovery_source=(
                    DISCOVERY_SOURCE
                    if outcome.registered
                    # The column holds 100 characters.
                    else (
                        f"{DISCOVERY_SOURCE} rejected: "
                        f"{outcome.error}"
                    )[:100]
                ),
                last_verified_at=moment,
            )
        )

        known.add(
            outcome.board.key
        )

        if outcome.registered:
            added.append(
                outcome
            )

    session.flush()

    return added


def _known_boards(
    session: Session,
) -> set[tuple[str, str]]:
    return {
        board_key(
            source_type,
            source_account,
        )
        for source_type, source_account in session.execute(
            sa.select(
                JobSourceRecord.source_type,
                JobSourceRecord.source_account,
            )
        ).all()
    }


def _definition(
    board: NamedBoard,
) -> SourceDefinition:
    detected = board.detected

    return SourceDefinition(
        source_type=detected.source_type,
        source_account=detected.source_account,
        company_name=board.company_name,
        enabled=True,
        poll_interval_seconds=registration_interval(
            detected.source_type.value
        ),
        source_host=(
            detected.source_host
            or SOURCE_HOSTS.get(
                detected.source_type.value
            )
        ),
    )
