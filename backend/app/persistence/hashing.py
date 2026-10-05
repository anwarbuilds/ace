"""Stable content hashing for normalized ACE jobs."""

import hashlib
import json
from datetime import (
    datetime,
    timezone,
)

from backend.app.models.job import CanonicalJob


def _serialize_datetime(
    value: datetime | None,
) -> str | None:
    """Convert an optional datetime into a stable ISO representation.

    An aware time is written in UTC. Greenhouse gives "-04:00" offsets
    and the database hands the same instant back in UTC, so hashing the
    literal text made a stored job's hash differ from its ingested one:
    27,950 Greenhouse evaluations looked permanently stale, and every
    re-evaluation redid all of them.
    """

    if value is None:
        return None

    if value.tzinfo is not None:
        value = value.astimezone(
            timezone.utc
        )

    return value.isoformat()


def compute_job_content_hash(
    job: CanonicalJob,
) -> str:
    """Return a deterministic SHA-256 hash of persisted job content.

    Provider update timestamps are intentionally excluded.

    An ATS may update its own timestamp without making a meaningful
    posting-content change. ACE therefore hashes the normalized content
    that matters to users rather than the provider's bookkeeping time.
    """

    payload = {
        "company": job.company,
        "requisition_id": job.requisition_id,
        "title": job.title,
        "location": job.location,
        "description": job.description,
        "official_url": job.official_url,
        "posted_at": _serialize_datetime(
            job.posted_at
        ),
        # Eligibility-relevant, so its own change has to register as a
        # content change and trigger re-evaluation the same way a
        # title or description edit already does. Without this, a job
        # whose employment_type flips from unknown to "contract" on a
        # later poll would sit under a decision made before that was
        # known, since nothing else about the posting changed.
        "employment_type": (
            job.employment_type
        ),
    }

    serialized_payload = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized_payload.encode("utf-8")
    ).hexdigest()