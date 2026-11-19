"""The daily score: did ACE find the roles on the test lists? (REC-01)

Once a day the scheduler reads the two test lists (``held_out.py``), the only
reads of them anywhere in ACE, and asks of every open role on them:

* **board**: ACE holds it from the employer's own board (any reader but a
  public list; RippleMatch counts, since employers post there themselves);
* **feed**: ACE holds it only as a copy from a list it reads (Simplify or Zapply);
* **missed**: ACE does not hold it at all, with what ACE knows about the
  company, so a miss says what would fix it.

A role is found whatever the gate decided; a found role your filters hide is
counted separately, with the gate's reason. A role ACE first saw no later than
the day after the list's date was found within a day. List dates are dates
without a time of day, so that is the finest honest comparison.

Matching: a list that links the employer's posting is matched on its posting
number first; a list of short links is never followed, so its roles match by
company and title, as does any role whose number ACE does not hold. A link's
board counts whatever company name ACE holds it under ("Raytheon" on a list,
"RTX" in ACE), and its posting is matched by an identifier in the link's last
part, compared only within that board (SmartRecruiters' number, Workday's
requisition).

A miss says what ACE knows of the role's board (REC-02): not added yet,
switched off, not read in the last day, another career site of a company ACE
reads, or read with the role not there. Nothing here finds jobs or adds a
board. Boards added because of a miss (``MISSED_ROLE_ORIGIN``) still count as
found, and the score also counts their roles apart, so it keeps showing which
companies a miss taught ACE.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import html
import logging
import re
import unicodedata
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo

import httpx
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.benchmark import company_keys, normalise_company
from backend.app.coverage.held_out import HELD_OUT_LISTS, HeldOutList, held_out_rows, is_held_out
from backend.app.discovery.detector import detect_source_from_url
from backend.app.discovery.feed_links import board_key
from backend.app.db.models import (
    EmployerLead,
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
    RecallRunRecord,
    SourceState,
)


LOGGER = logging.getLogger(__name__)

PACIFIC = ZoneInfo("America/Los_Angeles")

BOARD = "board"
FEED = "feed"
MISSED = "missed"

# Readers that copy a public list rather than read an employer.
FEED_SOURCES = frozenset({"simplify", "zapply"})

# Jobs ACE last saw longer ago than this cannot be today's list role.
LOOKBACK_DAYS = 240
# Timing is judged only on roles a list dated within this many days.
TIMING_DAYS = 14
TREND_DAYS = 14
# The check runs once a Pacific day, after this hour, when the lists have
# taken in the night's postings.
RUN_AFTER_HOUR = 5
# Words one title may carry beyond the other when they match by words.
MAX_EXTRA_WORDS = 3
# A list read that yields fewer roles than this is a broken read, not a list.
MIN_ROLES = 20

USER_AGENT = "ace-recall-check/1.0 (personal job search; reads two public lists once a day)"

MONTHS = {name: number for number, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1
)}

# Hosts of hiring sites ACE has no reader for yet, for a missed role's reason.
UNREAD_SITES = {
    "icims.com": "iCIMS",
    "applytojob.com": "JazzHR",
    "jobvite.com": "Jobvite",
    "taleo.net": "Taleo",
    "bamboohr.com": "BambooHR",
    "rippling.com": "Rippling",
    "paylocity.com": "Paylocity",
    "adp.com": "ADP",
    "dayforcehcm.com": "Dayforce",
    "successfactors.com": "SuccessFactors",
    "successfactors.eu": "SuccessFactors",
    "ultipro.com": "UKG",
    "ukg.net": "UKG",
    "paycomonline.net": "Paycom",
    "breezy.hr": "Breezy",
    "recruitee.com": "Recruitee",
    "teamtailor.com": "Teamtailor",
    "pinpointhq.com": "Pinpoint",
    "dover.com": "Dover",
    "hibob.com": "HiBob",
    "clearcompany.com": "ClearCompany",
    "linkedin.com": "LinkedIn",
    "handshake.com": "Handshake",
    "joinhandshake.com": "Handshake",
}

LEAD_REASONS = {
    "noreader": "Uses a hiring site ace can't read yet, or no board found",
    "refused": "The site turned ace away",
    "agency": "A staffing agency, not the employer",
    "waiting": "Good board, left out",
    "checking": "ace has not checked this company yet",
    "dormant": "Board read, no US software jobs on it then",
    "polling": "Board read, role not there",
}
NO_LEAD = "ace has not heard of this company"
BOARD_READ = "Board read, role not there"
READABLE_NOT_ADDED = "On a board ace can read, not added yet"
# Reasons a missed role's own link can give (REC-02), checked against the
# board it names before the company name, since ACE may hold that board
# under another name ("Raytheon" on a list, "RTX" in ACE).
NOT_READ_LATELY = "Board not read in the last day"
OFF_AS_AGENCY = "Board switched off as a staffing agency"
SWITCHED_OFF = "Board switched off"
OTHER_SITE = "Another career site of a company ace reads"

# A board whose newest good read is older than this could not have shown a
# role listed since, so its miss says so rather than "role not there".
STALE_AFTER = timedelta(hours=24)

# Boards ACE added because the daily score showed a role it missed (REC-02).
# Their roles count as found, and the score also counts them apart, so it
# keeps showing which companies a miss taught ACE.
MISSED_ROLE_ORIGIN = "missed_role"


@dataclass(frozen=True, slots=True)
class ListedRole:
    """One open role on a test list."""

    list_key: str
    company: str
    title: str
    location: str
    link: str | None
    listed_on: date | None


@dataclass(frozen=True, slots=True)
class Candidate:
    """A job ACE holds that a listed role might be."""

    id: int
    source: str
    external_id: str
    company: str
    title: str
    official_url: str
    first_seen_at: datetime
    source_account: str = ""


@dataclass(slots=True)
class RoleResult:
    role: ListedRole
    outcome: str
    job_ids: tuple[int, ...] = ()
    first_seen_at: datetime | None = None
    shown: bool | None = None
    hidden_reason: str | None = None
    miss_reason: str | None = None
    # Found only on boards ACE added because of an earlier miss.
    added_board: bool = False


@dataclass(slots=True)
class _Index:
    by_key: dict[str, list[Candidate]] = field(default_factory=dict)
    by_token: dict[str, list[Candidate]] = field(default_factory=dict)
    by_url: dict[str, list[Candidate]] = field(default_factory=dict)
    # Jobs by the board they came from, and by a posting identifier within
    # that board, so a list's link finds its job whatever company name ACE
    # holds the board under.
    by_board: dict[tuple[str, str], list[Candidate]] = field(default_factory=dict)
    by_board_token: dict[tuple[str, str, str], list[Candidate]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HeldBoard:
    """One board in ACE's catalog, as far as a missed role's reason needs it."""

    source_type: str
    source_account: str
    company: str
    enabled: bool
    discovery_source: str
    last_read_at: datetime | None


@dataclass(slots=True)
class Catalog:
    """The boards ACE holds: by board, by company and by Workday tenant."""

    now: datetime
    by_board: dict[tuple[str, str], HeldBoard] = field(default_factory=dict)
    by_company: dict[str, list[HeldBoard]] = field(default_factory=dict)
    tenants: set[tuple[str, str]] = field(default_factory=set)

    def add(self, board: HeldBoard) -> None:
        key = board_key(board.source_type, board.source_account)
        held = self.by_board.get(key)
        # One board under two capitals is one board, read if either copy is on.
        if held is None or (board.enabled and not held.enabled):
            self.by_board[key] = board
        if not board.enabled:
            return
        for company in company_keys(board.company):
            self.by_company.setdefault(company, []).append(board)
        tenant = workday_tenant(board.source_type, board.source_account)
        if tenant:
            self.tenants.add((board.source_type, tenant))

    def stale(self, board: HeldBoard) -> bool:
        if board.last_read_at is None:
            return True
        return self.now - _as_utc(board.last_read_at) > STALE_AFTER

    def added_for_misses(self) -> set[tuple[str, str]]:
        return {
            key for key, board in self.by_board.items()
            if board.enabled and board.discovery_source.startswith(MISSED_ROLE_ORIGIN)
        }


# Reading the lists.

_TAG = re.compile(r"<[^>]+>")
_HREF = re.compile(r"""href=["']([^"']+)["']""")
_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_AGE = re.compile(r"^(\d+)\s*(h|d|w|mo|m|y)$")
_DATE = re.compile(r"^([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})$")
_WORDS = re.compile(r"[^a-z0-9]+")


def _cell_text(cell: str) -> str:
    text = _MD_LINK.sub(r"\1", cell)
    text = _TAG.sub(" ", text.replace("</br>", ", ").replace("<br>", ", ").replace("<br/>", ", "))
    text = html.unescape(text).replace("**", "")
    text = "".join(
        ch for ch in text
        if unicodedata.category(ch) not in {"So", "Cc", "Cf", "Co", "Cs"} and not "\ufe00" <= ch <= "\ufe0f"
    )
    return re.sub(r"\s+", " ", text).strip(" ,")


def _listed_on(text: str, today: date) -> date | None:
    value = text.strip().lower()
    age = _AGE.match(value)
    if age:
        count, unit = int(age.group(1)), age.group(2)
        days = {"h": 0, "d": count, "w": 7 * count, "mo": 30 * count, "m": 30 * count, "y": 365 * count}[unit]
        return today - timedelta(days=days)
    dated = _DATE.match(text.strip())
    if dated and dated.group(1).lower()[:3] in MONTHS:
        month, day = MONTHS[dated.group(1).lower()[:3]], int(dated.group(2))
        for year in (today.year, today.year - 1):
            try:
                candidate = date(year, month, day)
            except ValueError:
                return None
            if candidate <= today + timedelta(days=1):
                return candidate
    return None


def _column(header: list[str], *names: str) -> int | None:
    for index, cell in enumerate(header):
        if any(name in cell for name in names):
            return index
    return None


def parse_list(item: HeldOutList, markdown: str, *, today: date) -> list[ListedRole]:
    """Every open role in a list's tables. Closed rows (marked with a lock) are left out."""

    roles: list[ListedRole] = []
    header: list[str] | None = None
    previous_company = ""
    for line in markdown.splitlines():
        if not line.startswith("|"):
            header = None if not line.strip() else header
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        lowered = [_cell_text(cell).lower() for cell in cells]
        if lowered and lowered[0] in {"company", "company name"}:
            header = lowered
            continue
        if header is None or all(set(cell) <= set("-: ") for cell in cells):
            continue
        company_at = _column(header, "company") or 0
        title_at = _column(header, "position", "role", "title")
        location_at = _column(header, "location")
        link_at = _column(header, "posting", "application", "link", "apply")
        date_at = _column(header, "age", "date")
        if title_at is None or len(cells) <= max(i for i in (company_at, title_at) if i is not None):
            continue
        if "🔒" in line:
            continue
        company = _cell_text(cells[company_at])
        if company in {"↳", ""} or company.startswith("↳"):
            company = previous_company
        previous_company = company
        title = _cell_text(cells[title_at])
        if not company or not title:
            continue
        link = None
        if item.links == "employer" and link_at is not None and link_at < len(cells):
            hrefs = _HREF.findall(cells[link_at]) or [url for _, url in _MD_LINK.findall(cells[link_at])]
            link = html.unescape(hrefs[0]).strip() if hrefs else None
            if link and is_held_out(link):
                link = None
        roles.append(
            ListedRole(
                list_key=item.key,
                company=company,
                title=title,
                location=_cell_text(cells[location_at]) if location_at is not None and location_at < len(cells) else "",
                link=link,
                listed_on=_listed_on(_cell_text(cells[date_at]), today) if date_at is not None and date_at < len(cells) else None,
            )
        )
    return roles


