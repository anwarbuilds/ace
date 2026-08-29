"""Tests for stable ACE job-content hashing."""

from datetime import (
    datetime,
    timezone,
)

from backend.app.models.job import CanonicalJob
from backend.app.persistence.hashing import (
    compute_job_content_hash,
)


def make_job() -> CanonicalJob:
    """Return a representative normalized job."""

    return CanonicalJob(
        source="greenhouse",
        company="Example",
        external_id="123",
        requisition_id="REQ-123",
        title="Software Engineer",
        location="Seattle, Washington",
        description="Build reliable distributed systems.",
        official_url=(
            "https://example.com/jobs/123"
        ),
        posted_at=datetime(
            2026,
            8,
            1,
            tzinfo=timezone.utc,
        ),
        updated_at=datetime(
            2026,
            8,
            2,
            tzinfo=timezone.utc,
        ),
    )


def test_same_job_has_same_hash() -> None:
    job = make_job()

    assert (
        compute_job_content_hash(job)
        == compute_job_content_hash(job)
    )


def test_content_change_changes_hash() -> None:
    original = make_job()

    changed = original.model_copy(
        update={
            "description": (
                "Build reliable AI systems."
            )
        }
    )

    assert (
        compute_job_content_hash(original)
        != compute_job_content_hash(changed)
    )


def test_provider_update_timestamp_does_not_change_hash() -> None:
    original = make_job()

    timestamp_only_change = (
        original.model_copy(
            update={
                "updated_at": datetime(
                    2026,
                    8,
                    20,
                    tzinfo=timezone.utc,
                )
            }
        )
    )

    assert (
        compute_job_content_hash(original)
        == compute_job_content_hash(
            timestamp_only_change
        )
    )