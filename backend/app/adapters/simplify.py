"""Curated new-grad feed adapter for ACE.

SimplifyJobs publishes two openly-licensed GitHub lists of new-graduate
and internship postings, refreshed continuously:

    New-Grad-Positions/.github/scripts/listings.json
    Summer2026-Internships/.github/scripts/listings.json

Why this lane exists
--------------------

Direct ATS polling reaches employers whose board ACE has an adapter for.
It cannot reach a proprietary careers site. Measured against the live
feed, these hosts are unreachable any other way:

    lifeattiktok.com, jobs.bytedance.com, www.tesla.com,
    jobs.apple.com, oraclecloud.com, careers.amd.com

Apple in particular answers its own API with bot-protection responses,
so a curated public list is the appropriate route rather than the
last resort.

What this lane cannot do
------------------------

The feed carries no job description. Rules that read requirement text --
experience thresholds, export control, language scope -- therefore
cannot fire on these postings, and only title-level rules apply.

Two things keep that honest rather than merely lax:

1. The feed is already curated to new-graduate and internship roles,
   which is exactly ACE's target, so the population is pre-narrowed.
2. Structured fields the feed *does* carry are rendered into the
   description as plain sentences, so the existing deterministic gate
   evaluates them through its normal rules instead of through a second,
   parallel code path that could drift.

A posting marked "Does Not Offer Sponsorship" becomes a sentence the
sponsorship rule already recognises. Nothing new is trusted.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
from typing import Any

import httpx

from backend.app.models.job import CanonicalJob


SIMPLIFY_SOURCE = "simplify"

FEED_URLS: dict[str, str] = {
    "new-grad": (
        "https://raw.githubusercontent.com/"
        "SimplifyJobs/New-Grad-Positions/"
        "dev/.github/scripts/listings.json"
    ),
    "internships": (
        "https://raw.githubusercontent.com/"
        "SimplifyJobs/Summer2026-Internships/"
        "dev/.github/scripts/listings.json"
    ),
}


# The feed's own taxonomy. Hardware is excluded to match ACE's rule that
# hardware-oriented roles are out of scope; Quant and Product are not
# target families.
INCLUDED_CATEGORIES = frozenset(
    {
        "software",
        "software engineering",
        "ai/ml/data",
    }
)


# Feed sponsorship values that state a blocker. Rendered into the
# description so the existing gate rules evaluate them.
SPONSORSHIP_BLOCKER_TEXT: dict[str, str] = {
    "does not offer sponsorship": (
        "This employer will not provide "
        "sponsorship for this role."
    ),
    "u.s. citizenship is required": (
        "Applicants must be a U.S. citizen "
        "for this role."
    ),
}


REQUEST_TIMEOUT_SECONDS = 30.0

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)


def parse_feed_name(
    source_account: str,
) -> str:
    """Validate which curated list a source refers to."""

    normalized = (
        source_account or ""
    ).strip().lower()

    if normalized not in FEED_URLS:
        raise ValueError(
            (
                "Unknown curated feed "
                f"{source_account!r}; expected "
                f"one of {sorted(FEED_URLS)}."
            )
        )

    return normalized


def _parse_posted_at(
    value: object,
) -> datetime | None:
    """Parse the feed's unix posting timestamp."""

    if isinstance(
        value,
        bool,
    ):
        return None

    if not isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return None

    if value <= 0:
        return None

    try:
        return datetime.fromtimestamp(
            float(
                value
            ),
            tz=timezone.utc,
        )

    except (
        OverflowError,
        OSError,
        ValueError,
    ):
        return None


def build_description(
    entry: dict[str, Any],
) -> str:
    """Render the feed's structured fields as plain sentences.

    The feed has no description. Rather than adding a parallel rule
    path for its metadata, the metadata is written as text the existing
    deterministic gate already understands.
    """

    parts: list[str] = [
        (
            "Sourced from a curated "
            "new-graduate listing. Full "
            "requirements are on the "
            "employer's posting."
        ),
    ]

    sponsorship = str(
        entry.get(
            "sponsorship"
        )
        or ""
    ).strip().lower()

    blocker = (
        SPONSORSHIP_BLOCKER_TEXT.get(
            sponsorship
        )
    )

    if blocker:
        parts.append(
            blocker
        )

    degrees = entry.get(
        "degrees"
    )

    if isinstance(
        degrees,
        list,
    ):
        named = [
            str(
                degree
            ).strip()
            for degree in degrees
            if str(
                degree
            ).strip()
        ]

        if named:
            parts.append(
                "Degrees considered: "
                + ", ".join(
                    named
                )
                + "."
            )

    terms = entry.get(
        "terms"
    )

    if isinstance(
        terms,
        list,
    ):
        named_terms = [
            str(
                term
            ).strip()
            for term in terms
            if str(
                term
            ).strip()
        ]

        if named_terms:
            parts.append(
                "Term: "
                + ", ".join(
                    named_terms
                )
                + "."
            )

    return " ".join(
        parts
    )


