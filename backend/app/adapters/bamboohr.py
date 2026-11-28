"""BambooHR careers boards: ``https://<account>.bamboohr.com/careers`` (DIS-09, owner approved 2026-11-28).

Each board answers its whole list at ``/careers/list`` (JSON), each posting
at ``/careers/<id>/detail`` (JSON with the description) and its company's
name at ``/careers/company-info``. robots.txt disallows nothing. The list is
the whole board, so a read is complete; descriptions are read only for titles
the gate could pass, and kept between polls.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import re
from typing import Any

import httpx

from backend.app.adapters.listed_details import descriptions
from backend.app.adapters.retry import request_with_retry
from backend.app.models.job import CanonicalJob
from backend.app.verification.employer_page import READ, UNREACHABLE, Reading, ReadingStore, _flatten

SOURCE = "bamboohr"

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

TIMEOUT_SECONDS = 30.0

_ACCOUNT = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

EMPLOYMENT_TYPES = {
    "full-time": "full-time",
    "full time": "full-time",
    "part-time": "part-time",
    "part time": "part-time",
    "contractor": "contract",
    "contract": "contract",
    "temporary": "contract",
    "intern": "internship",
    "internship": "internship",
}


def board_account(account: str) -> str:
    value = (account or "").strip().lower()
    if not _ACCOUNT.match(value) or value in ("www", "api", "app"):
        raise ValueError(f"A BambooHR account is the board's subdomain; got {account!r}.")
    return value


def base_url(account: str) -> str:
    return f"https://{board_account(account)}.bamboohr.com/careers"


def posting_url(account: str, posting_id: str) -> str:
    return f"{base_url(account)}/{posting_id}"


def _location(posting: dict[str, Any]) -> str:
    place = posting.get("location") if isinstance(posting.get("location"), dict) else {}
    ats = posting.get("atsLocation") if isinstance(posting.get("atsLocation"), dict) else {}
    parts = [
        str(place.get("city") or ats.get("city") or "").strip(),
        str(place.get("state") or ats.get("state") or ats.get("province") or "").strip(),
        str(ats.get("country") or place.get("addressCountry") or "").strip(),
    ]
    text = ", ".join(part for part in parts if part)
    if str(posting.get("isRemote") or "").lower() in ("true", "1") or str(posting.get("locationType") or "") == "1":
        text = (text + " (Remote)") if text else "Remote"
    return text


def _detail(http: httpx.Client, url: str) -> Reading:
    try:
        response = request_with_retry(lambda: http.get(url + "/detail"))
    except httpx.HTTPError:
        return Reading(UNREACHABLE)
    if response.status_code != 200:
        return Reading(UNREACHABLE)
    opening = ((response.json() or {}).get("result") or {}).get("jobOpening") or {}
    text = _flatten(str(opening.get("description") or ""))
    return Reading(READ, text) if text else Reading(UNREACHABLE)


def fetch_bamboohr_jobs(
    *,
    source_account: str,
    company_name: str,
    should_fetch_detail: Callable[[str], bool] | None = None,
    store: ReadingStore | None = None,
    client: httpx.Client | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> list[CanonicalJob]:
    """Read every posting on one BambooHR board."""

    account = board_account(source_account)
    store = store or ReadingStore()
    owns = client is None
    http = client or httpx.Client(timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        response = request_with_retry(lambda: http.get(f"{base_url(account)}/list"))
        response.raise_for_status()
        rows = [row for row in ((response.json() or {}).get("result") or []) if isinstance(row, dict) and row.get("id")]
        postings = [(posting_url(account, str(row["id"])), str(row.get("jobOpeningName") or "").strip()) for row in rows]
        found = descriptions(postings, lambda url: _detail(http, url), should_fetch_detail=should_fetch_detail,
                             store=store, now=now())
    finally:
        if owns:
            http.close()
    jobs = []
    for row, (url, title) in zip(rows, postings):
        if not title:
            continue
        jobs.append(CanonicalJob(
            source=SOURCE, company=company_name, external_id=str(row["id"]), requisition_id=str(row["id"]),
            title=title, location=_location(row), description=found.get(url, ""), official_url=url,
            employment_type=EMPLOYMENT_TYPES.get(str(row.get("employmentStatusLabel") or "").strip().lower()),
        ))
    return jobs


def company_name_of(fetch: Callable[[str], Any], account: str) -> str | None:
    """The company a board names itself, from /careers/company-info."""

    try:
        body = fetch(f"{base_url(account)}/company-info")
    except ValueError:
        return None
    name = ((body or {}).get("result") or {}).get("name") if isinstance(body, dict) else None
    return " ".join(str(name).split()) or None if name else None


__all__ = ["SOURCE", "base_url", "board_account", "company_name_of", "fetch_bamboohr_jobs", "posting_url"]