# Matching.

_EARLY_WORDS = frozenset(
    {"new", "grad", "grads", "graduate", "graduates", "university", "college", "campus", "early", "career",
     "careers", "entry", "level", "program", "class", "of", "intern", "2025", "2026", "2027", "2028",
     "start", "starts", "bs", "ms", "phd", "us", "usa"}
)
_EARLY_TITLE = re.compile(
    r"\b(new\s*grad|graduate|university|college|campus|early\s*career|entry[\s-]*level|20(?:25|26|27|28))\b",
    re.IGNORECASE,
)


_INTERN = re.compile(r"\b(intern|interns|internship|co-?op)\b", re.IGNORECASE)


def title_forms(title: str) -> set[str]:
    """A title as words, and without a trailing code or note after " - " or "(".

    "Software Dev Engineer II - AMZ003914" and "Software Dev Engineer II" are
    one role; "Software Engineer" and "Senior Software Engineer" are not.
    A list's own label before a colon ("New Grad 2027: Software Engineer")
    is not part of the employer's title.
    """

    text = (title or "").lower().replace("&", " and ")
    if ":" in text and _EARLY_TITLE.search(text.split(":", 1)[0]):
        text = text.split(":", 1)[1]
    forms = {_WORDS.sub(" ", text).strip()}
    for mark in (" - ", " – ", "(", ",", " | "):
        if mark in text:
            forms.add(_WORDS.sub(" ", text.split(mark)[0]).strip())
    return {form for form in forms if len(form) >= 3}


