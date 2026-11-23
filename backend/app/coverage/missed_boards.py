"""Add the boards behind the roles the daily score missed (REC-02).

The owner asked on November 20 and approved on November 22, 2026: every new
grad role the daily score says ACE missed should still reach the owner, and
its company's own board should be added so the next role is not missed.

The test lists stay unread for finding jobs. Nothing here puts a listed role
into Pulls. A missed role reaches the owner only on Coverage, Needs you, with
its own link, as something to look at. A role reaches Pulls only from the
employer's own board, once ACE reads that board like any other. The score
counts roles found on boards added this way apart (``board_added``), so it
stays honest about what ACE found by itself.

Once a day, right after the score, the boards the missed roles' own links name
go through the same checks as every board ACE adds: the robots rules first,
then one read of the board, the staffing filter, at least one US software or
ML role and the identity check. A board the catalog holds, on or off, is never
touched. Each missed role then carries what happened, in plain words.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa

from backend.app.coverage import recall
from backend.app.coverage.benchmark import normalise_company
from backend.app.coverage.held_out import is_held_out
from backend.app.discovery.detector import detect_source_from_url
from backend.app.discovery.feed_links import board_key
from backend.app.db.models import EmployerLead, RecallRunRecord

LOGGER = logging.getLogger(__name__)

# At most this many boards are read for misses each day, so a bad day on the
# lists cannot crowd out normal reading. The rest wait for the next day.
BOARDS_PER_DAY = 12

# What happened to a missed role's board, as the Needs you tab shows it.
ADDED = "added"          # ace added the company's board today
TRYING = "trying"        # ace will try the board again on a later day
HELD = "held"            # ace already reads this board
OFF = "off"              # the board is in ace, switched off, and stays off
NOT_ADDED = "not_added"  # ace read the board and it did not pass the checks
NO_BOARD = "no_board"    # no board ace can read; the owner can still apply

STATES = (ADDED, TRYING, HELD, OFF, NOT_ADDED, NO_BOARD)

# Platforms whose boards ace does not add while they turn ace away.
SKIPPED_PLATFORMS = {
    "smartrecruiters": "SmartRecruiters' robots rules refuse ace, so ace does not add its boards",
    "workable": "Workable turns ace away, so ace does not add its boards",
}

_READ_CHECK_WORDS = {
    "hiring US engineers": "ace added this company's board",
    "no US software or ML roles today": "The board has no US software or ML role today",
    "empty: the board read, but holds nothing": "The board is empty today",
}


# A company ace had never heard of goes on Leads by itself (owner, November 22:
# "I should not have any manual work"); the lead check looks for its board by
# name and adds a good one.
NAMED_NOTE = "ace put this company on Leads and looks for its board by name. A good board is added by itself"


@dataclass(frozen=True, slots=True)
class BoardFix:
    state: str
    note: str


def _plain(reason: str) -> str:
    """The registration check's reason, in words the owner reads."""

    if reason in _READ_CHECK_WORDS:
        return _READ_CHECK_WORDS[reason]
    head = reason.split(":", 1)[0].strip().lower()
    if head == "staffing":
        return "The board belongs to a staffing agency, not the employer"
    if head == "shared":
        return "The board is shared by several companies, so ace does not add it"
    if head == "identity":
        return "ace could not confirm the board belongs to this company"
    return "The board did not pass ace's checks"


def held_fix(row: dict) -> BoardFix | None:
    """What a miss's own reason already says, without reading anything. None: its board can be tried."""

    reason = row.get("reason") or ""
    if reason in (recall.READABLE_NOT_ADDED, recall.OTHER_SITE):
        return None
    if reason == recall.BOARD_READ:
        return BoardFix(HELD, "ace reads this company's board. The role was not on it at the last read")
    if reason == recall.NOT_READ_LATELY:
        return BoardFix(HELD, "ace has this company's board and reads it again soon")
    if reason in (recall.OFF_AS_AGENCY, recall.SWITCHED_OFF):
        return BoardFix(OFF, "This board was switched off earlier, so ace leaves it off")
    # The company is on Leads: what the lead check found so far.
    if reason in (recall.LEAD_REASONS["checking"], recall.LEAD_REASONS["waiting"]):
        return BoardFix(TRYING, NAMED_NOTE)
    if reason == recall.LEAD_REASONS["dormant"]:
        return BoardFix(NOT_ADDED, "The board had no US software role when ace read it. ace looks again later")
    if reason == recall.LEAD_REASONS["agency"]:
        return BoardFix(OFF, "A staffing agency, not the employer, so ace leaves it off")
    return BoardFix(NO_BOARD, reason or "No board ace can read")


def _candidate_of(row: dict):
    link = row.get("link")
    if not link or is_held_out(link):
        return None
    return detect_source_from_url(link)


