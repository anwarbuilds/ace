"""Adzuna aggregator adapter for ACE.

Every other adapter reads one company's own board. Adzuna reads a
public job-search aggregator instead, which is the answer to a
different question: not "what did Stripe post", but "what is posted
anywhere, at a company ACE has never heard of".

That is deliberately the only thing this source is for. Companies ACE
already polls directly get a better listing from their own board --
a full description, not a 500-character snippet, and an application
link that goes straight to the employer rather than through an
aggregator's own apply page. Duplicating those from Adzuna would add
noise for no coverage gained, so every result is checked against the
companies ACE already watches directly and dropped if it matches.
That check needs a database read, which is why it lives in the
dispatcher wrapper (``AdzunaSourceFetcher`` in ``scheduling/dispatcher.py``)
rather than here: this module stays a pure HTTP client, like every
other adapter, and is fully testable without a database.

Adzuna's free tier truncates every description to 500 characters with
no per-posting detail call to complete it, unlike Greenhouse or
Eightfold. A posting whose requirements sit past that cut lands in the
gate's "no figure stated" bucket rather than being misjudged, which is
the same conservative treatment already given to any posting ACE could
not read at all -- not a new failure mode, the existing one, reached by
a different door. Title-based signals (an explicit "New Grad" or
numeric level in the title) are unaffected, since titles are never
truncated.

Search terms are deliberately narrow. "software engineer" alone
returned close to six thousand results in a three-day window on this
key, almost all of it mid-career noise the gate would reject one
expensive page at a time. The terms below stay in the dozens to low
hundreds, keeping this within a free-tier daily call budget while
still surfacing the postings actually worth the aggregator's breadth.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import httpx

from backend.app.adapters.retry import request_with_retry
from backend.app.models.job import CanonicalJob


USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project; "
    "https://github.com/anwarbuilds/ace)"
)

REQUEST_TIMEOUT_SECONDS = 25.0

API_BASE = "https://api.adzuna.com/v1/api/jobs"

# Adzuna clamps this server-side regardless of what is requested.
RESULTS_PER_PAGE = 50

# Per query term, per poll. Observed volume for these terms is in the
# dozens to low hundreds over a few days, so this is a wide margin
# rather than a number expected to bind in practice. It exists so a
# future broader term cannot page indefinitely against someone else's
# API and someone else's free-tier quota, which is the user's own,
# not ACE's to spend carelessly.
MAX_POSTINGS_PER_QUERY = 400

# Titles a new graduate would plausibly search for and find. Kept
# narrow on purpose -- see the module docstring for why "software
# engineer" alone is the wrong query.
DEFAULT_QUERY_TERMS = (
    "new grad software engineer",
    "entry level software engineer",
    "early career software engineer",
    "associate software engineer",
    "campus software engineer",
    "graduate software engineer",
)

# A daily poll only needs a small safety margin past one day, to
# survive ACE itself having been offline (its own machine off
# overnight is the documented, expected case) without a gap in
# coverage once it comes back.
MAX_POSTING_AGE_DAYS = 4


def fetch_adzuna_jobs(
    *,
    app_id: str,
    app_key: str,
    country: str = "us",
    query_terms: tuple[str, ...] = (
        DEFAULT_QUERY_TERMS
    ),
    max_days_old: int = (
        MAX_POSTING_AGE_DAYS
    ),
    client: httpx.Client | None = None,
) -> list[CanonicalJob]:
    """Fetch new-grad-shaped postings across every employer Adzuna
    indexes.

    Every job is returned, company exclusion happens one layer up.
    Deduplicated by Adzuna's own posting id, since a posting matching
    two query terms is not two postings.
    """

    key = app_id.strip()

    secret = app_key.strip()

    if not key or not secret:
        raise ValueError(
            "app_id and app_key must "
            "not be empty."
        )

    owns_client = client is None

    session = (
        client
        if client is not None
        else httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
    )

    try:
        by_id: dict[str, dict] = {}

        for term in query_terms:
            for posting in _search(
                session,
                app_id=key,
                app_key=secret,
                country=country,
                query=term,
                max_days_old=max_days_old,
            ):
                posting_id = str(
                    posting.get(
                        "id"
                    )
                    or ""
                )

                if posting_id:
                    by_id[posting_id] = (
                        posting
                    )

        return [
            job
            for posting in by_id.values()
            if (
                job := _to_canonical(
                    posting
                )
            )
            is not None
        ]
    finally:
        if owns_client:
            session.close()


def _search(
    session: httpx.Client,
    *,
    app_id: str,
    app_key: str,
    country: str,
    query: str,
    max_days_old: int,
) -> list[dict]:
    """Page through one query term's results."""

    collected: list[dict] = []

    page = 1

    while len(
        collected
    ) < MAX_POSTINGS_PER_QUERY:
        response = request_with_retry(
            lambda: session.get(
                f"{API_BASE}/{country}"
                f"/search/{page}",
                params={
                    "app_id": app_id,
                    "app_key": app_key,
                    "what": query,
                    "max_days_old": (
                        max_days_old
                    ),
                    "results_per_page": (
                        RESULTS_PER_PAGE
                    ),
                    "content-type": (
                        "application/json"
                    ),
                },
            )
        )

        if response.status_code == 400:
            # Adzuna 400s past the last real page rather than
            # returning an empty list, which is otherwise
            # indistinguishable from a real failure.
            break

        response.raise_for_status()

        results = (
            response.json().get(
                "results"
            )
            or []
        )

        if not results:
            break

        collected.extend(
            results
        )

        if (
            len(
                results
            )
            < RESULTS_PER_PAGE
        ):
            break

        page += 1

    return collected[
        :MAX_POSTINGS_PER_QUERY
    ]


