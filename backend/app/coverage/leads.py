"""A lasting record of every employer ACE has heard of.

ACE learned names from its own list, startup networks, feeds and searches,
then kept only the boards it registered. Everything else was a one-time
result: a network board with no US software role on the day it was read was
dropped, and a company a probe could not reach kept that answer with nothing
due to look again.

Each lead here has a state, a reason, the last check and the next check.
``sync_leads`` writes what ACE already knows, without a single request, and
``check_due_leads`` looks again at what is due, a few at a time.

Evidence only. A check that finds a board hiring US engineers moves the lead
to "waiting" for the owner. Nothing here registers a board.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import re
import time

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.benchmark import normalise_company
from backend.app.coverage.companies import (
    MULTI_EMPLOYER_SOURCES,
    TARGET_COMPANIES,
    is_namesake,
)
from backend.app.coverage.host_policy import (
    HostTarget,
    read_targets,
    refusal_for,
)
from backend.app.coverage.recovery import dark_sources
from backend.app.db.models import (
    EmployerLead,
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
    SourceProbeRecord,
    SourceState,
)
from backend.app.discovery.feed_links import board_key


LOGGER = logging.getLogger("ace.coverage.leads")

POLLING = "polling"
WAITING = "waiting"
CHECKING = "checking"
DORMANT = "dormant"
NOREADER = "noreader"
REFUSED = "refused"
AGENCY = "agency"

STATES = (POLLING, WAITING, CHECKING, DORMANT, NOREADER, REFUSED, AGENCY)

STATE_LABELS = {
    POLLING: "ace reads it",
    WAITING: "Waiting for you",
    CHECKING: "Being checked",
    DORMANT: "No US software jobs",
    NOREADER: "Can't read yet",
    REFUSED: "Site says no",
    AGENCY: "Staffing agency",
}

# Said once on the page, for anyone wondering what a status means.
STATE_MEANINGS = {
    POLLING: "ace reads this company all day. You will find it under Sources.",
    WAITING: "ace found a good board, and adding it needs your approval.",
    CHECKING: "ace has not looked yet, or will try again soon.",
    DORMANT: "The board reads fine, with no US software jobs today. ace looks again every week.",
    NOREADER: "They use a site ace has no reader for, or no board was found. ace looks again every month.",
    REFUSED: "The site asks automated readers to stay off. ace respects that. Check it by hand.",
    AGENCY: "Not an employer, so ace leaves it out.",
}

# How long a state lasts before ACE looks again. New grad roles open in
# waves, so a board with nothing today is read again soon. A polling lead is
# read by the scheduler all day; this is the ledger re-reading the catalog.
RECHECK_AFTER = {
    POLLING: timedelta(days=1),
    WAITING: timedelta(days=7),
    CHECKING: timedelta(days=1),
    DORMANT: timedelta(days=7),
    NOREADER: timedelta(days=30),
    REFUSED: timedelta(days=30),
    AGENCY: timedelta(days=90),
}

OWNER = "owner"
CURATED = "curated"
NETWORK = "network"
FEED = "feed"
SEARCH = "search"

# Strongest first: the one "Lead from" names when a lead has several.
ORIGINS = (OWNER, CURATED, NETWORK, FEED, SEARCH)

ORIGIN_LABELS = {
    OWNER: "Added by you",
    CURATED: "Your list",
    NETWORK: "City network",
    FEED: "New grad list",
    SEARCH: "ace search",
}

ORIGIN_NOTES = {
    OWNER: "Links and names you added",
    CURATED: "The companies you chose",
    NETWORK: "Lists of startups, collected once",
    FEED: "Names in the public lists ace reads",
    SEARCH: "Found by ace's earlier company searches",
}

DEFAULT_NETWORK_FILE = Path(__file__).resolve().parents[1] / "discovery" / "network_boards.json"

# What one maintenance run may do. Reading a whole board is one request on
# most platforms and up to a hundred on the paged ones, and looking for a
# company by name is many.
BOARDS_PER_RUN = 40
PAGED_PER_RUN = 2
NAMES_PER_RUN = 5
SECONDS_PER_RUN = 600.0
PAUSE_SECONDS = 0.5
BOARDS_PER_LEAD = 3
MAX_ORIGIN_DETAILS = 12

PAGED_PROVIDERS = frozenset({"workday", "oracle_recruiting"})

# The discovery_source of a board the owner added and then took back.
UNDONE = "added_by_hand undone"

_STAFFING = re.compile(r"rejected: staffing(?: agency)?:?\s*(.*)", re.IGNORECASE | re.DOTALL)

_DASHES = re.compile(r"\s*(?:--|—|–)\s*")

# What a probe found, as a ledger state. A board that names someone else is
# not a site refusing ACE, so it reads "No reader yet" and the reason says it.
_PROBE_STATES = {
    "other_ats": NOREADER,
    "no_board_found": NOREADER,
    "site_unreachable": NOREADER,
    "refused": NOREADER,
    "blocked": REFUSED,
    "no_postings": DORMANT,
}


def _clean(text: str | None) -> str:
    return _DASHES.sub(", ", (text or "").strip())


# The interface's own voice: the wordmark is lowercase, and probe details and
# stored reasons were written with the name in capitals.
def voice(text: str | None) -> str:
    return re.sub(r"\bACE\b", "ace", text or "")


def _aware(value: datetime | None) -> datetime | None:
    # SQLite hands back naive values for what PostgreSQL stores with a zone.
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


_BOARD_LABELS = {
    "greenhouse": "Greenhouse",
    "ashby": "Ashby",
    "lever": "Lever",
    "smartrecruiters": "SmartRecruiters",
    "workable": "Workable",
    "workday": "Workday",
    "oracle_recruiting": "Oracle",
    "gem": "Gem",
    "eightfold": "Eightfold",
    "eightfold_pcsx": "Eightfold",
    "jibe": "iCIMS Jibe",
    "avature": "Avature",
    "jobposting_sitemap": "careers site",
}


def _platform(source_type: str) -> str:
    return _BOARD_LABELS.get(source_type, source_type.replace("_", " ").title())


def _origin_of(discovery_source: str | None) -> str:
    text = (discovery_source or "").lower()
    if text.startswith(("manual", "added_by_hand", "user_reported")):
        return OWNER
    if text.startswith("curated"):
        return CURATED
    if text.startswith("talent_network"):
        return NETWORK
    if text.startswith(("feed_link", "simplify")):
        return FEED
    return SEARCH


def _board(source_type: str, source_account: str, source_host: str | None) -> dict:
    return {
        "source_type": source_type,
        "source_account": source_account,
        "source_host": source_host,
    }


@dataclass(slots=True)
class Evidence:
    """Everything ACE knows about one employer, gathered without a request."""

    name: str = ""
    name_rank: int = 99
    details: set[str] = field(default_factory=set)
    boards: dict[tuple[str, str], dict] = field(default_factory=dict)
    agency: str = ""
    probe: SourceProbeRecord | None = None
    owner_added: datetime | None = None

    def named(self, name: str, rank: int) -> None:
        if rank < self.name_rank and name.strip():
            self.name = name.strip()[:255]
            self.name_rank = rank

    def origin(self) -> str:
        for origin in ORIGINS:
            if any(detail.split(":", 1)[0] == origin for detail in self.details):
                return origin
        return SEARCH


def gather_evidence(
    session: Session,
    *,
    network_file: Path = DEFAULT_NETWORK_FILE,
) -> dict[str, Evidence]:
    """Every employer ACE knows of, from what it already holds."""

    evidence: dict[str, Evidence] = {}

    def entry(name: str | None) -> tuple[str, Evidence] | None:
        key = normalise_company(name)[:255]
        if not key:
            return None
        return key, evidence.setdefault(key, Evidence())

    for name in TARGET_COMPANIES:
        found = entry(name)
        if found:
            found[1].named(name, 0)
            found[1].details.add(CURATED)

    for row in session.execute(
        sa.select(
            JobSourceRecord.source_type,
            JobSourceRecord.source_account,
            JobSourceRecord.source_host,
            JobSourceRecord.company_name,
            JobSourceRecord.enabled,
            JobSourceRecord.discovery_source,
            JobSourceRecord.first_discovered_at,
        )
    ):
        # A feed is where names come from, not an employer.
        if row.source_type in MULTI_EMPLOYER_SOURCES:
            continue

        # A retired copy of a board that has its own row, or a board the
        # owner took back: neither is evidence, and neither comes back.
        kind = (row.discovery_source or "").lower()
        if kind.startswith("duplicate of") or kind == UNDONE:
            continue

        found = entry(row.company_name)
        if not found:
            continue

        lead = found[1]
        lead.named(row.company_name, 1 if row.enabled else 3)
        lead.details.add(_origin_of(row.discovery_source))

        if kind.startswith(("added_by_hand", "user_reported")):
            lead.owner_added = _aware(row.first_discovered_at)

        staffing = _STAFFING.search(row.discovery_source or "")
        if staffing and not row.enabled:
            detail = _clean(staffing.group(1)).strip(" ()")
            lead.agency = f"Staffing firm: {detail}." if detail else "Staffing firm."
            continue

        if is_namesake(row.source_type, row.source_account):
            continue

        lead.boards[board_key(row.source_type, row.source_account)] = _board(
            row.source_type,
            row.source_account,
            row.source_host,
        )

    for probe in session.scalars(sa.select(SourceProbeRecord)):
        key = (probe.company_key or "")[:255]
        if not key:
            continue
        lead = evidence.setdefault(key, Evidence())
        lead.named(probe.company_name, 4)
        lead.details.add(SEARCH)
        lead.probe = probe
        if (
            probe.source_type
            and probe.source_account
            and probe.source_type not in PAGED_PROVIDERS
            and not is_namesake(probe.source_type, probe.source_account)
        ):
            lead.boards.setdefault(
                board_key(probe.source_type, probe.source_account),
                _board(probe.source_type, probe.source_account, None),
            )

    if network_file.exists():
        for row in json.loads(network_file.read_text())["boards"]:
            found = entry(row.get("company") or row["source_account"])
            if not found:
                continue
            lead = found[1]
            lead.named(row.get("company") or row["source_account"], 2)
            networks = row.get("networks") or []
            lead.details.update(f"{NETWORK}:{name}" for name in networks[:4])
            lead.details.add(NETWORK)
            if not is_namesake(row["source_type"], row["source_account"]):
                lead.boards.setdefault(
                    board_key(row["source_type"], row["source_account"]),
                    _board(row["source_type"], row["source_account"], row.get("source_host")),
                )

    for company, source in session.execute(
        sa.select(JobRecord.company, JobRecord.source)
        .where(
            JobRecord.source.in_(sorted(MULTI_EMPLOYER_SOURCES)),
            JobRecord.is_active.is_(True),
        )
        .distinct()
    ):
        found = entry(company)
        if found:
            found[1].named(company, 5)
            found[1].details.add(f"{FEED}:{source}")

    return evidence


def _polling_reason(platforms: list[str], dark: bool) -> str:
    names = sorted(set(platforms))
    if len(platforms) == 1:
        text = f"Reads its {names[0]} board"
    elif len(names) == 1:
        text = f"Reads {len(platforms)} {names[0]} boards"
    else:
        text = f"Reads {len(platforms)} boards on " + " and ".join((", ".join(names[:-1]), names[-1]))
    return text + (", but one has stopped answering." if dark else ".")


def _seed(lead: Evidence, now: datetime) -> tuple[str, str, datetime | None, datetime]:
    """A new lead's first state, from what ACE already knows."""

    if lead.agency:
        return AGENCY, lead.agency, None, now + RECHECK_AFTER[AGENCY]

    probe = lead.probe

    if probe is not None and probe.outcome == "blocked":
        checked = _aware(probe.checked_at) or now
        return REFUSED, _clean(probe.detail), checked, checked + RECHECK_AFTER[REFUSED]

    if lead.boards:
        return CHECKING, "Has a board ACE has not read yet.", None, now

    if probe is not None and probe.outcome in _PROBE_STATES:
        state = _PROBE_STATES[probe.outcome]
        checked = _aware(probe.checked_at) or now
        return state, _clean(probe.detail), checked, checked + RECHECK_AFTER[state]

    return CHECKING, "Not looked at yet.", None, now