def title_core(title: str) -> str:
    """A title without its new grad words and years: "Software Engineer, New Grad 2027" is "software engineer"."""

    words = _WORDS.sub(" ", (title or "").lower().replace("&", " and ")).split()
    return " ".join(word for word in words if word not in _EARLY_WORDS)


def is_early_title(title: str) -> bool:
    return bool(_EARLY_TITLE.search(title or ""))


def link_tokens(link: str | None) -> set[str]:
    """Posting numbers a link may carry: path parts and query values."""

    if not link:
        return set()
    try:
        parts = urlsplit(link)
    except ValueError:
        return set()
    tokens = {part for part in parts.path.split("/") if part}
    tokens.update(value for _, value in parse_qsl(parts.query))
    return {token for token in tokens if len(token) >= 5 and any(ch.isdigit() for ch in token)}


# A long number a posting's last address part starts with (SmartRecruiters
# links "744000161528139-software-engineer"; ACE stores ".../744000161528139"),
# and a requisition after its last underscore (Workday "..._01864077").
_LEADING_NUMBER = re.compile(r"^(\d{8,})(?:-|$)")
_REQUISITION = re.compile(r"_([A-Za-z]{0,3}\d{6,})$")


def posting_tokens(url: str | None) -> set[str]:
    """Identifiers of one posting in an address's last part. Compared only
    within one board, because two employers can number their postings alike."""

    if not url:
        return set()
    try:
        path = urlsplit(url.strip()).path
    except ValueError:
        return set()
    last = path.rstrip("/").rsplit("/", 1)[-1]
    tokens = set()
    if len(last) >= 5 and any(ch.isdigit() for ch in last):
        tokens.add(last.lower())
    for pattern in (_LEADING_NUMBER, _REQUISITION):
        found = pattern.search(last)
        if found:
            tokens.add(found.group(1).lower())
    return tokens