def _location(
    entry: dict[str, Any],
) -> str:
    """Join the feed's location list."""

    locations = entry.get(
        "locations"
    )

    if not isinstance(
        locations,
        list,
    ):
        return ""

    named = [
        str(
            item
        ).strip()
        for item in locations
        if str(
            item
        ).strip()
    ]

    return "; ".join(
        named
    )


def is_reachable_by_adapter(
    url: str,
) -> bool:
    """Return whether ACE could poll this posting's board directly.

    An employer on a supported ATS belongs in the source catalog, where
    the adapter reads the full description and the whole gate applies.
    Ingesting the same posting from a description-less feed as well
    would duplicate it and vet it less thoroughly.

    This lane is therefore scoped to what direct polling cannot reach.
    """

    # Imported lazily: the discovery package reaches back into
    # scheduling, and importing it at module scope would close a cycle
    # through the dispatcher.
    from backend.app.discovery.detector import (
        detect_source_from_url,
    )

    return (
        detect_source_from_url(
            url
        )
        is not None
    )


def is_included(
    entry: dict[str, Any],
) -> bool:
    """Return whether one feed entry belongs in ACE."""

    if not entry.get(
        "active"
    ):
        return False

    if not entry.get(
        "is_visible",
        True,
    ):
        return False

    category = str(
        entry.get(
            "category"
        )
        or ""
    ).strip().lower()

    if category not in INCLUDED_CATEGORIES:
        return False

    return not is_reachable_by_adapter(
        str(
            entry.get(
                "url"
            )
            or ""
        )
    )


def fetch_simplify_jobs(
    *,
    source_account: str,
    company_name: str = "",
    client: httpx.Client | None = None,
) -> list[CanonicalJob]:
    """Fetch one curated listing feed.

    ``company_name`` is ignored: unlike an employer board this feed spans
    many employers, and each entry carries its own company.
    """

    feed = parse_feed_name(
        source_account
    )

    owns_client = client is None

    http = (
        client
        if client is not None
        else httpx.Client(
            timeout=(
                REQUEST_TIMEOUT_SECONDS
            ),
            headers={
                "User-Agent": USER_AGENT,
                "Accept": (
                    "application/json"
                ),
            },
            follow_redirects=True,
        )
    )

    jobs: list[CanonicalJob] = []

    seen_ids: set[str] = set()

    try:
        response = http.get(
            FEED_URLS[feed]
        )

        response.raise_for_status()

        entries = response.json()

        if not isinstance(
            entries,
            list,
        ):
            return []

        for entry in entries:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            if not is_included(
                entry
            ):
                continue

            external_id = str(
                entry.get(
                    "id"
                )
                or ""
            ).strip()

            title = str(
                entry.get(
                    "title"
                )
                or ""
            ).strip()

            company = str(
                entry.get(
                    "company_name"
                )
                or ""
            ).strip()

            url = str(
                entry.get(
                    "url"
                )
                or ""
            ).strip()

            if not (
                external_id
                and title
                and company
                and url.startswith(
                    "http"
                )
            ):
                continue

            if external_id in seen_ids:
                continue

            seen_ids.add(
                external_id
            )

            jobs.append(
                CanonicalJob(
                    source=SIMPLIFY_SOURCE,
                    company=company,
                    external_id=external_id,
                    requisition_id=None,
                    title=title,
                    location=_location(
                        entry
                    ),
                    description=(
                        build_description(
                            entry
                        )
                    ),
                    official_url=url,
                    posted_at=_parse_posted_at(
                        entry.get(
                            "date_posted"
                        )
                    ),
                    updated_at=_parse_posted_at(
                        entry.get(
                            "date_updated"
                        )
                    ),
                )
            )

    finally:
        if owns_client:
            http.close()

    return jobs