@dataclass(frozen=True, slots=True)
class SyncSummary:
    total: int
    created: int
    changed: int


def sync_leads(
    session: Session,
    *,
    now: datetime,
    network_file: Path = DEFAULT_NETWORK_FILE,
) -> SyncSummary:
    """Write what ACE already knows into the ledger. Makes no request.

    A lead whose evidence goes away keeps its row: the record is meant to
    last, and a feed dropping a name does not mean the company stopped hiring.
    """

    evidence = gather_evidence(session, network_file=network_file)

    catalog = {
        board_key(row.source_type, row.source_account): row
        for row in session.execute(
            sa.select(
                JobSourceRecord.source_type,
                JobSourceRecord.source_account,
                JobSourceRecord.enabled,
            )
        )
    }

    enabled = {key for key, row in catalog.items() if row.enabled and key[0] not in MULTI_EMPLOYER_SOURCES}

    last_success: dict[tuple[str, str], datetime] = {}

    for source, account, success in session.execute(
        sa.select(SourceState.source, SourceState.source_account, SourceState.last_success_at)
    ):
        last_success[board_key(source, account)] = _aware(success)

    dark = {board_key(item.source_type, item.source_account) for item in dark_sources(session, now=now)}

    rows = {row.company_key: row for row in session.scalars(sa.select(EmployerLead))}

    created = 0
    changed = 0

    for key, lead in evidence.items():
        row = rows.get(key)

        if row is None:
            state, reason, checked, next_check = _seed(lead, now)
            row = EmployerLead(
                company_key=key,
                company_name=lead.name or key[:255],
                origin=lead.origin(),
                origin_details=sorted(lead.details)[:MAX_ORIGIN_DETAILS],
                state=state,
                reason=reason,
                boards=list(lead.boards.values()),
                first_seen_at=now,
                last_checked_at=checked,
                owner_added_at=lead.owner_added,
                next_check_at=next_check,
                updated_at=now,
            )
            session.add(row)
            created += 1
        else:
            before = (row.origin, list(row.origin_details or []), row.state, row.reason)

            details = sorted(set(row.origin_details or []) | lead.details)[:MAX_ORIGIN_DETAILS]
            if details != list(row.origin_details or []):
                row.origin_details = details

            origin = lead.origin()
            if ORIGINS.index(origin) < ORIGINS.index(row.origin if row.origin in ORIGINS else SEARCH):
                row.origin = origin

            known = {board_key(b["source_type"], b["source_account"]): b for b in row.boards or []}
            added = {k: b for k, b in lead.boards.items() if k not in known}
            if added:
                row.boards = list(known.values()) + list(added.values())

            if lead.owner_added is not None and row.owner_added_at is None:
                row.owner_added_at = lead.owner_added

            if tuple(before) != (row.origin, list(row.origin_details or []), row.state, row.reason):
                changed += 1

    session.flush()

    # A second pass, so a board found under another name still counts: a
    # network that lists one employer can point at a board registered under
    # the name the board itself declares.
    for row in session.scalars(sa.select(EmployerLead)):
        reading = [
            (board_key(b["source_type"], b["source_account"]), b)
            for b in row.boards or []
            if board_key(b["source_type"], b["source_account"]) in enabled
        ]

        lead = evidence.get(row.company_key)

        if reading:
            if row.state != POLLING or _aware(row.next_check_at) <= now:
                keys = [key for key, _ in reading]
                seen = [last_success[key] for key in keys if key in last_success]
                row.state = POLLING
                row.reason = _polling_reason(
                    [_platform(b["source_type"]) for _, b in reading],
                    any(key in dark for key in keys),
                )
                row.last_checked_at = max(seen) if seen else row.last_checked_at
                row.next_check_at = now + RECHECK_AFTER[POLLING]
                row.check_failures = 0
                changed += 1
            continue

        if row.state == POLLING:
            if lead is not None and lead.agency:
                row.state = AGENCY
                row.reason = lead.agency
                row.next_check_at = now + RECHECK_AFTER[AGENCY]
            else:
                row.state = CHECKING
                row.reason = "Its board was switched off, so ACE looks again."
                row.next_check_at = now
            changed += 1
        elif lead is not None and lead.agency and row.state != AGENCY:
            row.state = AGENCY
            row.reason = lead.agency
            row.next_check_at = now + RECHECK_AFTER[AGENCY]
            changed += 1

    session.flush()

    return SyncSummary(total=len(rows) + created, created=created, changed=changed)