def linked_board(link: str | None) -> tuple[str, str] | None:
    """The board a list's employer link names, keyed as ACE keys boards."""

    if not link:
        return None
    detected = detect_source_from_url(link)
    if detected is None:
        return None
    return board_key(str(getattr(detected.source_type, "value", detected.source_type)), detected.source_account)


def workday_tenant(source_type: str, source_account: str) -> str:
    """A Workday tenant runs several career sites ("tenant/site"); "" for anything else."""

    if source_type != "workday" or "/" not in source_account:
        return ""
    return source_account.split("/", 1)[0].strip().lower()


def _url_key(url: str | None) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ""
    return f"{(parts.hostname or '').lower().removeprefix('www.')}{parts.path.rstrip('/').lower()}"


def build_index(candidates: Iterable[Candidate]) -> _Index:
    index = _Index()
    for job in candidates:
        for key in company_keys(job.company):
            index.by_key.setdefault(key, []).append(job)
        if job.external_id:
            index.by_token.setdefault(job.external_id, []).append(job)
        url = _url_key(job.official_url)
        if url:
            index.by_url.setdefault(url, []).append(job)
        if job.source_account:
            board = board_key(job.source, job.source_account)
            index.by_board.setdefault(board, []).append(job)
            for token in posting_tokens(job.official_url) | posting_tokens(job.external_id):
                index.by_board_token.setdefault((*board, token), []).append(job)
    return index


