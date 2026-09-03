"""SmartRecruiters Posting API adapter for ACE.

This adapter retrieves all currently active public postings for one
SmartRecruiters company and converts them into ACE CanonicalJob objects.

SmartRecruiters list responses contain posting summaries. ACE follows
each posting with a detail request because job-ad description sections
are exposed by the posting-detail endpoint.
"""

from __future__ import annotations

from datetime import datetime
import html
import re
from typing import Any
from urllib.parse import quote

import httpx

from backend.app.models.job import CanonicalJob


SMARTRECRUITERS_API_BASE_URL = (
    "https://api.smartrecruiters.com/v1/companies"
)

SMARTRECRUITERS_JOB_HOST = (
    "jobs.smartrecruiters.com"
)

REQUEST_TIMEOUT_SECONDS = 20.0

DEFAULT_PAGE_SIZE = 100

USER_AGENT = (
    "ACE/0.1 "
    "(personal career-intelligence project)"
)


def _clean_html(
    value: str | None,
) -> str:
    """Convert SmartRecruiters job-ad HTML into normalized plain text."""

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


def _parse_datetime(
    value: object,
) -> datetime | None:
    """Parse an optional SmartRecruiters ISO-8601 timestamp."""

    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = value.strip()

    if not normalized:
        return None

    if normalized.endswith(
        "Z"
    ):
        normalized = (
            normalized[:-1]
            + "+00:00"
        )

    try:
        return datetime.fromisoformat(
            normalized
        )

    except ValueError:
        return None


def _location_from_posting(
    posting: dict[str, Any],
) -> str:
    """Build a searchable human-readable SmartRecruiters location."""

    location = posting.get(
        "location"
    )

    if not isinstance(
        location,
        dict,
    ):
        return "Unknown"

    parts: list[str] = []

    for key in (
        "city",
        "region",
        "country",
    ):
        value = location.get(
            key
        )

        if not isinstance(
            value,
            str,
        ):
            continue

        normalized = (
            value.strip()
        )

        if not normalized:
            continue

        if key == "country":
            normalized = (
                normalized.upper()
            )

        if normalized not in parts:
            parts.append(
                normalized
            )

    rendered_location = (
        ", ".join(
            parts
        )
    )

    if (
        location.get(
            "remote"
        )
        is True
    ):
        if rendered_location:
            return (
                "Remote | "
                f"{rendered_location}"
            )

        return "Remote"

    if rendered_location:
        return rendered_location

    return "Unknown"


def _description_from_posting(
    posting: dict[str, Any],
) -> str:
    """Build complete eligibility-searchable job description text.

    Company-description text is deliberately excluded because company
    history can contain unrelated year counts that would create false
    experience-requirement matches.
    """

    job_ad = posting.get(
        "jobAd"
    )

    if not isinstance(
        job_ad,
        dict,
    ):
        return ""

    sections = job_ad.get(
        "sections"
    )

    if not isinstance(
        sections,
        dict,
    ):
        return ""

    parts: list[str] = []

    for section_key in (
        "jobDescription",
        "qualifications",
        "additionalInformation",
    ):
        section = sections.get(
            section_key
        )

        if not isinstance(
            section,
            dict,
        ):
            continue

        raw_text = section.get(
            "text"
        )

        if not isinstance(
            raw_text,
            str,
        ):
            continue

        cleaned_text = _clean_html(
            raw_text
        )

        if not cleaned_text:
            continue

        raw_title = section.get(
            "title"
        )

        if isinstance(
            raw_title,
            str,
        ):
            cleaned_title = _clean_html(
                raw_title
            )

        else:
            cleaned_title = ""

        if cleaned_title:
            parts.append(
                (
                    f"{cleaned_title}\n"
                    f"{cleaned_text}"
                )
            )

        else:
            parts.append(
                cleaned_text
            )

    return "\n\n".join(
        parts
    )


def _require_non_empty_string(
    value: object,
    *,
    field_name: str,
) -> str:
    """Require one provider field to contain a non-empty string."""

    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            (
                "SmartRecruiters posting "
                f"{field_name} is missing."
            )
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            (
                "SmartRecruiters posting "
                f"{field_name} is empty."
            )
        )

    return normalized


def _get_json_object(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, int] | None = None,
) -> dict[str, Any]:
    """GET one SmartRecruiters endpoint and require a JSON object."""

    response = client.get(
        url,
        params=params,
    )

    response.raise_for_status()

    payload = response.json()

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            (
                "SmartRecruiters API returned "
                "a non-object JSON payload."
            )
        )

    return payload


