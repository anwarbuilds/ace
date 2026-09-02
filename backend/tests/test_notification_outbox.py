"""Tests for ACE notification-outbox behavior."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.app.evaluation.types import (
    AlertDisposition,
    EvaluatedJob,
)
from backend.app.intelligence.eligibility import (
    EligibilityDecision,
    EligibilityReasonCode,
    EligibilityStatus,
)
from backend.app.intelligence.roles import (
    RoleFamily,
    RolePriority,
)
from backend.app.models.job import (
    CanonicalJob,
)
from backend.app.notifications.outbox import (
    build_notification_dedupe_key,
    enqueue_alert_candidates,
)
from backend.app.persistence.types import (
    JobObservationStatus,
)


DETECTED_AT = datetime(
    2026,
    9,
    2,
    20,
    0,
    tzinfo=timezone.utc,
)


def make_candidate(
    *,
    title: str = "Software Engineer",
    description: str = (
        "Build distributed software systems."
    ),
    observation_status: (
        JobObservationStatus
    ) = JobObservationStatus.NEW,
    updated_at: datetime | None = None,
) -> EvaluatedJob:
    """Create one deterministic ACE alert candidate."""

    if updated_at is None:
        updated_at = (
            DETECTED_AT
            - timedelta(minutes=5)
        )

    job = CanonicalJob(
        source="greenhouse",
        company="Databricks",
        external_id="123",
        requisition_id="REQ-123",
        title=title,
        location="Seattle, Washington",
        description=description,
        official_url=(
            "https://example.com/jobs/123"
        ),
        posted_at=(
            DETECTED_AT
            - timedelta(minutes=10)
        ),
        updated_at=updated_at,
    )

    eligibility = (
        EligibilityDecision(
            status=(
                EligibilityStatus.PASS
            ),
            role_family=(
                RoleFamily
                .SOFTWARE_ENGINEERING
            ),
            role_priority=(
                RolePriority.PRIMARY
            ),
            reason_codes=(
                EligibilityReasonCode
                .NO_HARD_BLOCKER,
            ),
            reasons=(
                (
                    "No hard eligibility "
                    "blocker detected."
                ),
            ),
        )
    )

    return EvaluatedJob(
        job=job,
        observation_status=(
            observation_status
        ),
        eligibility=eligibility,
        alert_disposition=(
            AlertDisposition.ALERT
        ),
    )


class FakeOutboxWriter:
    """In-memory outbox writer used by service tests."""

    def __init__(self) -> None:
        self.keys: set[str] = set()

        self.records: list[
            dict[str, object]
        ] = []

    def enqueue_if_absent(
        self,
        *,
        dedupe_key: str,
        source: str,
        source_account: str,
        external_id: str,
        observation_status: str,
        job_content_hash: str,
        source_updated_at: (
            datetime | None
        ),
        recipient: str,
        subject: str,
        text_body: str,
    ) -> bool:
        if dedupe_key in self.keys:
            return False

        self.keys.add(
            dedupe_key
        )

        self.records.append(
            {
                "dedupe_key": (
                    dedupe_key
                ),
                "source": source,
                "source_account": (
                    source_account
                ),
                "external_id": (
                    external_id
                ),
                "observation_status": (
                    observation_status
                ),
                "job_content_hash": (
                    job_content_hash
                ),
                "source_updated_at": (
                    source_updated_at
                ),
                "recipient": recipient,
                "subject": subject,
                "text_body": text_body,
            }
        )

        return True


def test_enqueue_alert_candidate() -> None:
    writer = FakeOutboxWriter()

    result = enqueue_alert_candidates(
        writer,
        candidates=(
            make_candidate(),
        ),
        source_account="databricks",
        recipient="user@example.com",
        detected_at=DETECTED_AT,
    )

    assert (
        result.candidate_count
        == 1
    )

    assert (
        result.queued_count
        == 1
    )

    assert (
        result.duplicate_count
        == 0
    )

    assert len(
        writer.records
    ) == 1

    record = writer.records[
        0
    ]

    assert (
        record["source"]
        == "greenhouse"
    )

    assert (
        record["source_account"]
        == "databricks"
    )

    assert (
        record["external_id"]
        == "123"
    )

    assert (
        record["observation_status"]
        == "NEW"
    )

    assert (
        record["recipient"]
        == "user@example.com"
    )

    assert (
        "[ACE] NEW | PRIMARY"
        in str(
            record["subject"]
        )
    )

    assert (
        "Official application:"
        in str(
            record["text_body"]
        )
    )


def test_same_event_is_deduplicated_even_when_detection_time_changes() -> None:
    writer = FakeOutboxWriter()

    candidate = make_candidate()

    first = enqueue_alert_candidates(
        writer,
        candidates=(
            candidate,
        ),
        source_account="databricks",
        recipient="user@example.com",
        detected_at=DETECTED_AT,
    )

    second = enqueue_alert_candidates(
        writer,
        candidates=(
            candidate,
        ),
        source_account="databricks",
        recipient="user@example.com",
        detected_at=(
            DETECTED_AT
            + timedelta(minutes=30)
        ),
    )

    assert first.queued_count == 1

    assert second.queued_count == 0

    assert (
        second.duplicate_count
        == 1
    )

    assert len(
        writer.records
    ) == 1


def test_content_change_creates_new_event_identity() -> None:
    original = make_candidate(
        description=(
            "Build distributed systems."
        )
    )

    changed = make_candidate(
        description=(
            "Build distributed systems "
            "and developer infrastructure."
        )
    )

    original_key = (
        build_notification_dedupe_key(
            original,
            source_account="databricks",
            recipient="user@example.com",
        )
    )

    changed_key = (
        build_notification_dedupe_key(
            changed,
            source_account="databricks",
            recipient="user@example.com",
        )
    )

    assert (
        original_key
        != changed_key
    )


def test_lifecycle_change_creates_new_event_identity() -> None:
    new_candidate = make_candidate(
        observation_status=(
            JobObservationStatus.NEW
        )
    )

    updated_candidate = make_candidate(
        observation_status=(
            JobObservationStatus.UPDATED
        )
    )

    new_key = (
        build_notification_dedupe_key(
            new_candidate,
            source_account="databricks",
            recipient="user@example.com",
        )
    )

    updated_key = (
        build_notification_dedupe_key(
            updated_candidate,
            source_account="databricks",
            recipient="user@example.com",
        )
    )

    assert (
        new_key
        != updated_key
    )


def test_blank_recipient_is_rejected() -> None:
    writer = FakeOutboxWriter()

    with pytest.raises(
        ValueError,
        match="recipient",
    ):
        enqueue_alert_candidates(
            writer,
            candidates=(
                make_candidate(),
            ),
            source_account="databricks",
            recipient="   ",
            detected_at=DETECTED_AT,
        )


def test_blank_source_account_is_rejected() -> None:
    writer = FakeOutboxWriter()

    with pytest.raises(
        ValueError,
        match="source_account",
    ):
        enqueue_alert_candidates(
            writer,
            candidates=(
                make_candidate(),
            ),
            source_account="   ",
            recipient="user@example.com",
            detected_at=DETECTED_AT,
        )