@dataclass(frozen=True, slots=True)
class Finding:
    """What one check showed."""

    state: str
    reason: str
    # A busy provider says nothing about the employer: keep what was known.
    transient: bool = False
    # The board itself is gone: look for the company by name next time.
    gone: bool = False


def finding_from(outcome, board: dict) -> Finding:
    """Read what ``register_network_boards.assess`` decided about a board."""

    platform = _platform(board["source_type"])
    reason = outcome.reason or ""

    if outcome.added:
        roles = outcome.us_engineering or outcome.passing
        noun = "role" if roles == 1 else "roles"
        return Finding(
            WAITING,
            f"{platform} board reads, with {roles} US software {noun} today, "
            f"{outcome.passing} passing your filters. Waiting for your approval.",
        )

    if reason.startswith("no US software"):
        return Finding(DORMANT, f"{platform} board read, no US software role today.")

    if reason.startswith("empty"):
        return Finding(DORMANT, f"{platform} board reads, but holds nothing today.")

    if reason.startswith("staffing:"):
        return Finding(AGENCY, f"Staffing firm: {_clean(reason.split(':', 1)[1])}.")

    if reason.startswith("shared:"):
        return Finding(AGENCY, "A firm's shared portfolio board, not one employer.")

    if outcome.transient:
        return Finding(CHECKING, f"Could not read its {platform} board today. Will try again.", transient=True)

    return Finding(CHECKING, f"Its {platform} board no longer answers.", gone=True)


