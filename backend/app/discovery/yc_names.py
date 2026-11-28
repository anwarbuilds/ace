"""YC companies marked hiring become name leads, once a day (DIS-06, owner approved 2026-11-27).

YC's own Terms of Use cover the whole Y Combinator website and say "you will
not engage in or use any data mining, robots, scraping or similar data
gathering or extraction methods", so ACE never opens a YC page, its job pages
included. With the owner's approval ACE reads instead a public file on GitHub
Pages, the open source yc-oss project's list of YC companies marked hiring:

    https://yc-oss.github.io/api/companies/hiring.json

The project builds it daily from YC's search index; it has no license file.
ACE takes names and each company's own website from it, nothing else: no
jobs, no YC links. A US company ACE does not already read goes on Leads; the
lead check then looks for its own job board, starting at that website, and
adds a good board through the same checks as every other lead.

The website travels as an origin detail, ``yc:<host>``, so no table changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import re
from urllib.parse import urlsplit

import httpx
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.app.coverage.benchmark import normalise_company
from backend.app.db.models import EmployerLead, JobSourceRecord, RecallRunRecord

LOGGER = logging.getLogger("ace.discovery.yc_names")

LIST_URL = "https://yc-oss.github.io/api/companies/hiring.json"

LIST_HOST = "yc-oss.github.io"

ORIGIN = "yc"

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

# The list changes once a day.
HARVEST_EVERY = timedelta(days=1)

# A list far shorter than the 1,477 companies it held on 2026-11-27 is not
# the whole list; nothing is learned from it.
MIN_COMPANIES = 300

US_REGION = "United States of America"

KEPT_STATUSES = frozenset({"active", "public"})

MAX_ORIGIN_DETAILS = 12

_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$")

REASON = "A YC company marked hiring. ace looks for its job board, starting at its own website."


class ShortList(ValueError):
    """The list held too few companies to be the whole list."""


@dataclass(slots=True)
class Company:
    name: str
    host: str | None


@dataclass(slots=True)
class Harvest:
    companies: list[Company] = field(default_factory=list)
    listed: int = 0
    us: int = 0


def website_host(
    value: str | None,
) -> str | None:
    """The bare host of a company's website, or None when it is not a plain web address."""

    text = (value or "").strip()
    if not text:
        return None
    if "://" not in text:
        text = "https://" + text
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    host = (parts.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host if _HOST.match(host) else None


def parse(
    rows: object,
) -> Harvest:
    """The US companies marked hiring, with their own website."""

    if not isinstance(rows, list):
        raise ShortList("The YC list is not a list.")
    found = Harvest(listed=len(rows))
    if found.listed < MIN_COMPANIES:
        raise ShortList(f"The YC list held {found.listed} companies, fewer than {MIN_COMPANIES}.")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not row.get("isHiring"):
            continue
        if str(row.get("status") or "").strip().lower() not in KEPT_STATUSES:
            continue
        if US_REGION not in (row.get("regions") or []):
            continue
        name = " ".join(str(row.get("name") or "").split())
        key = normalise_company(name)
        if not name or not key or key in seen:
            continue
        seen.add(key)
        found.us += 1
        found.companies.append(Company(name=name[:255], host=website_host(row.get("website"))))
    return found


def harvest(
    get: Callable[[str], httpx.Response],
) -> Harvest:
    response = get(LIST_URL)
    response.raise_for_status()
    return parse(response.json())


# Origins whose details may carry a company's own website, as "<origin>:<host>".
SITE_HINT_ORIGINS = ("yc", "hn", "site")


def site_hints(
    details: list[str] | None,
) -> tuple[str, ...]:
    """The websites a lead's origin details name, in the order they were added."""

    return tuple(dict.fromkeys(
        detail.split(":", 1)[1]
        for detail in details or []
        if detail.split(":", 1)[0] in SITE_HINT_ORIGINS and ":" in detail and website_host(detail.split(":", 1)[1])
    ))


def remember(
    session: Session,
    found: Harvest,
    *,
    now: datetime,
) -> dict:
    """Write the companies ACE does not read into the lead ledger. Registers nothing."""

    from backend.app.coverage.leads import CHECKING, DORMANT, NOREADER

    reading = {
        normalise_company(name)
        for (name,) in session.execute(
            sa.select(JobSourceRecord.company_name).where(JobSourceRecord.enabled.is_(True))
        )
    }
    rows = {row.company_key: row for row in session.scalars(sa.select(EmployerLead))}
    counts = {"us_hiring": found.us, "read_by_ace": 0, "leads_new": 0, "leads_with_new_site": 0, "leads_known": 0}
    for company in found.companies:
        key = normalise_company(company.name)[:255]
        if key in reading:
            counts["read_by_ace"] += 1
            continue
        details = {ORIGIN} | ({f"{ORIGIN}:{company.host}"} if company.host else set())
        row = rows.get(key)
        if row is None:
            row = EmployerLead(
                company_key=key, company_name=company.name, origin=ORIGIN,
                origin_details=sorted(details), state=CHECKING, reason=REASON, boards=[],
                first_seen_at=now, next_check_at=now, updated_at=now,
            )
            session.add(row)
            rows[key] = row
            counts["leads_new"] += 1
            continue
        before = set(row.origin_details or [])
        if details <= before:
            counts["leads_known"] += 1
            continue
        # The website goes first, so the twelve-detail cap never drops it.
        row.origin_details = (sorted(details - before) + sorted(before))[:MAX_ORIGIN_DETAILS]
        # A name search that found nothing can now start at the company's own site.
        new_site = company.host and f"{ORIGIN}:{company.host}" not in before
        if new_site and not row.boards and row.state in (CHECKING, DORMANT, NOREADER):
            row.state = CHECKING
            row.reason = REASON
            row.next_check_at = now
            counts["leads_with_new_site"] += 1
        else:
            counts["leads_known"] += 1
        row.updated_at = now
    session.flush()
    return counts


def _recent(
    session: Session,
    now: datetime,
) -> bool:
    """A read finished within the day, or one was tried today (recorded with that day's score)."""

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
) -> dict | None:
    """Read the list once a day, after the day's score. Returns what was recorded, or None when not due."""

    with session_factory() as session:
        run = session.scalars(sa.select(RecallRunRecord).order_by(RecallRunRecord.day.desc()).limit(1)).first()
        if run is None or _recent(session, now):
            return None
        run_id = run.id

    mark: dict = {"checked_at": now.isoformat(), "finished": False}
    if not allows(LIST_URL):
        mark["stopped"] = "the list's robots rules refuse ace"
    else:
        try:
            found = harvest(get)
        except (httpx.HTTPError, ValueError) as error:
            mark["stopped"] = type(error).__name__
        else:
            with session_factory.begin() as session:
                mark.update(remember(session, found, now=now))
            mark.update({"finished": True, "listed": found.listed})

    with session_factory.begin() as session:
        run = session.get(RecallRunRecord, run_id)
        run.summary = {**(run.summary or {}), ORIGIN: mark}
    LOGGER.info("yc_names_read %s", mark)
    return mark


__all__ = [
    "Company",
    "Harvest",
    "LIST_URL",
    "ORIGIN",
    "ShortList",
    "USER_AGENT",
    "harvest",
    "harvest_if_due",
    "parse",
    "remember",
    "site_hints",
    "website_host",
]
