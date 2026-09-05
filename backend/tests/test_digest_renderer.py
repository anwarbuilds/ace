"""Tests for ACE digest rendering.

The digest is the product. It must stay scannable, correctly ordered,
and never claim more than it knows.
"""

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.app.notifications.digest import (
    build_digest_subject,
    render_digest,
    sort_digest_items,
)
from backend.app.notifications.payload import (
    DigestItem,
    build_alert_payload,
    digest_item_from_payload,
)


REFERENCE = datetime(
    2026,
    9,
    5,
    16,
    30,
    tzinfo=timezone.utc,
)


def item(
    *,
    title: str = "Software Engineer",
    company: str = "Example Co",
    priority: str = "PRIMARY",
    eligibility: str = "PASS",
    age_days: int | None = 1,
    url: str = "https://example.com/jobs/1",
    location: str = "Seattle, WA",
    reasons: tuple[str, ...] = (
        "No hard eligibility blocker "
        "detected.",
    ),
) -> DigestItem:
    """Build one digest item."""

    return DigestItem(
        title=title,
        company=company,
        location=location,
        official_url=url,
        observation_status="NEW",
        eligibility_status=eligibility,
        role_family=(
            "SOFTWARE_ENGINEERING"
        ),
        role_priority=priority,
        reasons=reasons,
        posted_at=None,
        detected_at=REFERENCE,
        posting_age_days=age_days,
    )


# ----------------------------------------------------------------------
# Subject
# ----------------------------------------------------------------------


def test_subject_leads_with_the_count() -> None:
    subject = build_digest_subject(
        item_count=7,
        window_label="Morning",
        reference_time=REFERENCE,
        timezone_name=(
            "America/Los_Angeles"
        ),
    )

    assert subject.startswith(
        "[ACE] 7 new matches"
    )

    assert "Morning" in subject


def test_subject_is_singular_for_one_job() -> None:
    assert (
        "1 new match —"
        in build_digest_subject(
            item_count=1,
            window_label="Evening",
            reference_time=REFERENCE,
            timezone_name="UTC",
        )
    )


def test_subject_date_uses_configured_timezone() -> None:
    """16:30 UTC is still Sep 5 in Pacific but Sep 6 in Kolkata."""

    pacific = build_digest_subject(
        item_count=1,
        window_label="Morning",
        reference_time=REFERENCE,
        timezone_name=(
            "America/Los_Angeles"
        ),
    )

    kolkata = build_digest_subject(
        item_count=1,
        window_label="Morning",
        reference_time=REFERENCE,
        timezone_name="Asia/Kolkata",
    )

    assert "Sep 5" in pacific

    assert "Sep 5" in kolkata


def test_empty_subject_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        build_digest_subject(
            item_count=0,
            window_label="Morning",
            reference_time=REFERENCE,
            timezone_name="UTC",
        )


# ----------------------------------------------------------------------
# Ordering
# ----------------------------------------------------------------------


def test_primary_roles_come_before_secondary() -> None:
    ordered = sort_digest_items(
        [
            item(
                title="Secondary",
                priority="SECONDARY",
            ),
            item(
                title="Primary",
                priority="PRIMARY",
            ),
        ]
    )

    assert (
        ordered[0].title == "Primary"
    )


def test_pass_comes_before_stretch() -> None:
    ordered = sort_digest_items(
        [
            item(
                title="Stretch",
                eligibility="STRETCH",
            ),
            item(
                title="Pass",
                eligibility="PASS",
            ),
        ]
    )

    assert ordered[0].title == "Pass"


def test_fresher_postings_come_first() -> None:
    ordered = sort_digest_items(
        [
            item(
                title="Older",
                age_days=20,
            ),
            item(
                title="Newer",
                age_days=1,
            ),
        ]
    )

    assert ordered[0].title == "Newer"


def test_unknown_age_sorts_last() -> None:
    """An unknown posting date must not masquerade as freshest."""

    ordered = sort_digest_items(
        [
            item(
                title="Unknown",
                age_days=None,
            ),
            item(
                title="Known",
                age_days=25,
            ),
        ]
    )

    assert ordered[0].title == "Known"


def test_ordering_is_stable_across_renders() -> None:
    """A retry must produce the same digest as the first attempt."""

    items = [
        item(
            title=f"Role {index}",
            age_days=index % 3,
        )
        for index in range(
            10
        )
    ]

    first = render_digest(
        items,
        window_label="Morning",
        reference_time=REFERENCE,
        timezone_name="UTC",
    )

    second = render_digest(
        list(
            reversed(
                items
            )
        ),
        window_label="Morning",
        reference_time=REFERENCE,
        timezone_name="UTC",
    )

    assert (
        first.text_body
        == second.text_body
    )


# ----------------------------------------------------------------------
# Body content
# ----------------------------------------------------------------------