# A busy board is tried again sooner, and a persistent failure less often.
def _backoff(failures: int) -> timedelta:
    return timedelta(days=min(2 ** max(failures - 1, 0), 14))


# When a lead has several boards, the best news wins.
_RANK = {WAITING: 0, DORMANT: 1, CHECKING: 2, NOREADER: 3, AGENCY: 4, REFUSED: 5}


def _record(row: EmployerLead, finding: Finding, now: datetime) -> None:
    if finding.transient:
        row.check_failures = (row.check_failures or 0) + 1
        row.next_check_at = now + _backoff(row.check_failures)
        if row.state == CHECKING:
            row.reason = finding.reason
        return

    row.state = finding.state
    row.reason = finding.reason
    row.check_failures = 0
    row.last_checked_at = now
    row.next_check_at = now + RECHECK_AFTER[finding.state]


@dataclass(slots=True)
class CheckSummary:
    boards: int = 0
    names: int = 0
    refused: int = 0
    deferred: int = 0
    stopped_early: bool = False
    states: dict[str, int] = field(default_factory=dict)


def check_due_leads(
    sessions,
    *,
    now: Callable[[], datetime],
    assess_board: Callable[[dict, str], object],
    diagnose_name: Callable[[str], object],
    refusal: Callable[..., str | None] = refusal_for,
    boards_per_run: int = BOARDS_PER_RUN,
    paged_per_run: int = PAGED_PER_RUN,
    names_per_run: int = NAMES_PER_RUN,
    seconds: float = SECONDS_PER_RUN,
    pause: Callable[[float], None] = time.sleep,
) -> CheckSummary:
    """Look again at the leads that are due, oldest first.

    Each is saved as soon as it is read, so a restart loses nothing. A lead
    the budget does not reach stays due and goes first next time. A provider
    that answers "not now" is left alone for the rest of the run.
    """

    summary = CheckSummary()

    with sessions() as session:
        # Every due lead, not the oldest few: name searches and board reads
        # have separate budgets, so a long line of old name-only leads must
        # not keep boards that are one request away from being read.
        due = [
            (row.id, row.company_name, list(row.boards or []))
            for row in session.execute(
                sa.select(EmployerLead.id, EmployerLead.company_name, EmployerLead.boards)
                .where(
                    EmployerLead.state != POLLING,
                    EmployerLead.next_check_at <= now(),
                )
                .order_by(EmployerLead.next_check_at, EmployerLead.id)
            )
        ]

    started = time.monotonic()

    throttled: set[str] = set()

    paged_used = 0

    for lead_id, company, boards in due:
        if time.monotonic() - started > seconds:
            summary.stopped_early = True
            break

        live = [board for board in boards if not board.get("gone")][:BOARDS_PER_LEAD]

        if live:
            if summary.boards >= boards_per_run:
                continue

            if any(board["source_type"] in throttled for board in live):
                summary.deferred += 1
                continue

            is_paged = any(board["source_type"] in PAGED_PROVIDERS for board in live)

            if is_paged and paged_used >= paged_per_run:
                continue

            if is_paged:
                paged_used += 1

            summary.boards += 1

            _check_boards(
                sessions,
                lead_id,
                company,
                live,
                now=now,
                assess_board=assess_board,
                refusal=refusal,
                throttled=throttled,
                summary=summary,
            )

            pause(PAUSE_SECONDS)
            continue

        if summary.names >= names_per_run:
            continue

        summary.names += 1

        _check_name(
            sessions,
            lead_id,
            company,
            now=now,
            diagnose_name=diagnose_name,
            summary=summary,
        )

        pause(PAUSE_SECONDS)

    return summary


