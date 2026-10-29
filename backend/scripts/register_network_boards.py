"""Register the employer boards that startup talent networks link to.

    python -m backend.scripts.register_network_boards
    python -m backend.scripts.register_network_boards --apply

Venture firms and accelerators publish their portfolio companies' open
roles, and each role links to the company's own board: Ashby,
Greenhouse, Lever, Workable, Gem. On 2026-10-29 the owner pointed at
a16z's speedrun network and asked for every startup in networks like
it, so new grad roles at startups stop going unseen. The links were
collected once, within each site's robots.txt, into
``backend/app/discovery/network_boards.json``.

A board is read once through the normal adapter before it is trusted,
as feed links are. It is added only when it reads, is not an agency's,
and holds at least one US software, machine learning or forward deployed
role today. A startup hiring engineers in the US is the one that posts
the next new grad role; a board with none would cost requests for
nothing. A board left out is not recorded, so a later run adds it once
it hires. A board the catalog already holds, enabled or not, is never
touched. A board with a role that passes today is polled every fifteen
minutes; the rest hourly, until they produce one (``coverage/cadence``).

Nothing is written without --apply.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
import json
from pathlib import Path
import re
import time

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.benchmark import normalise_company
from backend.app.coverage.companies import (
    NETWORK_DISCOVERY_SOURCE,
    NETWORK_POLL_INTERVAL_SECONDS,
    SOURCE_HOSTS,
    registration_interval,
)
from backend.app.db.models import JobSourceRecord
from backend.app.discovery.detector import (
    DetectedSourceIdentity,
)
from backend.app.discovery.feed_links import (
    NamedBoard,
    board_key,
    is_transient,
    staffing_reason,
)
from backend.app.intelligence.eligibility import (
    EligibilityReasonCode,
    EligibilityStatus,
    evaluate_job,
)
from backend.app.intelligence.roles import (
    RoleFamily,
    classify_role,
)
from backend.app.scheduling.types import (
    SourceDefinition,
    SourceType,
)


DISCOVERY_SOURCE = NETWORK_DISCOVERY_SOURCE

DEFAULT_INPUT = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "discovery"
    / "network_boards.json"
)

TARGET_FAMILIES = frozenset(
    {
        RoleFamily.SOFTWARE_ENGINEERING,
        RoleFamily.AI_ML_ENGINEERING,
        RoleFamily.FORWARD_DEPLOYED_ENGINEERING,
    }
)

# Read a page of twenty at a time, so one tenant is up to a hundred
# requests on a shared edge that also serves employers ACE already
# reads. The networks link them for large public companies, not the
# startups this is for; the feed path registers them a few a run.
PAGED_PROVIDERS = frozenset(
    {
        "workday",
        "oracle_recruiting",
    }
)

# A US engineering role that is still not the trade the owner applies
# to: an internship or a contract says nothing about full-time hiring.
_NOT_FULL_TIME = frozenset(
    {
        EligibilityReasonCode.OUTSIDE_US,
        EligibilityReasonCode.NON_TARGET_ROLE,
        EligibilityReasonCode.INTERNSHIP_ROLE,
        EligibilityReasonCode.CONTRACT_ROLE,
    }
)


# A firm's own board carrying its portfolio's roles: Pear VC's Ashby
# board lists a hundred postings from a dozen companies, and the network
# that linked one of them named the board after that one company.
_FIRM_NAME = re.compile(
    r"\b(?:vc|ventures?|capital|partners|portfolio|talent\s+network)\b",
    re.IGNORECASE,
)


def _same_employer(
    first: str,
    second: str,
) -> bool:
    """One name contains the other, or every word of one is in the other.

    Not merely a shared word: "Blue Apron" is not "Blue Origin".
    """

    left = normalise_company(
        first
    )

    right = normalise_company(
        second
    )

    if not left or not right:
        return True

    squashed_left = left.replace(" ", "")

    squashed_right = right.replace(" ", "")

    left_words = set(left.split())

    right_words = set(right.split())

    return (
        squashed_left in squashed_right
        or squashed_right in squashed_left
        or left_words <= right_words
        or right_words <= left_words
    )


def _initials_of(
    first: str,
    second: str,
) -> bool:
    """Whether one name is the initials of the other's words."""

    for short, long in (
        (first, second),
        (second, first),
    ):
        words = normalise_company(
            long
        ).split()

        if len(words) >= 2 and normalise_company(
            short
        ).replace(" ", "") == "".join(
            word[0]
            for word in words
        ):
            return True

    return False


