"""What each host ACE reads says about being read, dated and rechecked.

The rule was already followed in many readers, one at a time, and written
down nowhere. A verdict here is judged on the exact paths ACE reads on that
host, because a robots file usually opens one route and closes another.

A refused host is an answer. Nothing in this module, or anything calling it,
tries another address, proxy or identity. A failed read is not a refusal: it
keeps the last verdict and says the recheck failed, because a brief outage
must not read as a site turning ACE away.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.adapters.bytedance import PORTALS
from backend.app.adapters.lever import LEVER_API_HOST_BY_JOB_HOST
from backend.app.adapters.simplify import FEED_URLS
from backend.app.adapters.sitemap_jobs import site_for
from backend.app.coverage.probing import (
    PAGE_READ_BYTES,
    TIMEOUT_SECONDS,
    USER_AGENT,
    _fetch_json,
    _fetch_robots,
    _fetch_text,
    _post_json,
    refuses_automation,
    robots_allows,
)
from backend.app.db.models import (
    EmployerPageReading,
    HostPolicyRecord,
    JobSourceRecord,
)


LOGGER = logging.getLogger("ace.coverage.hosts")

UNKNOWN = "unknown"
ALLOWED = "allowed"
REFUSED = "refused"

RECHECK_AFTER = timedelta(days=30)

# A file that could not be read is tried again tomorrow.
RETRY_AFTER = timedelta(days=1)

# Each check is one small request, and a whole sweep is a thousand hosts,
# so a run is bounded in count and in time.
HOSTS_PER_RUN = 60
SECONDS_PER_RUN = 180.0

# ACE's wider rule: these answers are a refusal, whatever RFC 9309 says
# about client errors. 429 is left out on purpose. It says "not now", and is
# reported as a failed read until the host answers.
REFUSING_STATUSES = frozenset({401, 403, 405})

EMPLOYER_PAGE = "employer_page"

PLATFORM_LABELS = {
    "greenhouse": "Greenhouse",
    "ashby": "Ashby",
    "lever": "Lever",
    "smartrecruiters": "SmartRecruiters",
    "workable": "Workable",
    "workday": "Workday",
    "oracle_recruiting": "Oracle Recruiting",
    "gem": "Gem",
    "eightfold": "Eightfold",
    "jibe": "iCIMS Jibe",
    "avature": "Avature",
    "employer_site": "Employers' own career sites",
    "feed": "Multi-employer feeds",
    EMPLOYER_PAGE: "Employer posting pages",
}


@dataclass(frozen=True, slots=True)
class HostTarget:
    """A host ACE reads, and the paths it reads there."""

    host: str

    platform: str

    paths: tuple[str, ...]


def _host_of(value: str) -> str:
    return value.strip().strip("/").split("/", 1)[0].lower()


def read_targets(
    source_type: str,
    source_account: str,
    source_host: str | None = None,
) -> tuple[HostTarget, ...]:
    """The hosts one source's reader requests, and the paths it asks for.

    Shared hosts use a stand-in board name: the verdict is about the route,
    and a robots file does not name one employer's board.
    """

    account = (source_account or "").strip()

    host = _host_of(source_host or "")

    if source_type == "greenhouse":
        return (HostTarget("boards-api.greenhouse.io", "greenhouse", ("/v1/boards/example/jobs",)),)

    if source_type == "ashby":
        return (HostTarget("api.ashbyhq.com", "ashby", ("/posting-api/job-board/example",)),)

    if source_type == "lever":
        api_host = LEVER_API_HOST_BY_JOB_HOST.get(host, "api.lever.co")
        return (HostTarget(api_host, "lever", ("/v0/postings/example",)),)

    if source_type == "smartrecruiters":
        return (HostTarget("api.smartrecruiters.com", "smartrecruiters", ("/v1/companies/example/postings",)),)

    if source_type == "workable":
        return (
            HostTarget(
                "apply.workable.com",
                "workable",
                ("/api/v3/accounts/example/jobs", "/api/v2/accounts/example/jobs/example"),
            ),
        )

    if source_type == "workday":
        tenant, _, site = account.partition("/")
        if not host or not site:
            return ()
        return (HostTarget(host, "workday", (f"/wday/cxs/{tenant}/{site}/jobs",)),)

    if source_type == "oracle_recruiting":
        oracle_host = _host_of(account)
        if not oracle_host:
            return ()
        return (
            HostTarget(
                oracle_host,
                "oracle_recruiting",
                (
                    "/hcmRestApi/resources/latest/recruitingCEJobRequisitions",
                    "/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails",
                ),
            ),
        )

    if source_type == "gem":
        return (HostTarget("api.gem.com", "gem", ("/job_board/v0/example/job_posts/",)),)

    if source_type == "eightfold":
        eightfold_host = host or _host_of(account)
        if not eightfold_host:
            return ()
        return (HostTarget(eightfold_host, "eightfold", ("/api/apply/v2/jobs",)),)

    if source_type == "eightfold_pcsx":
        eightfold_host = host or _host_of(account)
        if not eightfold_host:
            return ()
        return (HostTarget(eightfold_host, "eightfold", ("/api/pcsx/search", "/api/pcsx/position_details")),)

    if source_type == "jibe":
        jibe_host = _host_of(account)
        if not jibe_host:
            return ()
        return (HostTarget(jibe_host, "jibe", ("/api/jobs",)),)

    if source_type == "avature":
        parts = urlsplit(account)
        if not parts.netloc:
            return ()
        return (HostTarget(parts.netloc.lower(), "avature", (parts.path or "/",)),)

    if source_type == "jobposting_sitemap":
        sitemap_host = _host_of(account)
        if not sitemap_host:
            return ()
        posting = (
            "/profile/job_details/1/"
            if sitemap_host.endswith("metacareers.com")
            else "/job/example/example/1/1"
        )
        return (
            HostTarget(
                sitemap_host,
                "employer_site",
                (urlsplit(site_for(sitemap_host).sitemap).path, posting),
            ),
        )

    if source_type == "bytedance":
        portal = PORTALS.get(account)
        if portal is None:
            return ()
        parts = urlsplit(portal.api)
        return (HostTarget(parts.netloc, "employer_site", (parts.path,)),)

    if source_type == "simplify":
        paths = tuple(sorted(urlsplit(url).path for url in FEED_URLS.values()))
        return (HostTarget("raw.githubusercontent.com", "feed", paths),)

    fixed = {
        "amazon": ("www.amazon.jobs", "employer_site", ("/search.json",)),
        "ibm": ("www-api.ibm.com", "employer_site", ("/search/api/v2",)),
        "google": ("www.google.com", "employer_site", ("/about/careers/applications/jobs/results",)),
        "atlassian": (
            "www.atlassian.com",
            "employer_site",
            ("/endpoint/careers/listings", "/company/careers/details/1"),
        ),
        "shopify": ("www.shopify.com", "employer_site", ("/careers", "/careers/example_1")),
        "apple": ("jobs.apple.com", "employer_site", ("/en-us/search", "/en-us/details/1/example")),
        "ripplematch": ("app.ripplematch.com", "feed", ("/sitemap.xml", "/v2/public/job/example")),
    }.get(source_type)

    if fixed is None:
        return ()

    return (HostTarget(*fixed),)


def _wanted_hosts(session: Session) -> dict[str, tuple[str, set[str]]]:
    """Every host ACE reads today, with its platform and paths."""

    wanted: dict[str, tuple[str, set[str]]] = {}

    for source_type, source_account, source_host in session.execute(
        sa.select(
            JobSourceRecord.source_type,
            JobSourceRecord.source_account,
            JobSourceRecord.source_host,
        ).where(JobSourceRecord.enabled.is_(True))
    ):
        for target in read_targets(source_type, source_account, source_host):
            wanted.setdefault(target.host, (target.platform, set()))[1].update(target.paths)

    # Feed postings are judged on the employer's own page, and those pages
    # are hosts ACE reads too. Their reader already asks robots each time.
    for url in session.scalars(sa.select(EmployerPageReading.url)):
        parts = urlsplit(url or "")
        host = parts.netloc.lower()
        if not host:
            continue
        platform, paths = wanted.setdefault(host, (EMPLOYER_PAGE, set()))
        if platform == EMPLOYER_PAGE and len(paths) < 3:
            paths.add(parts.path or "/")

    return wanted


def sync_hosts(session: Session, *, now: datetime) -> int:
    """Give every host ACE reads a row. Returns how many were new.

    A host ACE stops reading keeps its row: the record stays, with its date.
    """

    wanted = _wanted_hosts(session)

    existing = {row.host: row for row in session.scalars(sa.select(HostPolicyRecord))}

    created = 0

    for host, (platform, paths) in wanted.items():
        row = existing.get(host)

        if row is None:
            session.add(
                HostPolicyRecord(
                    host=host,
                    platform=platform,
                    paths=sorted(paths),
                    next_check_at=now,
                    first_seen_at=now,
                    updated_at=now,
                )
            )
            created += 1
            continue

        if row.platform != platform:
            row.platform = platform

        if set(row.paths or []) != paths:
            # New paths have not been judged yet.
            row.paths = sorted(paths)
            row.next_check_at = min(_aware(row.next_check_at), now)

    session.flush()

    return created


def _aware(value: datetime) -> datetime:
    # SQLite hands back naive values for what PostgreSQL stores with a zone.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def read_robots(
    host: str,
    *,
    opener=urllib.request.urlopen,
) -> tuple[int | None, str]:
    """A host's robots.txt, as (status, text). Status None: nothing answered."""

    request = urllib.request.Request(
        f"https://{host}/robots.txt",
        headers={"User-Agent": USER_AGENT},
    )

    try:
        with opener(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read(PAGE_READ_BYTES).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except Exception:
        return None, ""


@dataclass(frozen=True, slots=True)
class Reading:
    """What one read of a robots file showed."""

    # None when the file could not be read, which decides nothing.
    verdict: str | None

    detail: str


def judge(
    host: str,
    paths: Iterable[str],
    status: int | None,
    text: str,
) -> Reading:
    """Turn one read of a robots file into a verdict. Pure."""

    if status is None:
        return Reading(None, "Nothing answered for its robots file.")

    if status in REFUSING_STATUSES:
        return Reading(REFUSED, f"Answers its robots file with {status}, which ACE treats as a refusal.")

    if status == 200:
        closed = [path for path in paths if not robots_allows(text, f"https://{host}{path}")]
        if closed:
            return Reading(REFUSED, "Robots file disallows " + ", ".join(sorted(closed)) + ".")
        return Reading(ALLOWED, "Robots file allows the pages ACE reads.")

    if 400 <= status < 500 and status != 429:
        return Reading(ALLOWED, f"No robots file ({status}), so it sets no rules.")

    return Reading(None, f"Its robots file answered {status}.")


def check_host(
    row: HostPolicyRecord,
    *,
    now: datetime,
    fetch_robots: Callable[[str], tuple[int | None, str]] = read_robots,
) -> str:
    """Read one host's robots file and record what it said."""

    status, text = fetch_robots(row.host)

    reading = judge(row.host, row.paths or ["/"], status, text)

    row.robots_status = status

    if reading.verdict is None:
        row.last_error = reading.detail
        row.next_check_at = now + RETRY_AFTER
        return row.robots_verdict

    if reading.verdict != row.robots_verdict:
        LOGGER.warning(
            "host_verdict_changed host=%s from=%s to=%s detail=%r",
            row.host,
            row.robots_verdict,
            reading.verdict,
            reading.detail,
        )

    row.robots_verdict = reading.verdict
    row.robots_detail = reading.detail
    row.last_error = ""
    row.checked_at = now
    row.next_check_at = now + RECHECK_AFTER

    return reading.verdict


def check_due_hosts(
    sessions,
    *,
    now: Callable[[], datetime],
    fetch_robots: Callable[[str], tuple[int | None, str]] = read_robots,
    limit: int = HOSTS_PER_RUN,
    seconds: float = SECONDS_PER_RUN,
) -> int:
    """Check the hosts that are due, oldest first, each saved as it is read."""

    with sessions() as session:
        due = list(
            session.scalars(
                sa.select(HostPolicyRecord.host)
                .where(HostPolicyRecord.next_check_at <= now())
                .order_by(HostPolicyRecord.next_check_at)
                .limit(limit)
            )
        )

    started = time.monotonic()

    checked = 0

    for host in due:
        if time.monotonic() - started > seconds:
            break

        with sessions.begin() as session:
            row = session.get(HostPolicyRecord, host)
            if row is not None:
                check_host(row, now=now(), fetch_robots=fetch_robots)
                checked += 1

    return checked


def refused_hosts(session: Session) -> set[str]:
    return set(
        session.scalars(
            sa.select(HostPolicyRecord.host).where(HostPolicyRecord.robots_verdict == REFUSED)
        )
    )


def refusal_for(
    session: Session,
    target: HostTarget,
    *,
    now: datetime,
    fetch_robots: Callable[[str], tuple[int | None, str]] = read_robots,
) -> str | None:
    """Why ACE must not newly read this host, or None when it may.

    For anything new: a board being added, a lead being checked. Asks the
    robots file first when ACE has never seen the host. A host whose rules
    could not be read at all is treated as closed for now, as RFC 9309 says.
    The caller commits.
    """

    row = session.get(HostPolicyRecord, target.host)

    if row is None:
        row = HostPolicyRecord(
            host=target.host,
            platform=target.platform,
            paths=sorted(target.paths),
            next_check_at=now,
            first_seen_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()

    if not set(target.paths) <= set(row.paths or []):
        row.paths = sorted(set(row.paths or []) | set(target.paths))
        row.next_check_at = now

    if row.robots_verdict == UNKNOWN or _aware(row.next_check_at) <= now:
        check_host(row, now=now, fetch_robots=fetch_robots)

    if row.robots_verdict == REFUSED:
        return row.robots_detail or "This host refuses automated reading."

    if row.robots_verdict == UNKNOWN:
        return row.last_error or "Its robots file could not be read yet."

    return None


def without_refused_hosts(
    sources: Iterable,
    refused: set[str],
) -> list:
    """The sources left once refused hosts are taken out of polling."""

    return [
        source
        for source in sources
        if not any(
            target.host in refused
            for target in read_targets(source.source_type.value, source.source_account, source.source_host)
        )
    ]


def hosts_report(
    session: Session,
    *,
    enforcing: bool,
    terms: dict,
) -> dict:
    """Every host's verdict, grouped by platform, as Coverage reads it."""

    rows = list(session.scalars(sa.select(HostPolicyRecord)))

    counts: dict[str, int] = {}

    for source_type, source_account, source_host in session.execute(
        sa.select(
            JobSourceRecord.source_type,
            JobSourceRecord.source_account,
            JobSourceRecord.source_host,
        ).where(JobSourceRecord.enabled.is_(True))
    ):
        for target in read_targets(source_type, source_account, source_host):
            counts[target.host] = counts.get(target.host, 0) + 1

    def stamp(value: datetime | None) -> str | None:
        return _aware(value).isoformat() if value else None

    def terms_out(platform: str) -> dict:
        reading = terms.get(platform)
        if reading is None:
            return {"verdict": "not_read", "note": "", "url": None, "reviewed_on": None, "recheck_on": None}
        return {
            "verdict": reading.verdict,
            "note": reading.note,
            "url": reading.url,
            "reviewed_on": reading.reviewed_on.isoformat(),
            "recheck_on": reading.recheck_on.isoformat(),
        }

    groups: dict[str, dict] = {}

    for row in rows:
        group = groups.setdefault(
            row.platform,
            {
                "platform": row.platform,
                "label": PLATFORM_LABELS.get(row.platform, row.platform),
                "hosts": 0,
                "allowed": 0,
                "refused": 0,
                "unknown": 0,
                "sources": 0,
                "example_host": row.host,
                "oldest_checked_at": None,
                "next_check_at": None,
                "terms": terms_out(row.platform),
            },
        )
        group["hosts"] += 1
        group[row.robots_verdict if row.robots_verdict in (ALLOWED, REFUSED) else UNKNOWN] += 1
        group["sources"] += counts.get(row.host, 0)
        checked = stamp(row.checked_at)
        if checked and (group["oldest_checked_at"] is None or checked < group["oldest_checked_at"]):
            group["oldest_checked_at"] = checked
        upcoming = stamp(row.next_check_at)
        if upcoming and (group["next_check_at"] is None or upcoming < group["next_check_at"]):
            group["next_check_at"] = upcoming

    def host_out(row: HostPolicyRecord) -> dict:
        return {
            "host": row.host,
            "platform": PLATFORM_LABELS.get(row.platform, row.platform),
            "detail": row.robots_detail or row.last_error,
            "last_error": row.last_error,
            "sources": counts.get(row.host, 0),
            "checked_at": stamp(row.checked_at),
            "next_check_at": stamp(row.next_check_at),
        }

    refused = sorted((row for row in rows if row.robots_verdict == REFUSED), key=lambda row: row.host)

    return {
        "enforcing": enforcing,
        "total": len(rows),
        "allowed": sum(1 for row in rows if row.robots_verdict == ALLOWED),
        "refused": len(refused),
        "unknown": sum(1 for row in rows if row.robots_verdict == UNKNOWN),
        "groups": sorted(groups.values(), key=lambda group: (-group["sources"], group["label"])),
        "refused_hosts": [host_out(row) for row in refused],
    }


class PoliteReader:
    """Discovery's fetchers, asking robots first and skipping refused hosts.

    The company search was only ever run by hand. Run on a schedule, it must
    ask each host before reading it, including the guessed careers pages.
    """

    def __init__(
        self,
        refused: set[str] | None = None,
        *,
        fetch=_fetch_json,
        fetch_text=_fetch_text,
        post=_post_json,
        robots=_fetch_robots,
        refuses=refuses_automation,
    ) -> None:
        self._refused = refused or set()
        self._fetch = fetch
        self._fetch_text = fetch_text
        self._post = post
        self._robots = robots
        self._refuses = refuses
        self._texts: dict[str, str | None] = {}

    def allows(self, url: str) -> bool:
        host = urlsplit(url).netloc.lower()
        if not host or host in self._refused:
            return False
        if host not in self._texts:
            self._texts[host] = self._robots(host)
        return robots_allows(self._texts[host], url)

    def fetch(self, url: str, **kwargs):
        return self._fetch(url, **kwargs) if self.allows(url) else None

    def fetch_text(self, url: str, **kwargs) -> str:
        return self._fetch_text(url, **kwargs) if self.allows(url) else ""

    def post(self, url: str, payload: dict, **kwargs):
        return self._post(url, payload, **kwargs) if self.allows(url) else None

    def refuses(self, url: str) -> bool:
        return self._refuses(url) if self.allows(url) else False