def _indexed_jobs(index: _Index) -> list[Candidate]:
    seen: dict[int, Candidate] = {}
    for group in (index.by_key, index.by_token, index.by_url, index.by_board):
        for jobs in group.values():
            for job in jobs:
                seen.setdefault(job.id, job)
    return list(seen.values())


def match_role(role: ListedRole, index: _Index) -> list[Candidate]:
    """The jobs ACE holds that are this listed role."""

    keys = company_keys(role.company)
    same_company = {job.id: job for key in keys for job in index.by_key.get(key, ())}
    linked = linked_board(role.link)
    if linked is not None:
        # The board the list links is the employer's, whatever name ACE
        # holds it under ("Raytheon" on the list, "RTX" in ACE).
        same_company.update((job.id, job) for job in index.by_board.get(linked, ()))
    # A full-time role on a list is never an internship ACE holds.
    if not _INTERN.search(role.title):
        same_company = {key: job for key, job in same_company.items() if not _INTERN.search(job.title)}

    exact: dict[int, Candidate] = {}
    for job in index.by_url.get(_url_key(role.link), ()):
        exact[job.id] = job
    for token in link_tokens(role.link):
        for job in index.by_token.get(token, ()):
            if job.id in same_company or len(token) >= 8:
                exact[job.id] = job
    if linked is not None:
        for token in posting_tokens(role.link):
            for job in index.by_board_token.get((*linked, token), ()):
                exact[job.id] = job
    if exact:
        return list(exact.values())

    forms = title_forms(role.title)
    same_title = [job for job in same_company.values() if title_forms(job.title) & forms]
    if same_title:
        return same_title
    # The list and the employer word a new grad role differently ("Backend
    # Engineer" against "Backend Engineer Graduate (Payments) - 2027 Start").
    # Only an employer title that is itself early career may match this way,
    # so a list's "New Grad: Software Engineer" never matches a senior
    # opening, and every word of one title must be in the other with at most
    # MAX_EXTRA_WORDS left over, so a team name still has to agree.
    listed = set(title_core(role.title).split())
    if len(listed) < 2:
        return []
    company_words = {word for key in keys for word in key.split()}
    found = []
    for job in same_company.values():
        if not is_early_title(job.title):
            continue
        held = set(title_core(job.title).split())
        small, large = sorted((listed, held), key=len)
        if len(small) >= 2 and small <= large and len((large - small) - company_words) <= MAX_EXTRA_WORDS:
            found.append(job)
    return found


def miss_reason(
    role: ListedRole,
    *,
    leads: dict[str, str],
    boards: set[str],
    catalog: Catalog | None = None,
) -> str:
    keys = company_keys(role.company)
    linked = linked_board(role.link)
    if catalog is not None and linked is not None:
        # The list links a board ACE can read: say what ACE knows of that board.
        held = catalog.by_board.get(linked)
        if held is not None and not held.enabled:
            return OFF_AS_AGENCY if "staffing" in held.discovery_source.lower() else SWITCHED_OFF
        if held is not None:
            return NOT_READ_LATELY if catalog.stale(held) else BOARD_READ
        tenant = workday_tenant(*linked)
        if tenant and (linked[0], tenant) in catalog.tenants:
            return OTHER_SITE
        return READABLE_NOT_ADDED
    if keys & boards:
        if catalog is not None:
            held = [board for key in keys for board in catalog.by_company.get(key, ())]
            if held and all(catalog.stale(board) for board in held):
                return NOT_READ_LATELY
        return BOARD_READ
    if role.link and detect_source_from_url(role.link) is not None:
        return READABLE_NOT_ADDED
    host = (urlsplit(role.link).hostname or "").lower() if role.link else ""
    for suffix, site in UNREAD_SITES.items():
        if host == suffix or host.endswith("." + suffix):
            return f"Posted on {site}, which ace can't read yet"
    state = leads.get(normalise_company(role.company))
    if state is None:
        for key in keys:
            state = leads.get(key)
            if state:
                break
    return LEAD_REASONS.get(state or "", NO_LEAD)