def _check_boards(
    sessions,
    lead_id: int,
    company: str,
    live: list[dict],
    *,
    now,
    assess_board,
    refusal,
    throttled: set[str],
    summary: CheckSummary,
) -> None:
    findings: list[Finding] = []

    gone: set[tuple[str, str]] = set()

    for board in live:
        targets: tuple[HostTarget, ...] = read_targets(
            board["source_type"],
            board["source_account"],
            board.get("source_host"),
        )

        if not targets:
            gone.add(board_key(board["source_type"], board["source_account"]))
            findings.append(Finding(CHECKING, "ACE cannot tell where this board lives.", gone=True))
            continue

        with sessions.begin() as session:
            why = next(
                (
                    reason
                    for reason in (refusal(session, target, now=now()) for target in targets)
                    if reason
                ),
                None,
            )

        if why:
            summary.refused += 1
            findings.append(Finding(REFUSED, why))
            continue

        try:
            outcome = assess_board(board, company)
        except Exception as exc:  # A read must never take the maintenance down.
            LOGGER.warning(
                "lead_board_read_failed source=%s/%s error=%s",
                board["source_type"],
                board["source_account"],
                type(exc).__name__,
            )
            findings.append(Finding(CHECKING, "Could not read this board today. Will try again.", transient=True))
            continue

        finding = finding_from(outcome, board)

        if finding.transient:
            throttled.add(board["source_type"])

        if finding.gone:
            gone.add(board_key(board["source_type"], board["source_account"]))

        findings.append(finding)

    if not findings:
        return

    best = min(findings, key=lambda item: (item.transient, _RANK.get(item.state, 9)))

    with sessions.begin() as session:
        row = session.get(EmployerLead, lead_id)

        if row is None:
            return

        if gone:
            row.boards = [
                {**b, "gone": True} if board_key(b["source_type"], b["source_account"]) in gone else b
                for b in row.boards or []
            ]

        _record(row, best, now())

        summary.states[row.state] = summary.states.get(row.state, 0) + 1


