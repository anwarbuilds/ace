"""Paylocity job boards: ``recruiting.paylocity.com/Recruiting/Jobs/All/<board id>`` (DIS-09, owner approved 2026-11-28).

The board page carries its whole list in ``window.pageData`` (title, date,
place, a short teaser); each posting's page, ``/Recruiting/Jobs/Details/<id>``,
carries a JobPosting with the whole description and the employer. The host
has no robots.txt. The list is the whole board, so a read is complete;
descriptions are read only for titles the gate could pass, and kept between
polls.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
import re
from typing import Any

import httpx

from backend.app.adapters.listed_details import descriptions
from backend.app.adapters.retry import request_with_retry
from backend.app.adapters.sitemap_jobs import parse_posting_page
from backend.app.models.job import CanonicalJob
from backend.app.verification.employer_page import READ, UNREACHABLE, Reading, ReadingStore, _flatten

SOURCE = "paylocity"

HOST = "recruiting.paylocity.com"

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

TIMEOUT_SECONDS = 30.0

_BOARD = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

_PAGE_DATA = re.compile(r"window\.pageData\s*=\s*(\{.*?\});\s*\n", re.DOTALL)


def board_id(account: str) -> str:
    value = (account or "").strip().lower()
    if not _BOARD.match(value):
        raise ValueError(f"A Paylocity account is the board's id; got {account!r}.")
    return value


def board_url(account: str) -> str:
    return f"https://{HOST}/Recruiting/Jobs/All/{board_id(account)}"


def posting_url(posting_id: str) -> str:
    return f"https://{HOST}/Recruiting/Jobs/Details/{posting_id}"


def listed(markup: str) -> list[dict[str, Any]]:
    """The postings a board page lists, or raises when the page holds no list."""

    found = _PAGE_DATA.search(markup or "")
    if not found:
        raise ValueError("The Paylocity board page holds no list.")
    data = json.loads(found.group(1))
    return [row for row in data.get("Jobs") or [] if isinstance(row, dict) and row.get("JobId") and not row.get("IsInternal")]


def _location(row: dict[str, Any]) -> str:
    place = row.get("JobLocation") if isinstance(row.get("JobLocation"), dict) else {}
    country = str(place.get("Country") or "").strip()
    parts = [str(place.get("City") or "").strip(), str(place.get("State") or "").strip(),
             "United States" if country.upper() in ("USA", "US", "UNITED STATES") else country]
    text = ", ".join(part for part in parts if part)
    if row.get("IsRemote"):
        text = (text + " (Remote)") if text else "Remote"
    return text


def _posted(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _detail(http: httpx.Client, url: str) -> Reading:
    try:
        response = request_with_retry(lambda: http.get(url))
    except httpx.HTTPError:
        return Reading(UNREACHABLE)
    if response.status_code != 200:
        return Reading(UNREACHABLE)
    posting = parse_posting_page(response.text) or {}
    text = _flatten(str(posting.get("description") or ""))
    return Reading(READ, text) if text else Reading(UNREACHABLE)


def employer_of(markup: str) -> str | None:
    """The employer a posting page's own JobPosting names."""

    organization = (parse_posting_page(markup or "") or {}).get("hiringOrganization")
    name = organization.get("name") if isinstance(organization, dict) else None
    return " ".join(str(name).split()) or None if name else None


def fetch_paylocity_jobs(
    *,
    source_account: str,
    company_name: str,
    should_fetch_detail: Callable[[str], bool] | None = None,
    store: ReadingStore | None = None,
    client: httpx.Client | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> list[CanonicalJob]:
    """Read every posting on one Paylocity board."""

    account = board_id(source_account)
    store = store or ReadingStore()
    owns = client is None
    http = client or httpx.Client(timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
    try:
        response = request_with_retry(lambda: http.get(board_url(account)))
        response.raise_for_status()
        rows = listed(response.text)
        postings = [(posting_url(str(row["JobId"])), " ".join(str(row.get("JobTitle") or "").split())) for row in rows]
        found = descriptions(postings, lambda url: _detail(http, url), should_fetch_detail=should_fetch_detail,
                             store=store, now=now())
    finally:
        if owns:
            http.close()
    return [
        CanonicalJob(
            source=SOURCE, company=company_name, external_id=str(row["JobId"]), requisition_id=str(row["JobId"]),
            title=title, location=_location(row), description=found.get(url, ""), official_url=url,
            posted_at=_posted(row.get("PublishedDate")),
        )
        for row, (url, title) in zip(rows, postings)
        if title
    ]


__all__ = ["HOST", "SOURCE", "board_id", "board_url", "employer_of", "fetch_paylocity_jobs", "listed", "posting_url"]