def score_roles(
    roles: list[ListedRole],
    index: _Index,
    *,
    statuses: dict[int, tuple[str, list]] | Callable[[set[int]], dict[int, tuple[str, list]]],
    leads: dict[str, str],
    boards: set[str],
    catalog: Catalog | None = None,
) -> list[RoleResult]:
    matched = [(role, match_role(role, index)) for role in roles]
    if callable(statuses):
        statuses = statuses({job.id for _, jobs in matched for job in jobs})
    added = catalog.added_for_misses() if catalog is not None else set()

    def on_added(job: Candidate) -> bool:
        return bool(job.source_account) and board_key(job.source, job.source_account) in added

    independent: _Index | None = None
    results = []
    for role, matches in matched:
        if not matches:
            results.append(
                RoleResult(role, MISSED, miss_reason=miss_reason(role, leads=leads, boards=boards, catalog=catalog))
            )
            continue
        direct = [job for job in matches if job.source not in FEED_SOURCES]
        outcome = BOARD if direct else FEED
        # Found only on boards a miss taught ACE: counted as found, and apart.
        # A role ACE also holds on a board it found by itself is not.
        added_board = bool(direct) and all(on_added(job) for job in direct)
        if added_board:
            if independent is None:
                independent = build_index(job for job in _indexed_jobs(index) if not on_added(job))
            if any(job.source not in FEED_SOURCES for job in match_role(role, independent)):
                added_board = False
        verdicts = [statuses.get(job.id) for job in matches]
        shown = any(verdict and verdict[0] == "PASS" for verdict in verdicts)
        hidden = None
        if not shown:
            reasons = [str(verdict[1][0]) for verdict in verdicts if verdict and verdict[1]]
            hidden = reasons[0] if reasons else "Not judged yet"
        results.append(
            RoleResult(
                role,
                outcome,
                job_ids=tuple(sorted(job.id for job in matches)),
                first_seen_at=min(job.first_seen_at for job in matches),
                shown=shown,
                hidden_reason=hidden,
                added_board=added_board,
            )
        )
    return results


def _as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def _pacific_day(moment: datetime) -> date:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(PACIFIC).date()


def summarize(results: list[RoleResult], *, today: date) -> dict:
    """Counts for one list or all of them. Every count has its denominator beside it."""

    outcomes = Counter(result.outcome for result in results)
    found = [result for result in results if result.outcome != MISSED]
    timed = [
        result for result in found
        if result.role.listed_on and result.role.listed_on >= today - timedelta(days=TIMING_DAYS)
    ]
    within = [
        result for result in timed
        if _pacific_day(result.first_seen_at) <= result.role.listed_on + timedelta(days=1)
    ]
    first = [result for result in timed if _pacific_day(result.first_seen_at) < result.role.listed_on]
    hidden = [result for result in found if not result.shown]
    added = [result for result in found if result.added_board]
    return {
        "listed": len(results),
        "found": len(found),
        "board": outcomes[BOARD],
        # Of "board": found only on boards ACE added because of an earlier miss.
        "board_added": len(added),
        "added_companies": sorted({result.role.company for result in added}, key=str.lower),
        "feed": outcomes[FEED],
        "missed": outcomes[MISSED],
        "timed": len(timed),
        "within_day": len(within),
        "seen_first": len(first),
        "hidden": len(hidden),
        "hidden_reasons": [
            {"reason": reason, "count": count}
            for reason, count in Counter(result.hidden_reason for result in hidden).most_common(3)
        ],
    }


def _missed_row(result: RoleResult) -> dict:
    role = result.role
    return {
        "list": role.list_key,
        "company": role.company,
        "title": role.title,
        "location": role.location,
        "listed_on": role.listed_on.isoformat() if role.listed_on else None,
        "link": role.link,
        "reason": result.miss_reason,
    }


# Reading ACE.