def _check_name(
    sessions,
    lead_id: int,
    company: str,
    *,
    now,
    diagnose_name,
    summary: CheckSummary,
) -> None:
    try:
        diagnosis = diagnose_name(company)
    except Exception as exc:  # A read must never take the maintenance down.
        LOGGER.warning("lead_name_check_failed error=%s", type(exc).__name__)
        with sessions.begin() as session:
            row = session.get(EmployerLead, lead_id)
            if row is not None:
                _record(row, Finding(CHECKING, "Could not finish looking today. Will try again.", transient=True), now())
        return

    with sessions.begin() as session:
        row = session.get(EmployerLead, lead_id)

        if row is None:
            return

        candidate = getattr(diagnosis, "candidate", None)

        moment = now()

        if diagnosis.outcome == "reached" and candidate is not None:
            board = _board(candidate.source_type, candidate.source_account, candidate.source_host)
            known = {board_key(b["source_type"], b["source_account"]) for b in row.boards or []}
            if board_key(candidate.source_type, candidate.source_account) not in known:
                row.boards = list(row.boards or []) + [board]
            row.state = CHECKING
            row.reason = "Found a board that names this company. ACE reads it next."
            row.last_checked_at = moment
            row.check_failures = 0
            # The board is read on the next run, through the same checks as
            # every other board.
            row.next_check_at = moment
        else:
            state = _PROBE_STATES.get(diagnosis.outcome, NOREADER)
            _record(row, Finding(state, _clean(diagnosis.detail)), moment)

        summary.states[row.state] = summary.states.get(row.state, 0) + 1

        # The Coverage page's "Cannot reach" reads the same answer.
        probe = session.scalar(
            sa.select(SourceProbeRecord).where(SourceProbeRecord.company_key == row.company_key)
        )
        if probe is None:
            probe = SourceProbeRecord(company_key=row.company_key)
            session.add(probe)
        probe.company_name = row.company_name
        probe.outcome = diagnosis.outcome
        probe.detail = diagnosis.detail or ""
        probe.source_type = candidate.source_type if candidate is not None else None
        probe.source_account = candidate.source_account if candidate is not None else None
        probe.checked_at = moment


