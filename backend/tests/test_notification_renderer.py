"""Tests for ACE notification rendering."""

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
from backend.app.notifications.renderer import (
    format_relative_age,
    render_alert_notification,
)
from backend.app.persistence.types import (
    JobObservationStatus,
)


DETECTED_AT = datetime(
    2026,
    9,
    2,
    18,
    0,
    tzinfo=timezone.utc,
)


def make_candidate(
    *,
    observation_status: (
        JobObservationStatus
    ) = JobObservationStatus.NEW,
    eligibility_status: (
        EligibilityStatus
    ) = EligibilityStatus.PASS,
    role_family: (
        RoleFamily
    ) = RoleFamily.SOFTWARE_ENGINEERING,
    role_priority: (
        RolePriority
    ) = RolePriority.PRIMARY,
    alert_disposition: (
        AlertDisposition
    ) = AlertDisposition.ALERT,
    posted_at: datetime | None = None,
    updated_at: datetime | None = None,
    required_experience_years: (
        int | None
    ) = None,
) -> EvaluatedJob:
    """Create one deterministic evaluated job."""

    if posted_at is None:
        posted_at = (
            DETECTED_AT
            - timedelta(minutes=15)
        )

    if updated_at is None:
        updated_at = posted_at

    if (
        eligibility_status
        == EligibilityStatus.STRETCH
    ):
        reason_codes = (
            EligibilityReasonCode.EXPERIENCE_STRETCH,
        )

        reasons = (
            (
                "Posting requires approximately "
                "3 years of experience."
            ),
        )

    elif (
        eligibility_status
        == EligibilityStatus.REJECT
    ):
        reason_codes = (
            EligibilityReasonCode.SENIOR_TITLE,
        )

        reasons = (
            "Title is clearly senior-level.",
        )

    else:
        reason_codes = (
            EligibilityReasonCode.NO_HARD_BLOCKER,
        )

        reasons = (
            (
                "No hard eligibility blocker "
                "detected."
            ),
        )

    job = CanonicalJob(
        source="greenhouse",
        company="Databricks",
        external_id="123",
        requisition_id="REQ-123",
        title="Software Engineer",
        location="Seattle, Washington",
        description=(
            "Build distributed software systems."
        ),
        official_url=(
            "https://example.com/jobs/123"
        ),
        posted_at=posted_at,
        updated_at=updated_at,
    )

    eligibility = EligibilityDecision(
        status=eligibility_status,
        role_family=role_family,
        role_priority=role_priority,
        reason_codes=reason_codes,
        reasons=reasons,
        required_experience_years=(
            required_experience_years
        ),
    )

    return EvaluatedJob(
        job=job,
        observation_status=(
            observation_status
        ),
        eligibility=eligibility,
        alert_disposition=(
            alert_disposition
        ),
    )


def test_render_primary_new_job() -> None:
    candidate = make_candidate()

    message = render_alert_notification(
        candidate,
        detected_at=DETECTED_AT,
    )

    assert (
        message.subject
        == (
            "[ACE] NEW | PRIMARY | "
            "Software Engineer | Databricks"
        )
    )

    assert (
        "ACE JOB ALERT"
        in message.text_body
    )

    assert (
        "Software Engineer"
        in message.text_body
    )

    assert (
        "Databricks"
        in message.text_body
    )

    assert (
        "Seattle, Washington"
        in message.text_body
    )

    assert (
        "Role family: SOFTWARE_ENGINEERING"
        in message.text_body
    )

    assert (
        "Priority: PRIMARY"
        in message.text_body
    )

    assert (
        "Eligibility: PASS"
        in message.text_body
    )

    assert (
        "Posted: 15 minutes ago"
        in message.text_body
    )

    assert (
        "ACE detected at: "
        "2026-09-02 18:00:00 UTC"
        in message.text_body
    )

    assert (
        "REQ-123"
        in message.text_body
    )

    assert (
        "https://example.com/jobs/123"
        in message.text_body
    )


def test_render_updated_stretch_job() -> None:
    candidate = make_candidate(
        observation_status=(
            JobObservationStatus.UPDATED
        ),
        eligibility_status=(
            EligibilityStatus.STRETCH
        ),
        role_family=(
            RoleFamily.AI_ML_ENGINEERING
        ),
        role_priority=(
            RolePriority.PRIMARY
        ),
        required_experience_years=3,
    )

    message = render_alert_notification(
        candidate,
        detected_at=DETECTED_AT,
    )

    assert (
        "[ACE] UPDATED | PRIMARY"
        in message.subject
    )

    assert (
        "Change: UPDATED"
        in message.text_body
    )

    assert (
        "Role family: AI_ML_ENGINEERING"
        in message.text_body
    )

    assert (
        "Eligibility: STRETCH"
        in message.text_body
    )

    assert (
        "3 years of experience"
        in message.text_body
    )


def test_render_unknown_source_timestamps() -> None:
    candidate = make_candidate(
        posted_at=None,
        updated_at=None,
    )

    job_without_times = (
        candidate.job.model_copy(
            update={
                "posted_at": None,
                "updated_at": None,
            }
        )
    )

    candidate_without_times = (
        EvaluatedJob(
            job=job_without_times,
            observation_status=(
                candidate.observation_status
            ),
            eligibility=(
                candidate.eligibility
            ),
            alert_disposition=(
                candidate.alert_disposition
            ),
        )
    )

    message = render_alert_notification(
        candidate_without_times,
        detected_at=DETECTED_AT,
    )

    assert (
        "Posted: Unknown"
        in message.text_body
    )

    assert (
        "Posted at: Unknown"
        in message.text_body
    )

    assert (
        "Updated at: Unknown"
        in message.text_body
    )


def test_relative_age_clamps_future_timestamp() -> None:
    future_timestamp = (
        DETECTED_AT
        + timedelta(minutes=5)
    )

    assert (
        format_relative_age(
            future_timestamp,
            reference_time=DETECTED_AT,
        )
        == "0 seconds ago"
    )


def test_renderer_rejects_suppressed_candidate() -> None:
    candidate = make_candidate(
        eligibility_status=(
            EligibilityStatus.REJECT
        ),
        alert_disposition=(
            AlertDisposition.SUPPRESS
        ),
    )

    with pytest.raises(
        ValueError,
        match="Only ALERT candidates",
    ):
        render_alert_notification(
            candidate,
            detected_at=DETECTED_AT,
        )


def test_renderer_rejects_naive_detection_time() -> None:
    candidate = make_candidate()

    naive_time = datetime(
        2026,
        9,
        2,
        18,
        0,
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        render_alert_notification(
            candidate,
            detected_at=naive_time,
        )