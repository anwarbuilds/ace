"""Lever Postings API adapter for ACE.

The adapter retrieves all currently published jobs for one Lever site
and converts them into ACE CanonicalJob objects.

Lever has separate global and EU public API hosts. ACE preserves the
original jobs host in SourceDefinition.source_host so the correct API
region can be selected deterministically.
"""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import quote

import httpx

from backend.app.models.job import CanonicalJob


LEVER_GLOBAL_JOB_HOST = "jobs.lever.co"
LEVER_EU_JOB_HOST = "jobs.eu.lever.co"

LEVER_API_HOST_BY_JOB_HOST = {
    LEVER_GLOBAL_JOB_HOST: "api.lever.co",
    LEVER_EU_JOB_HOST: "api.eu.lever.co",
}

REQUEST_TIMEOUT_SECONDS = 20.0

DEFAULT_PAGE_SIZE = 100

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)


def _clean_html(
    value: str | None,
) -> str:
    """Convert a small HTML fragment into normalized plain text."""

    if not value:
        return ""

    decoded = html.unescape(
        value
    )

    without_tags = re.sub(
        r"<[^>]+>",
        " ",
        decoded,
    )

    return re.sub(
        r"\s+",
        " ",
        without_tags,
    ).strip()


def _normalize_source_host(
    source_host: str | None,
) -> str:
    """Validate and normalize the Lever jobs host."""

    if source_host is None:
        raise ValueError(
            (
                "Lever source_host is required. "
                "Expected jobs.lever.co or "
                "jobs.eu.lever.co."
            )
        )

    normalized = (
        source_host
        .strip()
        .lower()
        .rstrip(".")
    )

    if (
        normalized
        not in LEVER_API_HOST_BY_JOB_HOST
    ):
        raise ValueError(
            (
                "Unsupported Lever source_host "
                f"{source_host!r}."
            )
        )

    return normalized


def _location_from_posting(
    posting: dict[str, Any],
) -> str:
    """Extract the best available human-readable location."""

    categories = posting.get(
        "categories"
    )

    if isinstance(
        categories,
        dict,
    ):
        primary = categories.get(
            "location"
        )

        if isinstance(
            primary,
            str,
        ):
            primary = (
                primary.strip()
            )

            if primary:
                return primary

        all_locations = (
            categories.get(
                "allLocations"
            )
        )

        if isinstance(
            all_locations,
            list,
        ):
            normalized_locations: list[
                str
            ] = []

            seen: set[
                str
            ] = set()

            for location in (
                all_locations
            ):
                if not isinstance(
                    location,
                    str,
                ):
                    continue

                normalized = (
                    location.strip()
                )

                if (
                    not normalized
                    or normalized
                    in seen
                ):
                    continue

                seen.add(
                    normalized
                )

                normalized_locations.append(
                    normalized
                )

            if normalized_locations:
                return " | ".join(
                    normalized_locations
                )

    workplace_type = (
        posting.get(
            "workplaceType"
        )
    )

    if (
        isinstance(
            workplace_type,
            str,
        )
        and workplace_type.strip().lower()
        == "remote"
    ):
        return "Remote"

    return "Unknown"


def _description_from_posting(
    posting: dict[str, Any],
) -> str:
    """Build a complete searchable description for ACE eligibility.

    Lever exposes requirements/benefits sections separately from
    descriptionPlain, so ACE includes those sections as well. This is
    important because experience and sponsorship language may appear
    there rather than in the main description.
    """

    parts: list[
        str
    ] = []

    description_plain = (
        posting.get(
            "descriptionPlain"
        )
    )

    if (
        isinstance(
            description_plain,
            str,
        )
        and description_plain.strip()
    ):
        parts.append(
            description_plain.strip()
        )

    elif isinstance(
        posting.get(
            "description"
        ),
        str,
    ):
        description_html = (
            _clean_html(
                posting.get(
                    "description"
                )
            )
        )

        if description_html:
            parts.append(
                description_html
            )

    lists = posting.get(
        "lists"
    )

    if isinstance(
        lists,
        list,
    ):
        for section in lists:
            if not isinstance(
                section,
                dict,
            ):
                continue

            section_name = (
                section.get(
                    "text"
                )
            )

            section_content = (
                section.get(
                    "content"
                )
            )

            section_parts: list[
                str
            ] = []

            if (
                isinstance(
                    section_name,
                    str,
                )
                and section_name.strip()
            ):
                section_parts.append(
                    section_name.strip()
                )

            if isinstance(
                section_content,
                str,
            ):
                normalized_content = (
                    _clean_html(
                        section_content
                    )
                )

                if normalized_content:
                    section_parts.append(
                        normalized_content
                    )

            if section_parts:
                parts.append(
                    "\n".join(
                        section_parts
                    )
                )

    additional_plain = (
        posting.get(
            "additionalPlain"
        )
    )

    if (
        isinstance(
            additional_plain,
            str,
        )
        and additional_plain.strip()
    ):
        parts.append(
            additional_plain.strip()
        )

    elif isinstance(
        posting.get(
            "additional"
        ),
        str,
    ):
        additional_html = (
            _clean_html(
                posting.get(
                    "additional"
                )
            )
        )

        if additional_html:
            parts.append(
                additional_html
            )

    return "\n\n".join(
        parts
    ).strip()