def _created_at(
    posting: dict,
) -> datetime | None:
    """Return the posting's listed creation time."""

    raw = posting.get(
        "created"
    )

    if not raw:
        return None

    try:
        stamp = str(
            raw
        ).replace(
            "Z",
            "+00:00",
        )

        moment = datetime.fromisoformat(
            stamp
        )
    except ValueError:
        return None

    if moment.tzinfo is None:
        moment = moment.replace(
            tzinfo=timezone.utc
        )

    return moment


def _to_canonical(
    posting: dict,
) -> CanonicalJob | None:
    """Normalize one Adzuna result.

    Returns None for a posting missing the fields a job cannot exist
    without, rather than fabricating a placeholder company or title
    that would read as real data.
    """

    posting_id = str(
        posting.get(
            "id"
        )
        or ""
    ).strip()

    title = str(
        posting.get(
            "title"
        )
        or ""
    ).strip()

    company = str(
        (
            posting.get(
                "company"
            )
            or {}
        ).get(
            "display_name"
        )
        or ""
    ).strip()

    url = str(
        posting.get(
            "redirect_url"
        )
        or ""
    ).strip()

    if not (
        posting_id
        and title
        and company
        and url
    ):
        return None

    location = str(
        (
            posting.get(
                "location"
            )
            or {}
        ).get(
            "display_name"
        )
        or ""
    ).strip()

    return CanonicalJob(
        source="adzuna",
        company=company,
        external_id=posting_id,
        requisition_id=None,
        title=title,
        location=location,
        description=str(
            posting.get(
                "description"
            )
            or ""
        ).strip(),
        official_url=url,
        posted_at=_created_at(
            posting
        ),
        # Adzuna exposes no separate update stamp; created is the only
        # date it offers.
        updated_at=None,
        # Only ever "contract" or absent in practice: most postings
        # carry no value here at all, which is treated as unknown
        # rather than assumed full-time. A real Vestwell posting and a
        # real T-Mobile posting both stated "contract" explicitly and
        # passed the gate before this was read at all.
        employment_type=(
            str(
                posting.get(
                    "contract_type"
                )
            ).strip().lower()
            if posting.get(
                "contract_type"
            )
            else None
        ),
    )