def settle_name(
    listed: str,
    declared: str | None,
) -> tuple[str, str | None]:
    """The name to register under, or why the board is not one employer.

    The network's name is kept when the board agrees with it or says
    nothing. A board that declares another employer is registered under
    its own name: Greycroft lists Data.ai, whose roles are on Sensor
    Tower's board now. One that declares a venture firm while the network
    named a company is the firm's shared board, and is left out.
    """

    declared = (
        declared or ""
    ).strip()

    if not declared or _same_employer(
        listed,
        declared,
    ):
        return listed, None

    # "ASI" is Air Space Intelligence and "BCC" Black Canyon Consulting:
    # one name is the other's initials, and the longer one says more.
    if _initials_of(
        listed,
        declared,
    ):
        return max(
            listed,
            declared,
            key=len,
        ), None

    if _FIRM_NAME.search(
        declared
    ) and not _FIRM_NAME.search(
        listed
    ):
        return listed, (
            f"shared: a firm's portfolio board, {declared!r}"
        )

    return declared, None


@dataclass(
    frozen=True,
    slots=True,
)
class Candidate:
    """One board a network links to."""

    source_type: str

    source_account: str

    company: str

    source_host: str | None = None

    @property
    def key(
        self,
    ) -> tuple[str, str]:
        return board_key(
            self.source_type,
            self.source_account,
        )

    def definition(
        self,
    ) -> SourceDefinition:
        return SourceDefinition(
            source_type=SourceType(
                self.source_type
            ),
            source_account=self.source_account,
            company_name=self.company,
            enabled=True,
            poll_interval_seconds=registration_interval(
                self.source_type
            ),
            source_host=(
                self.source_host
                or SOURCE_HOSTS.get(
                    self.source_type
                )
            ),
        )


@dataclass(
    frozen=True,
    slots=True,
)
class Outcome:
    """What reading one candidate showed."""

    candidate: Candidate

    added: bool

    reason: str

    jobs: int = 0

    us_engineering: int = 0

    passing: int = 0

    # A 429, a 5xx or a timeout says nothing about the board.
    transient: bool = False


def load_candidates(
    path: Path,
) -> list[Candidate]:
    """Read the collected boards, first company name winning."""

    payload = json.loads(
        path.read_text()
    )

    seen: dict[tuple[str, str], Candidate] = {}

    for row in payload["boards"]:
        candidate = Candidate(
            source_type=row["source_type"],
            source_account=row["source_account"],
            company=(
                row.get("company")
                or row["source_account"]
            ).strip(),
            source_host=row.get("source_host"),
        )

        seen.setdefault(
            candidate.key,
            candidate,
        )

    return list(
        seen.values()
    )


def known_boards(
    session: Session,
) -> set[tuple[str, str]]:
    """Every board the catalog holds, enabled or not."""

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


def assess(
    candidate: Candidate,
    read_board: Callable[[SourceDefinition], Sequence],
    declared_name: Callable[[Candidate], str | None] = (
        lambda candidate: None
    ),
) -> Outcome:
    """Read one board and decide whether it earns a place."""

    try:
        jobs = list(
            read_board(
                candidate.definition()
            )
        )

    except Exception as exc:
        return Outcome(
            candidate=candidate,
            added=False,
            reason=(
                f"unreadable: {type(exc).__name__}: {exc}"
            )[:200],
            transient=is_transient(
                exc
            ),
        )

    if not jobs:
        return Outcome(
            candidate=candidate,
            added=False,
            reason="empty: the board read, but holds nothing",
        )

    named = NamedBoard(
        detected=DetectedSourceIdentity(
            source_type=SourceType(
                candidate.source_type
            ),
            source_account=candidate.source_account,
            source_host=(
                candidate.definition().source_host
                or candidate.source_type
            ),
        ),
        company_name=candidate.company,
    )

    agency = staffing_reason(
        named,
        jobs,
    )

    if agency is not None:
        return Outcome(
            candidate=candidate,
            added=False,
            reason=f"staffing: {agency}",
            jobs=len(jobs),
        )

    # Only a software, machine learning or forward deployed title can
    # count, so only those go through the whole gate: a board of eight
    # hundred postings is otherwise seconds of regular expressions.
    decisions = [
        evaluate_job(
            job
        )
        for job in jobs
        if classify_role(
            job.title
        ).family
        in TARGET_FAMILIES
    ]

    us_engineering = sum(
        1
        for decision in decisions
        if decision.role_family in TARGET_FAMILIES
        and not _NOT_FULL_TIME.intersection(
            decision.reason_codes
        )
    )

    passing = sum(
        1
        for decision in decisions
        if decision.status is EligibilityStatus.PASS
    )

    if not us_engineering and not passing:
        return Outcome(
            candidate=candidate,
            added=False,
            reason="no US software or ML roles today",
            jobs=len(jobs),
        )

    name, shared = settle_name(
        candidate.company,
        declared_name(
            candidate
        ),
    )

    if shared is not None:
        return Outcome(
            candidate=candidate,
            added=False,
            reason=shared,
            jobs=len(jobs),
        )

    if name != candidate.company:
        candidate = Candidate(
            source_type=candidate.source_type,
            source_account=candidate.source_account,
            company=name,
            source_host=candidate.source_host,
        )

    return Outcome(
        candidate=candidate,
        added=True,
        reason="hiring US engineers",
        jobs=len(jobs),
        us_engineering=us_engineering,
        passing=passing,
    )