def _posting_to_job(
    posting: dict[str, Any],
    *,
    company_name: str,
) -> CanonicalJob:
    """Convert one Lever posting payload into CanonicalJob."""

    external_id = str(
        posting.get(
            "id"
        )
        or ""
    ).strip()

    if not external_id:
        raise ValueError(
            "Lever posting is missing id."
        )

    title = str(
        posting.get(
            "text"
        )
        or ""
    ).strip()

    if not title:
        raise ValueError(
            (
                "Lever posting "
                f"{external_id!r} "
                "is missing title."
            )
        )

    official_url = str(
        posting.get(
            "hostedUrl"
        )
        or ""
    ).strip()

    if not official_url:
        raise ValueError(
            (
                "Lever posting "
                f"{external_id!r} "
                "is missing hostedUrl."
            )
        )

    return CanonicalJob(
        source="lever",
        company=company_name,
        external_id=external_id,
        requisition_id=None,
        title=title,
        location=(
            _location_from_posting(
                posting
            )
        ),
        description=(
            _description_from_posting(
                posting
            )
        ),
        official_url=official_url,

        # Lever's documented public postings response does not expose
        # a canonical publication/update timestamp. Do not invent one.
        posted_at=None,
        updated_at=None,
    )


def fetch_lever_jobs(
    *,
    source_account: str,
    company_name: str,
    source_host: str | None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[CanonicalJob]:
    """Fetch all currently published jobs from one Lever site."""

    account = (
        source_account.strip()
    )

    if not account:
        raise ValueError(
            "Lever source_account must not be empty."
        )

    company = (
        company_name.strip()
    )

    if not company:
        raise ValueError(
            "Lever company_name must not be empty."
        )

    if page_size <= 0:
        raise ValueError(
            "page_size must be positive."
        )

    normalized_host = (
        _normalize_source_host(
            source_host
        )
    )

    api_host = (
        LEVER_API_HOST_BY_JOB_HOST[
            normalized_host
        ]
    )

    url = (
        f"https://{api_host}"
        "/v0/postings/"
        f"{quote(account, safe='')}"
    )

    jobs: list[
        CanonicalJob
    ] = []

    seen_ids: set[
        str
    ] = set()

    skip = 0

    while True:
        response = httpx.get(
            url,
            params={
                "mode": "json",
                "skip": skip,
                "limit": page_size,
            },
            headers={
                "Accept": (
                    "application/json"
                ),
                "User-Agent": (
                    USER_AGENT
                ),
            },
            timeout=(
                REQUEST_TIMEOUT_SECONDS
            ),
            follow_redirects=True,
        )

        response.raise_for_status()

        payload = response.json()

        if not isinstance(
            payload,
            list,
        ):
            raise ValueError(
                (
                    "Lever postings API "
                    "returned a non-list "
                    "JSON payload."
                )
            )

        if not payload:
            break

        page_new_ids = 0

        for raw_posting in payload:
            if not isinstance(
                raw_posting,
                dict,
            ):
                raise ValueError(
                    (
                        "Lever postings API "
                        "returned a non-object "
                        "posting."
                    )
                )

            job = _posting_to_job(
                raw_posting,
                company_name=company,
            )

            if (
                job.external_id
                in seen_ids
            ):
                continue

            seen_ids.add(
                job.external_id
            )

            page_new_ids += 1

            jobs.append(
                job
            )

        if len(
            payload
        ) < page_size:
            break

        if page_new_ids == 0:
            raise RuntimeError(
                (
                    "Lever pagination "
                    "did not advance."
                )
            )

        skip += len(
            payload
        )

    return jobs