def load_candidates(session: Session, roles: list[ListedRole], *, now: datetime) -> list[Candidate]:
    cutoff = now - timedelta(days=LOOKBACK_DAYS)
    wanted_keys = {key for role in roles for key in company_keys(role.company)}
    names = [
        name
        for name in session.scalars(sa.select(JobRecord.company).where(JobRecord.last_seen_at >= cutoff).distinct())
        if name and company_keys(name) & wanted_keys
    ]
    tokens = sorted({token for role in roles for token in link_tokens(role.link)})
    columns = (
        JobRecord.id,
        JobRecord.source,
        JobRecord.external_id,
        JobRecord.company,
        JobRecord.title,
        JobRecord.official_url,
        JobRecord.first_seen_at,
        JobRecord.source_account,
    )
    seen: dict[int, Candidate] = {}

    def take(condition) -> None:
        for row in session.execute(sa.select(*columns).where(condition, JobRecord.last_seen_at >= cutoff)):
            seen.setdefault(row.id, Candidate(*row))

    for start in range(0, len(names), 400):
        take(JobRecord.company.in_(names[start:start + 400]))
    for start in range(0, len(tokens), 400):
        take(JobRecord.external_id.in_(tokens[start:start + 400]))
    # The boards the lists link, as the catalog spells them, whatever company
    # name they hold: a role's own board is where its job would be.
    linked = {board for role in roles if (board := linked_board(role.link))}
    accounts: dict[str, set[str]] = {}
    for source_type, account in session.execute(
        sa.select(JobSourceRecord.source_type, JobSourceRecord.source_account).where(
            JobSourceRecord.source_type.not_in(sorted(FEED_SOURCES))
        )
    ):
        if board_key(source_type, account) in linked:
            accounts.setdefault(source_type, set()).add(account)
    for source_type, held in sorted(accounts.items()):
        names_held = sorted(held)
        for start in range(0, len(names_held), 200):
            take(sa.and_(JobRecord.source == source_type, JobRecord.source_account.in_(names_held[start:start + 200])))
    return list(seen.values())


def load_statuses(session: Session, job_ids: Iterable[int]) -> dict[int, tuple[str, list]]:
    ids = sorted(set(job_ids))
    statuses: dict[int, tuple[str, list]] = {}
    for start in range(0, len(ids), 1000):
        for job_id, status, reasons in session.execute(
            sa.select(
                JobEvaluationRecord.job_id,
                JobEvaluationRecord.eligibility_status,
                JobEvaluationRecord.reasons,
            ).where(JobEvaluationRecord.job_id.in_(ids[start:start + 1000]))
        ):
            statuses[job_id] = (status, list(reasons or []))
    return statuses


def load_company_facts(session: Session) -> tuple[dict[str, str], set[str]]:
    leads = dict(session.execute(sa.select(EmployerLead.company_key, EmployerLead.state)).all())
    boards = {
        key
        for name in session.scalars(
            sa.select(JobSourceRecord.company_name).where(
                JobSourceRecord.enabled.is_(True),
                JobSourceRecord.source_type.not_in(sorted(FEED_SOURCES)),
            ).distinct()
        )
        for key in company_keys(name)
    }
    return leads, boards


def load_catalog(session: Session, *, now: datetime) -> Catalog:
    """Every employer board ACE holds, with its newest good read, as the schedule table counts reads."""

    states = {
        board_key(row.source, row.source_account): max(
            (_as_utc(value) for value in (row.last_success_at, row.last_unchanged_at) if value), default=None
        )
        for row in session.execute(
            sa.select(SourceState.source, SourceState.source_account, SourceState.last_success_at,
                      SourceState.last_unchanged_at)
        )
    }
    catalog = Catalog(now=now)
    for row in session.execute(
        sa.select(
            JobSourceRecord.source_type,
            JobSourceRecord.source_account,
            JobSourceRecord.company_name,
            JobSourceRecord.enabled,
            JobSourceRecord.discovery_source,
        ).where(JobSourceRecord.source_type.not_in(sorted(FEED_SOURCES)))
    ):
        catalog.add(
            HeldBoard(
                source_type=row.source_type,
                source_account=row.source_account,
                company=row.company_name or "",
                enabled=bool(row.enabled),
                discovery_source=row.discovery_source or "",
                last_read_at=states.get(board_key(row.source_type, row.source_account)),
            )
        )
    return catalog


