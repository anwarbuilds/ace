"""Render ACE alert candidates into transport-neutral notifications."""

from datetime import (
    datetime,
    timezone,
)

from backend.app.evaluation.types import (
    AlertDisposition,
    EvaluatedJob,
)
from backend.app.notifications.types import (
    NotificationMessage,
)


def _require_aware_datetime(
    timestamp: datetime,
    *,
    field_name: str,
) -> datetime:
    """Validate and normalize a datetime to UTC."""

    if (
        timestamp.tzinfo is None
        or timestamp.utcoffset() is None
    ):
        raise ValueError(
            (
                f"{field_name} must be "
                "timezone-aware."
            )
        )

    return timestamp.astimezone(
        timezone.utc
    )


def format_timestamp(
    timestamp: datetime | None,
) -> str:
    """Render an exact UTC timestamp."""

    if timestamp is None:
        return "Unknown"

    normalized = (
        _require_aware_datetime(
            timestamp,
            field_name="timestamp",
        )
    )

    return normalized.strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def format_relative_age(
    timestamp: datetime | None,
    *,
    reference_time: datetime,
) -> str:
    """Render the age of a timestamp relative to a reference time."""

    if timestamp is None:
        return "Unknown"

    normalized_timestamp = (
        _require_aware_datetime(
            timestamp,
            field_name="timestamp",
        )
    )

    normalized_reference = (
        _require_aware_datetime(
            reference_time,
            field_name="reference_time",
        )
    )

    total_seconds = max(
        0,
        int(
            (
                normalized_reference
                - normalized_timestamp
            ).total_seconds()
        ),
    )

    if total_seconds < 60:
        unit = (
            "second"
            if total_seconds == 1
            else "seconds"
        )

        return (
            f"{total_seconds} "
            f"{unit} ago"
        )

    total_minutes = (
        total_seconds // 60
    )

    if total_minutes < 60:
        unit = (
            "minute"
            if total_minutes == 1
            else "minutes"
        )

        return (
            f"{total_minutes} "
            f"{unit} ago"
        )

    total_hours = (
        total_minutes // 60
    )

    if total_hours < 24:
        unit = (
            "hour"
            if total_hours == 1
            else "hours"
        )

        return (
            f"{total_hours} "
            f"{unit} ago"
        )

    total_days = (
        total_hours // 24
    )

    unit = (
        "day"
        if total_days == 1
        else "days"
    )

    return (
        f"{total_days} "
        f"{unit} ago"
    )


def render_alert_notification(
    candidate: EvaluatedJob,
    *,
    detected_at: datetime,
) -> NotificationMessage:
    """Render one ACE alert candidate.

    Only jobs already classified with ALERT disposition may enter this
    renderer. Suppressed jobs must never accidentally become delivery
    messages.
    """

    if (
        candidate.alert_disposition
        != AlertDisposition.ALERT
    ):
        raise ValueError(
            (
                "Only ALERT candidates may "
                "be rendered as notifications."
            )
        )

    normalized_detected_at = (
        _require_aware_datetime(
            detected_at,
            field_name="detected_at",
        )
    )

    job = candidate.job
    eligibility = candidate.eligibility

    subject = (
        f"[ACE] "
        f"{candidate.observation_status.value} | "
        f"{eligibility.role_priority.value} | "
        f"{job.title} | "
        f"{job.company}"
    )

    lines: list[str] = [
        "ACE JOB ALERT",
        "",
        job.title,
        job.company,
        job.location,
        "",
        (
            "Change: "
            f"{candidate.observation_status.value}"
        ),
        (
            "Role family: "
            f"{eligibility.role_family.value}"
        ),
        (
            "Priority: "
            f"{eligibility.role_priority.value}"
        ),
        (
            "Eligibility: "
            f"{eligibility.status.value}"
        ),
        "",
        (
            "Posted: "
            f"{format_relative_age(
                job.posted_at,
                reference_time=normalized_detected_at,
            )}"
        ),
        (
            "Posted at: "
            f"{format_timestamp(
                job.posted_at
            )}"
        ),
        (
            "Updated at: "
            f"{format_timestamp(
                job.updated_at
            )}"
        ),
        (
            "ACE detected at: "
            f"{format_timestamp(
                normalized_detected_at
            )}"
        ),
    ]

    if job.requisition_id:
        lines.extend(
            [
                "",
                (
                    "Requisition: "
                    f"{job.requisition_id}"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "Why ACE surfaced this job:",
        ]
    )

    if eligibility.reasons:
        for reason in (
            eligibility.reasons
        ):
            lines.append(
                f"- {reason}"
            )
    else:
        lines.append(
            "- No additional explanation supplied."
        )

    lines.extend(
        [
            "",
            "Official application:",
            job.official_url,
        ]
    )

    return NotificationMessage(
        subject=subject,
        text_body="\n".join(
            lines
        ),
    )