def register(
    session: Session,
    outcome: Outcome,
    *,
    now: datetime,
) -> bool:
    """Add one confirmed board, unless the catalog gained it meanwhile.

    The caller commits.
    """

    if not outcome.added or outcome.candidate.key in known_boards(
        session
    ):
        return False

    definition = outcome.candidate.definition()

    session.add(
        JobSourceRecord(
            source_type=definition.source_type.value,
            source_account=definition.source_account,
            company_name=definition.company_name,
            source_host=definition.source_host,
            enabled=True,
            # A board already showing a passing role is polled at its
            # provider's cadence; the rest hourly until they produce one.
            poll_interval_seconds=(
                definition.poll_interval_seconds
                if outcome.passing
                else max(
                    definition.poll_interval_seconds,
                    NETWORK_POLL_INTERVAL_SECONDS,
                )
            ),
            discovery_source=DISCOVERY_SOURCE,
            last_verified_at=now,
        )
    )

    session.flush()

    return True


def declared_name(
    candidate: Candidate,
) -> str | None:
    """The employer a board names itself, where its provider says."""

    from backend.app.coverage.probing import (
        board_metadata_name,
        board_page_name,
    )

    try:
        if candidate.source_type == "greenhouse":
            return board_metadata_name(
                source_type="greenhouse",
                token=candidate.source_account,
            )

        if candidate.source_type in ("ashby", "lever"):
            return board_page_name(
                source_type=candidate.source_type,
                token=candidate.source_account,
            )

    except Exception:
        return None

    return None


def main(
    argv: Sequence[str] | None = None,
) -> int:
    from backend.app.db.session import SessionLocal
    from backend.app.scheduling.dispatcher import (
        build_default_source_dispatcher,
    )

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--apply",
        action="store_true",
        help="register the boards found. Without it nothing is written.",
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="read at most this many unknown boards",
    )

    parser.add_argument(
        "--include-paged",
        action="store_true",
        help="also read Workday and Oracle boards (many requests each)",
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=0.5,
        help="seconds between board reads",
    )

    args = parser.parse_args(
        argv
    )

    candidates = load_candidates(
        args.input
    )

    with SessionLocal() as session:
        known = known_boards(
            session
        )

    new = [
        candidate
        for candidate in candidates
        if candidate.key not in known
    ]

    paged = [
        candidate
        for candidate in new
        if candidate.source_type in PAGED_PROVIDERS
    ]

    unknown = [
        candidate
        for candidate in new
        if args.include_paged
        or candidate.source_type not in PAGED_PROVIDERS
    ][
        : args.limit
    ]

    print(
        f"{len(candidates)} boards collected, "
        f"{len(candidates) - len(new)} already in ACE, "
        f"{len(unknown)} to read"
        + (
            ""
            if args.include_paged or not paged
            else f", {len(paged)} Workday or Oracle left for --include-paged"
        )
        + ("" if args.apply else " (dry run: nothing is written)")
    )

    dispatcher = build_default_source_dispatcher()

    # A provider that answered "too many requests" is left for a later run.
    throttled: set[str] = set()

    added = 0

    for candidate in unknown:
        if candidate.source_type in throttled:
            continue

        outcome = assess(
            candidate,
            lambda definition: dispatcher.fetch(
                definition
            ).jobs,
            declared_name,
        )

        if outcome.transient:
            throttled.add(
                candidate.source_type
            )

        if outcome.added and args.apply:
            with SessionLocal.begin() as session:
                if register(
                    session,
                    outcome,
                    now=datetime.now(
                        timezone.utc
                    ),
                ):
                    added += 1

        print(
            f"  {'ADD ' if outcome.added else 'skip'} "
            f"{candidate.company[:28]:28} "
            f"{candidate.source_type:10} "
            f"{candidate.source_account[:28]:28} "
            f"{outcome.jobs:4} jobs "
            f"{outcome.us_engineering:3} US eng "
            f"{outcome.passing:3} pass  "
            f"{outcome.reason}",
            flush=True,
        )

        time.sleep(
            args.pause
        )

    print(
        f"\nregistered {added} boards"
        if args.apply
        else "\nnothing written. Re-run with --apply to register."
    )

    if throttled:
        print(
            "throttled, read again later: "
            + ", ".join(sorted(throttled))
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