def remember_added(
    session: Session,
    *,
    company: str,
    state: str,
    reason: str,
    now: datetime,
    board: dict | None = None,
) -> EmployerLead | None:
    """Record what the owner just added, whatever became of it.

    The caller commits. A name that reduces to nothing has no lead.
    """

    key = normalise_company(company)[:255]

    if not key:
        return None

    row = session.scalar(sa.select(EmployerLead).where(EmployerLead.company_key == key))

    if row is None:
        row = EmployerLead(
            company_key=key,
            company_name=company.strip()[:255],
            origin=OWNER,
            origin_details=[OWNER],
            state=state,
            reason=reason,
            boards=[],
            first_seen_at=now,
            next_check_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.origin = OWNER
        row.origin_details = sorted(set(row.origin_details or []) | {OWNER})[:MAX_ORIGIN_DETAILS]

    if board is not None:
        known = {board_key(b["source_type"], b["source_account"]) for b in row.boards or []}
        if board_key(board["source_type"], board["source_account"]) not in known:
            row.boards = list(row.boards or []) + [board]

    row.owner_added_at = now
    row.state = state
    row.reason = reason
    row.check_failures = 0
    row.last_checked_at = now
    row.next_check_at = now + RECHECK_AFTER[state]

    session.flush()

    return row


def forget_added(session: Session, *, company: str) -> None:
    """Take back what ``remember_added`` wrote. The caller commits.

    A lead ACE also heard of elsewhere stays, as it was going to anyway.
    """

    key = normalise_company(company)[:255]

    row = session.scalar(sa.select(EmployerLead).where(EmployerLead.company_key == key))

    if row is None:
        return

    others = [detail for detail in row.origin_details or [] if detail != OWNER]

    if not others:
        session.delete(row)
        return

    row.owner_added_at = None
    row.origin_details = others
    row.origin = next(
        (origin for origin in ORIGINS if any(detail.split(":", 1)[0] == origin for detail in others)),
        SEARCH,
    )
    row.state = CHECKING
    row.reason = "You took this board back, so ace only keeps the company on record."
    row.boards = []
    row.next_check_at = row.next_check_at


_LIST_ORDER = sa.case(
    {WAITING: 0, REFUSED: 1, NOREADER: 2, CHECKING: 3, DORMANT: 4, AGENCY: 5, POLLING: 6},
    value=EmployerLead.state,
    else_=9,
)


def _like(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def added_report(session: Session, *, limit: int = 25) -> list[dict]:
    """What the owner added, newest first, and where each one is now."""

    rows = list(
        session.scalars(
            sa.select(EmployerLead)
            .where(EmployerLead.owner_added_at.is_not(None))
            .order_by(EmployerLead.owner_added_at.desc(), EmployerLead.id.desc())
            .limit(limit)
        )
    )

    out = []

    for row in rows:
        boards = [(b["source_type"], b["source_account"]) for b in row.boards or []]

        last_read = None
        jobs = 0
        passing = 0

        if row.state == POLLING and boards:
            for source_type, account in boards:
                state = session.get(SourceState, (source_type, account))
                if state is not None:
                    seen = _aware(state.last_success_at)
                    last_read = max(last_read, seen) if last_read else seen
                    jobs += state.last_job_count or 0
                passing += session.scalar(
                    sa.select(sa.func.count())
                    .select_from(JobRecord)
                    .join(JobEvaluationRecord, JobEvaluationRecord.job_id == JobRecord.id)
                    .where(
                        JobRecord.source == source_type,
                        JobRecord.source_account == account,
                        JobRecord.is_active.is_(True),
                        JobEvaluationRecord.eligibility_status == "PASS",
                    )
                ) or 0

        out.append(
            {
                "company": row.company_name,
                "added_at": _aware(row.owner_added_at).isoformat(),
                "state": row.state,
                "state_label": STATE_LABELS.get(row.state, row.state),
                "reason": voice(row.reason),
                "last_read_at": last_read.isoformat() if last_read else None,
                "jobs": jobs,
                "passing": passing,
                "next_check_at": _aware(row.next_check_at).isoformat(),
            }
        )

    return out


def leads_report(
    session: Session,
    *,
    state: str | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """The ledger, as the Coverage page reads it."""

    counts = dict(session.execute(sa.select(EmployerLead.state, sa.func.count()).group_by(EmployerLead.state)).all())

    total = sum(counts.values())

    origins = {
        origin: (leads, polling or 0)
        for origin, leads, polling in session.execute(
            sa.select(
                EmployerLead.origin,
                sa.func.count(),
                sa.func.sum(sa.case((EmployerLead.state == POLLING, 1), else_=0)),
            ).group_by(EmployerLead.origin)
        )
    }

    filters = []

    if state in STATE_LABELS:
        filters.append(EmployerLead.state == state)

    text = (query or "").strip()

    if text:
        filters.append(
            sa.or_(
                EmployerLead.company_name.ilike(_like(text), escape="\\"),
                EmployerLead.reason.ilike(_like(text), escape="\\"),
            )
        )

    matched = session.scalar(sa.select(sa.func.count()).select_from(EmployerLead).where(*filters))

    rows = list(
        session.scalars(
            sa.select(EmployerLead)
            .where(*filters)
            .order_by(_LIST_ORDER, EmployerLead.company_name, EmployerLead.id)
            .limit(limit)
            .offset(offset)
        )
    )

    # A polling lead's real last read and cadence live with its boards.
    wanted = {
        board_key(b["source_type"], b["source_account"])
        for row in rows
        if row.state == POLLING
        for b in row.boards or []
    }

    cadence: dict[tuple[str, str], int] = {}

    success: dict[tuple[str, str], datetime] = {}

    if wanted:
        for source_type, account, interval in session.execute(
            sa.select(
                JobSourceRecord.source_type,
                JobSourceRecord.source_account,
                JobSourceRecord.poll_interval_seconds,
            ).where(
                JobSourceRecord.enabled.is_(True),
                JobSourceRecord.source_type.in_(sorted({key[0] for key in wanted})),
            )
        ):
            key = board_key(source_type, account)
            if key in wanted:
                cadence[key] = interval

        for source, account, at in session.execute(
            sa.select(SourceState.source, SourceState.source_account, SourceState.last_success_at).where(
                SourceState.source.in_(sorted({key[0] for key in wanted}))
            )
        ):
            key = board_key(source, account)
            if key in wanted:
                success[key] = _aware(at)

    def row_out(row: EmployerLead) -> dict:
        last = _aware(row.last_checked_at)
        interval = None
        if row.state == POLLING:
            keys = [board_key(b["source_type"], b["source_account"]) for b in row.boards or []]
            seen = [success[key] for key in keys if key in success]
            last = max(seen) if seen else last
            minutes = [cadence[key] for key in keys if key in cadence]
            interval = min(minutes) if minutes else None
        return {
            "company": row.company_name,
            "origin": row.origin,
            "origin_label": ORIGIN_LABELS.get(row.origin, row.origin),
            "state": row.state,
            "state_label": STATE_LABELS.get(row.state, row.state),
            "reason": voice(row.reason),
            "last_checked_at": last.isoformat() if last else None,
            "next_check_at": _aware(row.next_check_at).isoformat(),
            "poll_interval_seconds": interval,
        }

    return {
        "total": total,
        "polling": counts.get(POLLING, 0),
        "matched": matched or 0,
        "limit": limit,
        "offset": offset,
        "states": [
            {
                "state": key,
                "label": STATE_LABELS[key],
                "meaning": STATE_MEANINGS[key],
                "leads": counts.get(key, 0),
            }
            for key in STATES
        ],
        "added": added_report(session),
        "origins": [
            {
                "origin": key,
                "label": ORIGIN_LABELS[key],
                "note": ORIGIN_NOTES[key],
                "leads": origins[key][0],
                "polling": origins[key][1],
            }
            for key in ORIGINS
            if key in origins
        ],
        "rows": [row_out(row) for row in rows],
    }