def fix_missed(
    rows: list[dict],
    *,
    known: set[tuple[str, str]],
    allows: Callable[[str, str, str | None], bool],
    try_board: Callable[[str, str, str, str | None], object],
    add_board: Callable[[object], bool],
    limit: int = BOARDS_PER_DAY,
) -> tuple[list[dict], dict]:
    """Return the missed rows, each with its ``fix``, and the day's counts.

    ``known`` is every board key the catalog holds. ``allows`` says whether
    the robots rules let ace read a board. ``try_board`` reads one board
    through the registration checks and returns its outcome; ``add_board``
    registers a passed outcome and says whether it was added.
    """

    done: dict[tuple[str, str], BoardFix] = {}
    tried = 0
    fixed: list[dict] = []
    for row in rows:
        fix = held_fix(row)
        detected = None if fix else _candidate_of(row)
        if fix is None and detected is None:
            fix = BoardFix(NO_BOARD, row.get("reason") or "No board ace can read")
        if fix is None:
            source_type = str(getattr(detected.source_type, "value", detected.source_type))
            account = detected.source_account
            host = getattr(detected, "source_host", None)
            key = board_key(source_type, account)
            fix = done.get(key)
            if fix is None:
                if key in known:
                    fix = BoardFix(HELD, "ace has this company's board and reads it again soon")
                elif source_type in SKIPPED_PLATFORMS:
                    fix = BoardFix(NO_BOARD, SKIPPED_PLATFORMS[source_type])
                elif not allows(source_type, account, host):
                    fix = BoardFix(NO_BOARD, "The site's robots rules refuse ace, so ace does not read it")
                elif tried >= limit:
                    fix = BoardFix(TRYING, "ace tries this company's board on another day")
                else:
                    tried += 1
                    try:
                        outcome = try_board(source_type, account, row.get("company") or "", host)
                    except Exception as error:  # a failed read says nothing about the board
                        LOGGER.warning("missed_board_unread source=%s/%s error=%r", source_type, account, str(error))
                        fix = BoardFix(TRYING, "The board could not be read today. ace tries again on another day")
                    else:
                        if getattr(outcome, "transient", False):
                            fix = BoardFix(TRYING, "The site asked ace to slow down. ace tries again on another day")
                        elif getattr(outcome, "added", False) and add_board(outcome):
                            known.add(key)
                            fix = BoardFix(ADDED, "ace added this company's board. New roles reach Pulls from it")
                            LOGGER.warning("missed_board_added company=%r source=%s/%s", row.get("company"), source_type, account)
                        elif getattr(outcome, "added", False):
                            fix = BoardFix(HELD, "ace has this company's board and reads it again soon")
                        else:
                            fix = BoardFix(NOT_ADDED, _plain(getattr(outcome, "reason", "")))
                done[key] = fix
        fixed.append({**row, "fix": {"state": fix.state, "note": fix.note}})
    counts = {state: sum(1 for row in fixed if row["fix"]["state"] == state) for state in STATES}
    return fixed, {"boards_read": tried, "roles": counts, "boards_added": sum(1 for f in done.values() if f.state == ADDED)}


def name_leads(session, rows: list[dict], *, now: datetime) -> set[str]:
    """Put each company ace had never heard of on Leads, with no board: the lead check searches by name.

    Returns the keys of the companies on Leads now, new or not. A test list is never read to find jobs: only the
    company's name is kept, and its board is found and read by ace itself."""

    from backend.app.coverage.leads import CHECKING, MISSED, is_real_name

    keys = set(session.scalars(sa.select(EmployerLead.company_key)))
    named: set[str] = set()
    for row in rows:
        if row.get("reason") != recall.NO_LEAD:
            continue
        name = (row.get("company") or "").strip()
        key = normalise_company(name)[:255]
        if not key or not is_real_name(name):
            continue
        if key not in keys:
            session.add(EmployerLead(
                company_key=key, company_name=name[:255], origin=MISSED, origin_details=[MISSED], state=CHECKING,
                reason="A role the daily check missed. ace looks for its board by name.", boards=[],
                first_seen_at=now, next_check_at=now, updated_at=now,
            ))
            keys.add(key)
            LOGGER.info("missed_company_named company=%r", name)
        named.add(key)
    session.flush()
    return named


def _counts(fixed: list[dict], base: dict) -> dict:
    return {**base, "roles": {state: sum(1 for row in fixed if row["fix"]["state"] == state) for state in STATES}}


def fix_latest_run(
    session_factory: Callable,
    *,
    now: datetime,
    known: Callable[[], set[tuple[str, str]]],
    allows: Callable[[str, str, str | None], bool],
    try_board: Callable[[str, str, str, str | None], object],
    register: Callable[[object, object], bool],
) -> dict | None:
    """Fix today's score's misses once. Returns the day's counts, or None when done already or not scored.

    A score fixed before companies were named (November 22) gets only the naming step."""

    with session_factory() as session:
        run = session.scalars(sa.select(RecallRunRecord).order_by(RecallRunRecord.day.desc()).limit(1)).first()
        if run is None:
            return None
        done = (run.summary or {}).get("fixes")
        if done and "named" in done:
            return None
        run_id, rows = run.id, list(run.missed or [])

    if done:
        fixed, counts = rows, {k: v for k, v in done.items() if k != "roles"}
    else:
        def add_board(outcome) -> bool:
            with session_factory.begin() as session:
                return register(session, outcome)

        fixed, counts = fix_missed(rows, known=known(), allows=allows, try_board=try_board, add_board=add_board)
        counts["checked_at"] = now.isoformat()

    with session_factory.begin() as session:
        before = int(session.scalar(sa.select(sa.func.count()).select_from(EmployerLead)) or 0)
        named = name_leads(session, fixed, now=now)
        counts["named"] = int(session.scalar(sa.select(sa.func.count()).select_from(EmployerLead)) or 0) - before
        fixed = [
            {**row, "fix": {"state": TRYING, "note": NAMED_NOTE}}
            if row.get("reason") == recall.NO_LEAD and normalise_company((row.get("company") or "").strip())[:255] in named
            else row
            for row in fixed
        ]
        counts = _counts(fixed, counts)
        run = session.get(RecallRunRecord, run_id)
        run.missed = fixed
        run.summary = {**(run.summary or {}), "fixes": counts}
    LOGGER.info("missed_boards_checked boards_read=%d boards_added=%d named=%d roles=%s",
                counts["boards_read"], counts["boards_added"], counts["named"], counts["roles"])
    return counts