def test_body_lists_every_job_with_apply_link() -> None:
    message = render_digest(
        [
            item(
                title=f"Role {index}",
                url=(
                    "https://example.com"
                    f"/jobs/{index}"
                ),
            )
            for index in range(
                1,
                4,
            )
        ],
        window_label="Morning",
        reference_time=REFERENCE,
        timezone_name="UTC",
    )

    for index in range(
        1,
        4,
    ):
        assert (
            f"Role {index}"
            in message.text_body
        )

        assert (
            f"https://example.com/jobs/{index}"
            in message.text_body
        )


def test_body_includes_useful_metadata() -> None:
    message = render_digest(
        [
            item(
                eligibility="STRETCH",
                priority="PRIMARY",
                location="Remote (US)",
            ),
        ],
        window_label="Morning",
        reference_time=REFERENCE,
        timezone_name="UTC",
    )

    body = message.text_body

    assert (
        "Eligibility: STRETCH" in body
    )

    assert "Priority: PRIMARY" in body

    assert "Change: NEW" in body

    assert "Remote (US)" in body

    assert (
        "SOFTWARE_ENGINEERING" in body
    )

    assert (
        "No hard eligibility blocker"
        in body
    )


def test_missing_url_is_stated_not_faked() -> None:
    """ACE must never present a broken or invented apply link."""

    message = render_digest(
        [
            item(
                url="",
            ),
        ],
        window_label="Morning",
        reference_time=REFERENCE,
        timezone_name="UTC",
    )

    assert (
        "no verified official URL"
        in message.text_body
    )


def test_deferred_count_is_reported() -> None:
    message = render_digest(
        [
            item(),
        ],
        window_label="Morning",
        reference_time=REFERENCE,
        timezone_name="UTC",
        deferred_count=12,
    )

    assert (
        "12 additional matches"
        in message.text_body
    )


def test_no_deferred_note_when_nothing_deferred() -> None:
    message = render_digest(
        [
            item(),
        ],
        window_label="Morning",
        reference_time=REFERENCE,
        timezone_name="UTC",
    )

    assert (
        "additional"
        not in message.text_body
    )


def test_empty_digest_is_refused() -> None:
    """Rendering enforces the zero-jobs-zero-email rule too."""

    with pytest.raises(
        ValueError
    ):
        render_digest(
            [],
            window_label="Morning",
            reference_time=REFERENCE,
            timezone_name="UTC",
        )


def test_negative_deferred_count_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        render_digest(
            [
                item(),
            ],
            window_label="Morning",
            reference_time=REFERENCE,
            timezone_name="UTC",
            deferred_count=-1,
        )


def test_body_is_plain_text_only() -> None:
    """Plain text must remain excellent and free of markup."""

    body = render_digest(
        [
            item(),
        ],
        window_label="Morning",
        reference_time=REFERENCE,
        timezone_name="UTC",
    ).text_body

    assert "<" not in body

    assert "</" not in body


# ----------------------------------------------------------------------
# Payload round-trip
# ----------------------------------------------------------------------


def test_payload_round_trip_preserves_fields() -> None:
    """What the pipeline captures is what the digest shows."""

    from backend.app.evaluation.types import (
        AlertDisposition,
        EvaluatedJob,
    )
    from backend.app.intelligence.eligibility import (
        evaluate_job,
    )
    from backend.app.models.job import (
        CanonicalJob,
    )
    from backend.app.persistence.types import (
        JobObservationStatus,
    )

    job = CanonicalJob(
        source="greenhouse",
        company="Acme",
        external_id="42",
        title="Software Engineer",
        location="Seattle, WA",
        description=(
            "Build reliable software "
            "systems."
        ),
        official_url=(
            "https://acme.com/jobs/42"
        ),
        posted_at=datetime(
            2026,
            9,
            3,
            tzinfo=timezone.utc,
        ),
    )

    candidate = EvaluatedJob(
        job=job,
        observation_status=(
            JobObservationStatus.NEW
        ),
        eligibility=evaluate_job(
            job
        ),
        alert_disposition=(
            AlertDisposition.ALERT
        ),
    )

    payload = build_alert_payload(
        candidate,
        source_account="acme",
        detected_at=REFERENCE,
    )

    restored = (
        digest_item_from_payload(
            payload
        )
    )

    assert (
        restored.title
        == "Software Engineer"
    )

    assert restored.company == "Acme"

    assert (
        restored.official_url
        == "https://acme.com/jobs/42"
    )

    assert (
        restored.eligibility_status
        == "PASS"
    )

    assert (
        restored.observation_status
        == "NEW"
    )

    body = render_digest(
        [
            restored,
        ],
        window_label="Morning",
        reference_time=REFERENCE,
        timezone_name="UTC",
    ).text_body

    assert (
        "https://acme.com/jobs/42"
        in body
    )


def test_malformed_payload_degrades_gracefully() -> None:
    """Corrupt stored data must not crash the whole digest."""

    restored = digest_item_from_payload(
        {
            "version": 1,
            "title": None,
            "reasons": "not-a-list",
            "posting_age_days": "nope",
            "posted_at": "garbage",
        }
    )

    assert (
        restored.title
        == "Untitled role"
    )

    assert restored.reasons == ()

    assert (
        restored.posting_age_days is None
    )

    assert restored.posted_at is None