def _canonical_job_from_posting(
    *,
    summary: dict[str, Any],
    detail: dict[str, Any],
    company_identifier: str,
    company_name: str,
) -> CanonicalJob:
    """Convert one SmartRecruiters posting into an ACE CanonicalJob."""

    posting_id = (
        detail.get(
            "id"
        )
        or summary.get(
            "id"
        )
    )

    normalized_posting_id = (
        _require_non_empty_string(
            posting_id,
            field_name="id",
        )
    )

    external_id_value = (
        detail.get(
            "uuid"
        )
        or summary.get(
            "uuid"
        )
        or normalized_posting_id
    )

    external_id = (
        _require_non_empty_string(
            external_id_value,
            field_name="uuid/id",
        )
    )

    title_value = (
        detail.get(
            "name"
        )
        or summary.get(
            "name"
        )
    )

    title = (
        _require_non_empty_string(
            title_value,
            field_name="name",
        )
    )

    requisition_value = (
        detail.get(
            "refNumber"
        )
        or summary.get(
            "refNumber"
        )
        or detail.get(
            "jobId"
        )
    )

    if isinstance(
        requisition_value,
        str,
    ):
        requisition_id = (
            requisition_value.strip()
            or None
        )

    else:
        requisition_id = None

    posting_url = detail.get(
        "postingUrl"
    )

    apply_url = detail.get(
        "applyUrl"
    )

    if (
        isinstance(
            posting_url,
            str,
        )
        and posting_url.strip()
    ):
        official_url = (
            posting_url.strip()
        )

    elif (
        isinstance(
            apply_url,
            str,
        )
        and apply_url.strip()
    ):
        official_url = (
            apply_url.strip()
        )

    else:
        official_url = (
            "https://"
            f"{SMARTRECRUITERS_JOB_HOST}/"
            f"{quote(company_identifier, safe='')}/"
            f"{quote(normalized_posting_id, safe='')}"
        )

    released_date = (
        detail.get(
            "releasedDate"
        )
        or summary.get(
            "releasedDate"
        )
    )

    return CanonicalJob(
        source="smartrecruiters",
        company=company_name,
        external_id=external_id,
        requisition_id=requisition_id,
        title=title,
        location=(
            _location_from_posting(
                detail
            )
        ),
        description=(
            _description_from_posting(
                detail
            )
        ),
        official_url=official_url,
        posted_at=(
            _parse_datetime(
                released_date
            )
        ),
        updated_at=None,
    )


def fetch_smartrecruiters_jobs(
    company_identifier: str,
    company_name: str,
    *,
    client: httpx.Client | None = None,
) -> list[CanonicalJob]:
    """Fetch all active postings for one SmartRecruiters company."""

    normalized_company_identifier = (
        company_identifier.strip()
    )

    normalized_company_name = (
        company_name.strip()
    )

    if not normalized_company_identifier:
        raise ValueError(
            (
                "SmartRecruiters "
                "company_identifier "
                "must not be empty."
            )
        )

    if not normalized_company_name:
        raise ValueError(
            (
                "SmartRecruiters "
                "company_name "
                "must not be empty."
            )
        )

    encoded_company_identifier = quote(
        normalized_company_identifier,
        safe="",
    )

    postings_url = (
        f"{SMARTRECRUITERS_API_BASE_URL}/"
        f"{encoded_company_identifier}/"
        "postings"
    )

    owns_client = (
        client is None
    )

    if client is None:
        client = httpx.Client(
            headers={
                "User-Agent": USER_AGENT,
            },
            timeout=(
                REQUEST_TIMEOUT_SECONDS
            ),
        )

    try:
        summaries: list[
            dict[str, Any]
        ] = []

        offset = 0

        while True:
            payload = _get_json_object(
                client,
                postings_url,
                params={
                    "limit": (
                        DEFAULT_PAGE_SIZE
                    ),
                    "offset": offset,
                },
            )

            content = payload.get(
                "content"
            )

            if not isinstance(
                content,
                list,
            ):
                raise ValueError(
                    (
                        "SmartRecruiters postings "
                        "response is missing "
                        "content list."
                    )
                )

            page_summaries: list[
                dict[str, Any]
            ] = []

            for item in content:
                if not isinstance(
                    item,
                    dict,
                ):
                    raise ValueError(
                        (
                            "SmartRecruiters postings "
                            "response contains a "
                            "non-object posting."
                        )
                    )

                page_summaries.append(
                    item
                )

            summaries.extend(
                page_summaries
            )

            page_count = len(
                page_summaries
            )

            if page_count == 0:
                break

            offset += page_count

            total_found = payload.get(
                "totalFound"
            )

            if (
                isinstance(
                    total_found,
                    int,
                )
                and not isinstance(
                    total_found,
                    bool,
                )
                and offset
                >= total_found
            ):
                break

            if (
                not isinstance(
                    total_found,
                    int,
                )
                and page_count
                < DEFAULT_PAGE_SIZE
            ):
                break

        jobs: list[
            CanonicalJob
        ] = []

        seen_external_ids: set[
            str
        ] = set()

        for summary in summaries:
            posting_id = (
                summary.get(
                    "id"
                )
                or summary.get(
                    "uuid"
                )
            )

            normalized_posting_id = (
                _require_non_empty_string(
                    posting_id,
                    field_name="id",
                )
            )

            detail_url = (
                f"{postings_url}/"
                f"{quote(normalized_posting_id, safe='')}"
            )

            detail = _get_json_object(
                client,
                detail_url,
            )

            if (
                detail.get(
                    "active"
                )
                is False
            ):
                continue

            job = (
                _canonical_job_from_posting(
                    summary=summary,
                    detail=detail,
                    company_identifier=(
                        normalized_company_identifier
                    ),
                    company_name=(
                        normalized_company_name
                    ),
                )
            )

            if (
                job.external_id
                in seen_external_ids
            ):
                continue

            seen_external_ids.add(
                job.external_id
            )

            jobs.append(
                job
            )

        return jobs

    finally:
        if owns_client:
            client.close()
