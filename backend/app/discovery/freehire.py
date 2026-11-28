"""A weekly harvest of employer boards from FreeHire's public API (DIS-02).

FreeHire (freehire.me) is an open-source job aggregator with a documented,
unauthenticated JSON API. Its robots rules allow ``/api/`` for every reader
but two search engines, and its terms allow the API without a plan for
personal, non-commercial use: a tool someone runs for themselves, which ACE
is. ACE reads it as a signal only. It takes from each posting the employer's
board, never the posting: the board goes into the lead ledger, and the lead
check reads that board itself with ACE's own reader, through the robots rules,
the staffing filter, the US software or ML role check and the identity check,
before it adds it (owner, November 22, 2026: "A", add good boards by
themselves). Nothing FreeHire returns is shown, stored as a posting or passed
on, and a FreeHire sighting never counts as ACE finding a role.

Only platforms FreeHire reads plainly, with its own name and its own address,
are used. Its open source (``internal/ingest/sources``, read November 22,
2026) sends some providers through a residential proxy, a Chrome disguise or
an anti-bot browser because those sites block its address; data gathered that
way is never used (``BYPASSED``). Of the rest, only platforms ACE has its own
reader for are asked for (``PLATFORMS``).

The harvest runs at most once a week and paces itself well under FreeHire's
published limit. A refusal stops it for the day.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import time
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.benchmark import normalise_company
from backend.app.coverage.companies import is_namesake
from backend.app.coverage.identity import shared_board_reason, staging_host_reason
from backend.app.db.models import EmployerLead, JobSourceRecord, RecallRunRecord
from backend.app.discovery.detector import detect_source_from_url
from backend.app.discovery.feed_links import board_key

LOGGER = logging.getLogger("ace.discovery.freehire")

API = "https://freehire.me/api/v1/jobs/search"
ROBOTS_PATH = "/api/v1/jobs/search"

USER_AGENT = "ACE/0.1 (personal career-intelligence project)"

# FreeHire's own source names, for the platforms it reads plainly and ACE
# has a reader for, with the board token's place in FreeHire's identifier.
PLATFORMS = ("greenhouse", "lever", "ashby", "gem", "workday", "oracle", "successfactors", "bamboohr", "rippling", "icims")

# Platforms FreeHire reads through a proxy, a browser disguise or an anti-bot
# browser (its proxy.go, fingerprinthttp.go and scraplingtier.go, read
# November 22, 2026). Never asked for, even if ACE gains a reader.
BYPASSED = frozenset({
    "adp", "adpmyjobs", "bayt", "bullhorn", "cake", "careerspage", "cleverstaff", "darwinbox", "djinni",
    "echojobs", "eightfold", "enlizt", "geekjob", "gradcracker", "gulftalent", "gusto", "habr_career",
    "infojobs", "jobleads", "kontur", "linkedin", "meta", "mynavi", "naukri", "neogov", "netempregos",
    "njoyn", "onstrider", "pageup", "peopleforce", "startupjobs", "teamtailor", "uber", "vagas",
    "wantapply", "wantapply-cy", "wellfound", "workable", "2gis",
})

assert not BYPASSED & set(PLATFORMS)

# Roles the registration check could pass; it judges each board itself.
CATEGORIES = ",".join((
    "software_engineering", "backend", "frontend", "fullstack", "ml_ai", "ai_engineering",
    "data_engineering", "data_science", "solutions_engineering",
))

# Postings opened in the last month, so a weekly run overlaps the one before.
OPEN_WITHIN_DAYS = 30
PAGE = 100
# FreeHire pages no further than this for one query.
MAX_OFFSET = 10_000
# FreeHire allows 300 requests a minute without a key; ACE asks for about one a second.
PAUSE_SECONDS = 1.0
KEEP_SPARE = 20

HARVEST_EVERY = timedelta(days=7)

ORIGIN = "freehire"

# Tokens FreeHire's identifier carries for platforms whose posting links can
# sit on an employer's own domain (careers.example.com/jobs/1?gh_jid=1).
_BOARD_URLS = {
    "greenhouse": "https://boards.greenhouse.io/{token}",
    "lever": "https://jobs.lever.co/{token}",
    "ashby": "https://jobs.ashbyhq.com/{token}",
    "gem": "https://jobs.gem.com/{token}",
    "bamboohr": "https://{token}.bamboohr.com/careers",
    "rippling": "https://ats.rippling.com/{token}/jobs",
}


class Refused(Exception):
    """FreeHire said no (429, 403, a challenge): stop for the day."""


@dataclass(slots=True)
class Board:
    source_type: str
    source_account: str
    source_host: str | None
    company: str
    platform: str
    postings: int = 0

    @property
    def key(self) -> tuple[str, str]:
        return board_key(self.source_type, self.source_account)


@dataclass(slots=True)
class Harvest:
    boards: dict[tuple[str, str], Board] = field(default_factory=dict)
    requests: int = 0
    postings: int = 0
    unmapped: int = 0
    per_platform: dict[str, int] = field(default_factory=dict)
    stopped: str = ""


def _clean_url(url: str) -> str:
    parts = urlsplit(url)
    query = "&".join(item for item in parts.query.split("&") if item and not item.startswith("utm_"))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def board_of(item: dict) -> tuple[str, str, str | None] | None:
    """The board a FreeHire posting names: (source_type, account, host), or None."""

    platform = item.get("source") or ""
    if platform not in PLATFORMS:
        return None
    external = item.get("external_id") or ""
    url = _clean_url(item.get("url") or "")
    candidates = [url]
    template = _BOARD_URLS.get(platform)
    if template and ":" in external:
        token = external.split(":", 1)[0].strip()
        if token and "/" not in token and "." not in token:
            candidates.insert(0, template.format(token=token) + "/jobs/1")
    if platform == "icims" and ":" in external:
        # "uscareers-bruker.icims.com:19658", or "apogeeusa:2476" for the usual careers-<name> site.
        site, posting = external.split(":", 1)
        site = site.strip().lower()
        host = site if site.endswith(".icims.com") else f"careers-{site}.icims.com"
        if posting.isdigit():
            candidates.insert(0, f"https://{host}/jobs/{posting}/posting/job")
    if platform == "successfactors" and ":" in external:
        # "jobs.example.com:1452291433": the careers site's host and the posting.
        host, posting = external.split(":", 1)
        if host and posting.isdigit():
            candidates.insert(0, f"https://{host.strip().lower()}/job/posting/{posting}/")
    for link in candidates:
        detected = detect_source_from_url(link) if link else None
        if detected is None:
            continue
        source_type = str(getattr(detected.source_type, "value", detected.source_type))
        expected = "oracle_recruiting" if platform == "oracle" else platform
        if source_type != expected:
            continue
        return source_type, detected.source_account, getattr(detected, "source_host", None)
    return None


def harvest(
    get: Callable[[str], httpx.Response],
    *,
    pause: Callable[[float], None] = time.sleep,
    platforms: Iterable[str] = PLATFORMS,
) -> Harvest:
    """Ask FreeHire, platform by platform, for US full-time software postings, and keep their boards."""

    result = Harvest()
    for platform in platforms:
        assert platform in PLATFORMS and platform not in BYPASSED
        offset = 0
        while offset < MAX_OFFSET:
            query = {
                "countries": "US", "employment_type": "full_time", "category": CATEGORIES,
                "open_within_days": str(OPEN_WITHIN_DAYS), "source": platform,
                "limit": str(PAGE), "offset": str(offset),
            }
            response = get(API + "?" + urlencode(query))
            result.requests += 1
            if response.status_code in (401, 403, 405, 429) or response.headers.get("cf-mitigated"):
                raise Refused(f"freehire answered {response.status_code}")
            response.raise_for_status()
            body = response.json()
            ignored = (body.get("meta") or {}).get("ignored_params")
            if ignored:
                # A filter FreeHire does not read would return its whole catalogue.
                raise ValueError(f"freehire ignored {ignored}")
            items = body.get("data") or []
            for item in items:
                result.postings += 1
                found = board_of(item)
                if found is None:
                    result.unmapped += 1
                    continue
                source_type, account, host = found
                board = result.boards.get(board_key(source_type, account))
                if board is None:
                    board = Board(source_type, account, host, (item.get("company") or "").strip(), platform)
                    result.boards[board.key] = board
                board.postings += 1
            total = int((body.get("meta") or {}).get("total") or 0)
            offset += PAGE
            remaining = response.headers.get("x-ratelimit-remaining")
            if remaining is not None and remaining.isdigit() and int(remaining) < KEEP_SPARE:
                reset = response.headers.get("x-ratelimit-reset") or "60"
                pause(float(reset) if reset.isdigit() else 60.0)
            else:
                pause(PAUSE_SECONDS)
            if not items or offset >= total:
                break
        result.per_platform[platform] = sum(1 for b in result.boards.values() if b.platform == platform)
    return result


def remember(session: Session, found: Harvest, *, now: datetime) -> dict:
    """Write the boards ACE does not hold into the lead ledger. Registers nothing."""

    from backend.app.coverage.leads import CHECKING, DORMANT, NOREADER, is_real_name

    known = {
        board_key(source_type, account)
        for source_type, account in session.execute(sa.select(JobSourceRecord.source_type, JobSourceRecord.source_account))
    }
    rows = {row.company_key: row for row in session.scalars(sa.select(EmployerLead))}
    held = {
        board_key(b["source_type"], b["source_account"])
        for row in rows.values()
        for b in row.boards or []
    }
    counts = {"boards": len(found.boards), "held_by_ace": 0, "already_leads": 0, "skipped": 0,
              "leads_new": 0, "boards_new_on_leads": 0}
    for key, board in sorted(found.boards.items()):
        if key in known:
            counts["held_by_ace"] += 1
            continue
        if key in held:
            counts["already_leads"] += 1
            continue
        if (not is_real_name(board.company) or shared_board_reason(board.source_type, board.source_account)
                or staging_host_reason(board.source_type, board.source_account, board.source_host)
                or is_namesake(board.source_type, board.source_account)):
            counts["skipped"] += 1
            continue
        company_key = normalise_company(board.company)[:255]
        if not company_key:
            counts["skipped"] += 1
            continue
        entry = {"source_type": board.source_type, "source_account": board.source_account,
                 "source_host": board.source_host}
        detail = f"{ORIGIN}:{board.platform}"
        row = rows.get(company_key)
        if row is None:
            row = EmployerLead(
                company_key=company_key, company_name=board.company[:255], origin=ORIGIN,
                origin_details=[ORIGIN, detail], state=CHECKING,
                reason="FreeHire lists a board ace has not read yet.", boards=[entry],
                first_seen_at=now, next_check_at=now, updated_at=now,
            )
            session.add(row)
            rows[company_key] = row
            counts["leads_new"] += 1
        else:
            # First, because the lead check reads only a lead's first few boards.
            row.boards = [entry] + list(row.boards or [])
            row.origin_details = sorted(set(row.origin_details or []) | {ORIGIN, detail})[:12]
            if row.state in (CHECKING, DORMANT, NOREADER):
                row.state = CHECKING
                row.reason = "FreeHire lists a board ace has not read yet."
                row.next_check_at = now
            row.updated_at = now
            counts["boards_new_on_leads"] += 1
        held.add(key)
    session.flush()
    return counts


def _recent(session: Session, now: datetime) -> bool:
    """A harvest finished within the week, or one was tried today (recorded with that day's score)."""

    since = (now - HARVEST_EVERY - timedelta(days=1)).date()
    for summary in session.scalars(sa.select(RecallRunRecord.summary).where(RecallRunRecord.day >= since)):
        mark = (summary or {}).get(ORIGIN) or {}
        checked = mark.get("checked_at")
        if not checked:
            continue
        at = datetime.fromisoformat(checked)
        if mark.get("finished") and now - at < HARVEST_EVERY:
            return True
        if at.date() == now.date():
            return True
    return False


def harvest_if_due(
    session_factory: Callable,
    *,
    now: datetime,
    allows: Callable[[str], bool],
    get: Callable[[str], httpx.Response],
    pause: Callable[[float], None] = time.sleep,
) -> dict | None:
    """Harvest once a week, after the day's score. Returns what was recorded, or None when not due."""

    with session_factory() as session:
        run = session.scalars(sa.select(RecallRunRecord).order_by(RecallRunRecord.day.desc()).limit(1)).first()
        if run is None or _recent(session, now):
            return None
        run_id = run.id

    mark: dict = {"checked_at": now.isoformat(), "finished": False}
    if not allows("https://freehire.me" + ROBOTS_PATH):
        mark["stopped"] = "freehire's robots rules refuse ace"
    else:
        try:
            found = harvest(get, pause=pause)
        except Refused as error:
            mark["stopped"] = str(error)
        except (httpx.HTTPError, ValueError) as error:
            mark["stopped"] = type(error).__name__
        else:
            with session_factory.begin() as session:
                mark.update(remember(session, found, now=now))
            mark.update({"finished": True, "requests": found.requests, "postings": found.postings,
                         "unmapped": found.unmapped, "per_platform": found.per_platform})

    with session_factory.begin() as session:
        run = session.get(RecallRunRecord, run_id)
        run.summary = {**(run.summary or {}), ORIGIN: mark}
    LOGGER.info("freehire_harvested %s", {k: v for k, v in mark.items() if k != "per_platform"})
    return mark
