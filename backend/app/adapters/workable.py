"""Workable: employer boards on apply.workable.com.

Found by the 2026-10-06 audit of feed links ACE could not read: 65
employers on Workable, 22 of whose postings could pass for the user,
reached ACE only through the Simplify feed -- which carries no
description, so a role requiring a SECRET clearance (Avalore's, for
one) passed unread.

Each board's own page calls a public JSON API:

    POST /api/v3/accounts/{account}/jobs     ten a page, "token" to page
    GET  /api/v2/accounts/{account}/jobs/{shortcode}    one posting

robots.txt on apply.workable.com disallows nothing. The account is the
board's slug, the first path segment of any posting link.

Descriptions are fetched only for titles the gate could pass, and kept
between polls in the shared reading store, so each is fetched once a
week. A board that does not finish inside its page budget raises rather
than return part of itself.
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from datetime import (
    datetime,
    timezone,
)
from typing import Any

import httpx

from backend.app.adapters.retry import (
    request_with_retry,
)
from backend.app.models.job import CanonicalJob
from backend.app.verification.employer_page import (
    READ,
    UNREACHABLE,
    Reading,
    ReadingStore,
    _flatten,
    is_stale,
)


SOURCE = "workable"

API = "https://apply.workable.com/api"

# Ten postings a page; 300 pages is 3,000, far past any board seen.
MAX_PAGES = 300

FRESH_DETAILS_PER_POLL = 150

CONCURRENCY = 4

TIMEOUT_SECONDS = 30.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)

EMPLOYMENT_TYPES = {
    "full": "full-time",
    "part": "part-time",
    "contract": "contract",
    "temporary": "contract",
    "internship": "internship",
}


class IncompleteWorkableRead(RuntimeError):
    """A board did not finish inside its page budget."""


def posting_url(
    account: str,
    shortcode: str,
) -> str:
    return f"https://apply.workable.com/{account}/j/{shortcode}/"


def _place(
    location: Any,
) -> str:
    if not isinstance(
        location,
        dict,
    ):
        return ""

    return ", ".join(
        part
        for part in (
            str(location.get("city") or "").strip(),
            str(location.get("region") or "").strip(),
            str(location.get("country") or "").strip(),
        )
        if part
    )


def build_location(
    posting: dict[str, Any],
) -> str:
    """Every visible location, separated by "; "."""

    places: list[str] = []

    for location in posting.get(
        "locations"
    ) or [
        posting.get("location"),
    ]:
        if isinstance(
            location,
            dict,
        ) and location.get("hidden"):
            continue

        place = _place(
            location
        )

        if place and place not in places:
            places.append(
                place
            )

    if posting.get("remote") and not places:
        places.append(
            "Remote"
        )

    return "; ".join(
        places
    )


def build_description(
    detail: dict[str, Any],
) -> str:
    """Description and requirements, as text -- the clearance and
    citizenship lines are usually in the requirements."""

    return "\n\n".join(
        text
        for text in (
            _flatten(
                str(
                    detail.get(field)
                    or ""
                )
            )
            for field in (
                "description",
                "requirements",
            )
        )
        if text
    )


def _posted_at(
    value: Any,
) -> datetime | None:
    try:
        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None


def fetch_workable_jobs(
    *,
    source_account: str,
    company_name: str,
    should_fetch_detail: (
        Callable[[str], bool] | None
    ) = None,
    store: ReadingStore | None = None,
    client: httpx.Client | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(
        timezone.utc
    ),
    max_pages: int = MAX_PAGES,
    fresh_details: int = FRESH_DETAILS_PER_POLL,
) -> list[CanonicalJob]:
    """Read every posting on one Workable board."""

    account = source_account.strip().strip(
        "/"
    )

    if not account or "/" in account:
        raise ValueError(
            (
                "A Workable source account is the board's slug; "
                f"got {source_account!r}."
            )
        )

    store = store or ReadingStore()

    owns_client = client is None

    http = (
        client
        if client is not None
        else httpx.Client(
            timeout=TIMEOUT_SECONDS,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
    )

    try:
        postings = _list_all(
            http,
            account=account,
            max_pages=max_pages,
        )

        urls = {
            str(posting["shortcode"]): posting_url(
                account,
                str(posting["shortcode"]),
            )
            for posting in postings
        }

        wanted = [
            str(posting["shortcode"])
            for posting in postings
            if should_fetch_detail is None
            or should_fetch_detail(
                str(
                    posting.get("title")
                    or ""
                )
            )
        ]

        moment = now()

        stored = store.load(
            [
                urls[shortcode]
                for shortcode in wanted
            ]
        )

        descriptions: dict[str, str] = {
            url: reading.description
            for url, (reading, _checked) in stored.items()
            if reading.status == READ and reading.description
        }

        due = [
            shortcode
            for shortcode in wanted
            if urls[shortcode] not in stored
            or is_stale(
                *stored[urls[shortcode]],
                moment,
            )
        ][
            :fresh_details
        ]

        if due:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=CONCURRENCY,
            ) as pool:
                fresh = dict(
                    zip(
                        due,
                        pool.map(
                            lambda shortcode: _detail(
                                http,
                                account=account,
                                shortcode=shortcode,
                            ),
                            due,
                        ),
                    )
                )

            readings = {
                urls[shortcode]: reading
                for shortcode, reading in fresh.items()
            }

            store.save(
                readings,
                moment=moment,
            )

            for url, reading in readings.items():
                if reading.status == READ and reading.description:
                    descriptions[url] = reading.description

    finally:
        if owns_client:
            http.close()

    jobs: list[CanonicalJob] = []

    for posting in postings:
        shortcode = str(
            posting["shortcode"]
        )

        title = str(
            posting.get("title")
            or ""
        ).strip()

        if not title:
            continue

        url = urls[shortcode]

        jobs.append(
            CanonicalJob(
                source=SOURCE,
                company=company_name,
                external_id=shortcode,
                requisition_id=shortcode,
                title=title,
                location=build_location(
                    posting
                ),
                description=descriptions.get(
                    url,
                    "",
                ),
                official_url=url,
                posted_at=_posted_at(
                    posting.get(
                        "published"
                    )
                ),
                employment_type=EMPLOYMENT_TYPES.get(
                    str(
                        posting.get("type")
                        or ""
                    ).lower()
                ),
            )
        )

    return jobs


def _list_all(
    http: httpx.Client,
    *,
    account: str,
    max_pages: int,
) -> list[dict[str, Any]]:
    postings: list[dict[str, Any]] = []

    seen: set[str] = set()

    token: str | None = None

    for _ in range(
        max_pages
    ):
        body: dict[str, Any] = {
            "query": "",
            "location": [],
            "department": [],
            "worktype": [],
            "remote": [],
        }

        if token:
            body["token"] = token

        response = request_with_retry(
            lambda body=body: http.post(
                f"{API}/v3/accounts/{account}/jobs",
                json=body,
            )
        )

        response.raise_for_status()

        data = response.json()

        for posting in data.get(
            "results"
        ) or []:
            if not isinstance(
                posting,
                dict,
            ) or not posting.get("shortcode"):
                continue

            shortcode = str(
                posting["shortcode"]
            )

            if shortcode in seen:
                continue

            seen.add(
                shortcode
            )

            postings.append(
                posting
            )

        token = data.get(
            "nextPage"
        )

        if not token:
            return postings

    raise IncompleteWorkableRead(
        (
            f"Workable board {account!r} did not finish in "
            f"{max_pages} pages; refusing to treat part of it as "
            "the whole."
        )
    )


def _detail(
    http: httpx.Client,
    *,
    account: str,
    shortcode: str,
) -> Reading:
    try:
        response = request_with_retry(
            lambda: http.get(
                f"{API}/v2/accounts/{account}/jobs/{shortcode}",
            )
        )
    except httpx.HTTPError:
        return Reading(
            UNREACHABLE,
        )

    if response.status_code != 200:
        return Reading(
            UNREACHABLE,
        )

    description = build_description(
        response.json()
    )

    if not description:
        return Reading(
            UNREACHABLE,
        )

    return Reading(
        READ,
        description,
    )
