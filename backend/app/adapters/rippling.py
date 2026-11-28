"""Rippling job boards: ``https://ats.rippling.com/<board>/jobs`` (DIS-09, owner approved 2026-11-28).

Each board answers its whole list from Rippling's public board API,
``https://api.rippling.com/platform/api/ats/v1/board/<board>/jobs``, and each
posting, with its description and the company's own name, at ``.../jobs/<id>``.
ats.rippling.com's robots.txt disallows only ``/internal/``; api.rippling.com
has none. The list is the whole board, so a read is complete; descriptions are
read only for titles the gate could pass, and kept between polls.
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

SOURCE = "rippling"

API = "https://api.rippling.com/platform/api/ats/v1/board"

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

TIMEOUT_SECONDS = 30.0

_BOARD = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,98}[a-z0-9])?$")


def board_slug(account: str) -> str:
    value = (account or "").strip().lower()
    if not _BOARD.match(value):
        raise ValueError(f"A Rippling account is the board's slug; got {account!r}.")
    return value


def list_url(account: str) -> str:
    return f"{API}/{board_slug(account)}/jobs"


def posting_url(account: str, posting_id: str) -> str:
    return f"https://ats.rippling.com/{board_slug(account)}/jobs/{posting_id}"


def _location(posting: dict[str, Any]) -> str:
    place = posting.get("workLocation")
    if isinstance(place, dict):
        return str(place.get("label") or "").strip()
    places = posting.get("workLocations")
    if isinstance(places, list):
        return "; ".join(str(item).strip() for item in places if str(item).strip())
    return ""


def _description(detail: dict[str, Any]) -> str:
    body = detail.get("description")
    if isinstance(body, dict):
        # The role first: it states the requirements; the company part is the same on every posting.
        parts = [body.get("role"), body.get("company")]
        return "\n\n".join(text for text in (_flatten(str(part or "")) for part in parts) if text)
    return _flatten(str(body or ""))


def _detail(http: httpx.Client, account: str, url: str) -> Reading:
    posting_id = url.rstrip("/").rsplit("/", 1)[1]
    try:
        response = request_with_retry(lambda: http.get(f"{list_url(account)}/{posting_id}"))
    except httpx.HTTPError:
        return Reading(UNREACHABLE)
    if response.status_code != 200:
        return Reading(UNREACHABLE)
    text = _description(response.json() or {})
    return Reading(READ, text) if text else Reading(UNREACHABLE)


def fetch_rippling_jobs(
    *,
    source_account: str,
    company_name: str,
    should_fetch_detail: Callable[[str], bool] | None = None,
    store: ReadingStore | None = None,
    client: httpx.Client | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> list[CanonicalJob]:
    """Read every posting on one Rippling board."""

    account = board_slug(source_account)
    store = store or ReadingStore()
    owns = client is None
    http = client or httpx.Client(timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        response = request_with_retry(lambda: http.get(list_url(account)))
        response.raise_for_status()
        body = response.json()
        rows = [row for row in (body if isinstance(body, list) else []) if isinstance(row, dict) and row.get("uuid")]
        postings = [(posting_url(account, str(row["uuid"])), str(row.get("name") or "").strip()) for row in rows]
        found = descriptions(postings, lambda url: _detail(http, account, url), should_fetch_detail=should_fetch_detail,
                             store=store, now=now())
    finally:
        if owns:
            http.close()
    return [
        CanonicalJob(
            source=SOURCE, company=company_name, external_id=str(row["uuid"]), requisition_id=str(row["uuid"]),
            title=title, location=_location(row), description=found.get(url, ""), official_url=url,
        )
        for row, (url, title) in zip(rows, postings)
        if title
    ]


def company_name_of(fetch: Callable[[str], Any], account: str) -> str | None:
    """The company a board's own postings name, from the first posting's record."""

    try:
        rows = fetch(list_url(account))
        first = next((row for row in rows or [] if isinstance(row, dict) and row.get("uuid")), None)
        detail = fetch(f"{list_url(account)}/{first['uuid']}") if first else None
    except (ValueError, TypeError):
        return None
    name = (detail or {}).get("companyName") if isinstance(detail, dict) else None
    return " ".join(str(name).split()) or None if name else None


__all__ = ["SOURCE", "board_slug", "company_name_of", "fetch_rippling_jobs", "list_url", "posting_url"]
