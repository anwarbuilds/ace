"""Structured alert payloads for ACE digest rendering.

An outbox row historically stored only pre-rendered text. That is enough
to send one email per job, but not enough to compose many jobs into one
readable digest.

This module defines the durable structured form of one alert candidate.

The payload is captured at enqueue time, inside the same transaction
that persisted the job lifecycle. A delivered digest therefore reports
exactly what ACE evaluated, even if the employer edits the posting
before the digest is sent.

Rows created before digest delivery existed carry no payload. They are
rendered from their legacy columns instead, so historical outbox
contents remain deliverable and auditable.
"""

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
from typing import Any

from backend.app.evaluation.types import EvaluatedJob


ALERT_PAYLOAD_VERSION = 1


UNKNOWN_VALUE = "UNKNOWN"


def _serialize_datetime(
    value: datetime | None,
) -> str | None:
    """Serialize an optional timestamp as a UTC ISO-8601 string."""

    if value is None:
        return None

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            (
                "Payload timestamps must be "
                "timezone-aware."
            )
        )

    return value.astimezone(
        timezone.utc
    ).isoformat()


def _parse_datetime(
    value: Any,
) -> datetime | None:
    """Parse a payload timestamp, tolerating malformed stored data."""

    if not isinstance(
        value,
        str,
    ):
        return None

    try:
        parsed = datetime.fromisoformat(
            value
        )

    except ValueError:
        return None

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        return parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


@dataclass(
    frozen=True,
    slots=True,
)
class DigestItem:
    """One opportunity as it appears inside a digest email."""

    title: str

    company: str

    location: str

    official_url: str

    observation_status: str

    eligibility_status: str

    role_family: str

    role_priority: str

    reasons: tuple[str, ...] = ()

    posted_at: datetime | None = None

    detected_at: datetime | None = None

    requisition_id: str | None = None

    posting_age_days: int | None = None


def build_alert_payload(
    candidate: EvaluatedJob,
    *,
    source_account: str,
    detected_at: datetime,
) -> dict[str, Any]:
    """Capture one alert candidate as a durable structured payload."""

    job = candidate.job

    eligibility = candidate.eligibility

    freshness = candidate.freshness

    return {
        "version": ALERT_PAYLOAD_VERSION,
        "source": job.source,
        "source_account": source_account,
        "external_id": job.external_id,
        "requisition_id": (
            job.requisition_id
        ),
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "official_url": (
            job.official_url
        ),
        "observation_status": (
            candidate.observation_status.value
        ),
        "eligibility_status": (
            eligibility.status.value
        ),
        "eligibility_reason_codes": [
            code.value
            for code
            in eligibility.reason_codes
        ],
        "reasons": list(
            eligibility.reasons
        ),
        "role_family": (
            eligibility.role_family.value
        ),
        "role_priority": (
            eligibility.role_priority.value
        ),
        "required_experience_years": (
            eligibility
            .required_experience_years
        ),
        "posted_at": _serialize_datetime(
            job.posted_at
        ),
        "updated_at": _serialize_datetime(
            job.updated_at
        ),
        "detected_at": _serialize_datetime(
            detected_at
        ),
        "freshness_reason": (
            None
            if freshness is None
            else freshness.reason.value
        ),
        "posting_age_days": (
            None
            if freshness is None
            else freshness.posting_age_days
        ),
    }


def _coerce_text(
    value: Any,
    *,
    default: str,
) -> str:
    """Return a usable string for rendering."""

    if isinstance(
        value,
        str,
    ):
        stripped = value.strip()

        if stripped:
            return stripped

    return default


def digest_item_from_payload(
    payload: dict[str, Any],
) -> DigestItem:
    """Build a renderable digest item from a stored payload."""

    raw_reasons = payload.get(
        "reasons"
    )

    reasons: tuple[str, ...]

    if isinstance(
        raw_reasons,
        list,
    ):
        reasons = tuple(
            str(reason)
            for reason in raw_reasons
            if str(reason).strip()
        )

    else:
        reasons = ()

    raw_age = payload.get(
        "posting_age_days"
    )

    posting_age_days = (
        raw_age
        if isinstance(
            raw_age,
            int,
        )
        and not isinstance(
            raw_age,
            bool,
        )
        else None
    )

    requisition_id = payload.get(
        "requisition_id"
    )

    return DigestItem(
        title=_coerce_text(
            payload.get(
                "title"
            ),
            default="Untitled role",
        ),
        company=_coerce_text(
            payload.get(
                "company"
            ),
            default="Unknown company",
        ),
        location=_coerce_text(
            payload.get(
                "location"
            ),
            default="Location not stated",
        ),
        official_url=_coerce_text(
            payload.get(
                "official_url"
            ),
            default="",
        ),
        observation_status=_coerce_text(
            payload.get(
                "observation_status"
            ),
            default=UNKNOWN_VALUE,
        ),
        eligibility_status=_coerce_text(
            payload.get(
                "eligibility_status"
            ),
            default=UNKNOWN_VALUE,
        ),
        role_family=_coerce_text(
            payload.get(
                "role_family"
            ),
            default=UNKNOWN_VALUE,
        ),
        role_priority=_coerce_text(
            payload.get(
                "role_priority"
            ),
            default=UNKNOWN_VALUE,
        ),
        reasons=reasons,
        posted_at=_parse_datetime(
            payload.get(
                "posted_at"
            )
        ),
        detected_at=_parse_datetime(
            payload.get(
                "detected_at"
            )
        ),
        requisition_id=(
            requisition_id
            if isinstance(
                requisition_id,
                str,
            )
            and requisition_id.strip()
            else None
        ),
        posting_age_days=(
            posting_age_days
        ),
    )


def digest_item_from_legacy_row(
    *,
    subject: str,
    observation_status: str,
    source_account: str,
    external_id: str,
) -> DigestItem:
    """Build a renderable item for a row that predates payloads.

    Legacy subjects were rendered as:

        [ACE] STATUS | PRIORITY | TITLE | COMPANY

    Parsing that back is deliberately best-effort. The goal is only that
    an old row remains readable and deliverable rather than silently
    dropped from a digest.
    """

    normalized_subject = subject.strip()

    body = normalized_subject

    if body.startswith(
        "[ACE]"
    ):
        body = body[
            len("[ACE]"):
        ].strip()

    parts = [
        part.strip()
        for part in body.split(
            "|"
        )
    ]

    role_priority = UNKNOWN_VALUE

    title = normalized_subject

    company = "Unknown company"

    if len(parts) >= 4:
        role_priority = (
            parts[1]
            or UNKNOWN_VALUE
        )

        title = (
            parts[2]
            or normalized_subject
        )

        company = (
            parts[3]
            or company
        )

    return DigestItem(
        title=title,
        company=company,
        location="Location not stated",
        official_url="",
        observation_status=(
            observation_status
            or UNKNOWN_VALUE
        ),
        eligibility_status=UNKNOWN_VALUE,
        role_family=UNKNOWN_VALUE,
        role_priority=role_priority,
        reasons=(
            (
                "Queued before ACE stored "
                "structured alert payloads; "
                "open the source posting for "
                "full detail."
            ),
        ),
        posted_at=None,
        detected_at=None,
        requisition_id=(
            f"{source_account}"
            f"/{external_id}"
        ),
        posting_age_days=None,
    )
