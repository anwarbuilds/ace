"""Stable content hashing for normalized ACE jobs."""

import hashlib
import json
from datetime import datetime

from backend.app.models.job import CanonicalJob


def _serialize_datetime(
    value: datetime | None,
) -> str | None:
    """Convert an optional datetime into a stable ISO representation."""

    if value is None:
        return None

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