def fetch_list(url: str) -> str:
    """Read one test list. Only test lists: this is the one reader allowed to."""

    if not is_held_out(url):
        raise ValueError(f"the daily check reads only test lists, not {url}")
    response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)
    response.raise_for_status()
    return response.text


def measure(
    session: Session,
    *,
    now: datetime,
    texts: dict[str, str | None],
) -> dict:
    """Score every list text against ACE. Read only."""

    today = _pacific_day(now)
    lists: list[dict] = []
    all_results: list[RoleResult] = []
    leads, boards = load_company_facts(session)
    catalog = load_catalog(session, now=now)
    for item in HELD_OUT_LISTS:
        text = texts.get(item.key)
        roles = parse_list(item, text, today=today) if text else []
        if len(roles) < MIN_ROLES:
            lists.append({"key": item.key, "label": item.label, "links": item.links, "error": "could not be read today"})
            continue
        index = build_index(load_candidates(session, roles, now=now))
        results = score_roles(
            roles,
            index,
            statuses=lambda ids: load_statuses(session, ids),
            leads=leads,
            boards=boards,
            catalog=catalog,
        )
        all_results.extend(results)
        lists.append({"key": item.key, "label": item.label, "links": item.links, **summarize(results, today=today)})

    missed = sorted(
        (_missed_row(result) for result in all_results if result.outcome == MISSED),
        key=lambda row: (row["listed_on"] or "", row["company"].lower()),
        reverse=True,
    )
    return {
        "day": today.isoformat(),
        "checked_at": now.isoformat(),
        "total": summarize(all_results, today=today),
        "lists": lists,
        "leaks": held_out_rows(session),
        "missed": missed,
    }


def run_daily_check(
    session_factory: Callable,
    *,
    now: datetime,
    fetch: Callable[[str], str] = fetch_list,
    force: bool = False,
) -> dict | None:
    """Score today once. Returns the stored result, or None when not due."""

    today = _pacific_day(now)
    if not force and now.astimezone(PACIFIC).hour < RUN_AFTER_HOUR:
        return None
    with session_factory() as session:
        if not force and session.scalar(sa.select(RecallRunRecord.id).where(RecallRunRecord.day == today)):
            return None

    texts: dict[str, str | None] = {}
    for item in HELD_OUT_LISTS:
        try:
            texts[item.key] = fetch(item.url)
        except (httpx.HTTPError, OSError) as error:
            LOGGER.warning("recall_list_unreadable list=%s error=%r", item.key, str(error))
            texts[item.key] = None

    with session_factory() as session:
        result = measure(session, now=now, texts=texts)
        session.rollback()

    with session_factory() as session:
        row = session.scalar(sa.select(RecallRunRecord).where(RecallRunRecord.day == today))
        if row is None:
            row = RecallRunRecord(day=today)
            session.add(row)
        row.checked_at = now
        row.summary = {key: value for key, value in result.items() if key != "missed"}
        row.missed = result["missed"]
        session.commit()

    total = result["total"]
    LOGGER.info(
        "recall_checked day=%s listed=%d board=%d feed=%d missed=%d within_day=%d/%d leaks=%s",
        result["day"], total["listed"], total["board"], total["feed"], total["missed"],
        total["within_day"], total["timed"], result["leaks"],
    )
    return result


def recall_report(session: Session) -> dict:
    """The newest daily score, the last two weeks of scores, and today's missed roles."""

    runs = session.scalars(
        sa.select(RecallRunRecord).order_by(RecallRunRecord.day.desc()).limit(TREND_DAYS)
    ).all()
    if not runs:
        return {"checked": False}
    latest = runs[0]
    return {
        "checked": True,
        **latest.summary,
        "checked_at": _as_utc(latest.checked_at).isoformat(),
        "missed": latest.missed or [],
        "trend": [
            {
                "day": run.day.isoformat(),
                "listed": run.summary.get("total", {}).get("listed", 0),
                "found": run.summary.get("total", {}).get("found", 0),
            }
            for run in reversed(runs)
        ],
    }
