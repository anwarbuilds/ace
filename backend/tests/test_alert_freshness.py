"""Tests for the ACE alert freshness policy.

Freshness exists to stop historical first-seen postings from producing
alerts, without reintroducing blanket baseline suppression.
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.app.evaluation.freshness import (
    FreshnessPolicy,
    FreshnessReason,
    evaluate_freshness,
)
from backend.app.persistence.types import (
    JobObservationStatus,
)


OBSERVED_AT = datetime(
    2026,
    9,
    5,
    16,
    0,
    tzinfo=timezone.utc,
)


POLICY = FreshnessPolicy(
    max_posting_age_days=30
)


def decide(
    *,
    observation_status=(
        JobObservationStatus.NEW
    ),
    is_baseline: bool = True,
    age_days: float | None = 1.0,
    policy: FreshnessPolicy = POLICY,
):
    """Evaluate freshness for a posting of a given age."""

    posted_at = (
        None
        if age_days is None
        else OBSERVED_AT
        - timedelta(
            days=age_days
        )
    )

    return evaluate_freshness(
        observation_status=(
            observation_status
        ),
        is_baseline=is_baseline,
        posted_at=posted_at,
        observed_at=OBSERVED_AT,
        policy=policy,
    )


# ----------------------------------------------------------------------
# Baseline NEW: the case that produced the historical alert flood
# ----------------------------------------------------------------------


def test_recent_baseline_new_job_still_alerts() -> None:
    """A company discovered today with a fresh role must still alert."""

    decision = decide(
        age_days=2,
    )

    assert decision.is_fresh is True

    assert (
        decision.reason
        is FreshnessReason.RECENTLY_POSTED
    )

    assert decision.posting_age_days == 2


def test_stale_baseline_new_job_is_suppressed() -> None:
    """A 336-day-old posting is new to ACE, not newly opened."""

    decision = decide(
        age_days=336,
    )

    assert decision.is_fresh is False

    assert (
        decision.reason
        is FreshnessReason.POSTING_TOO_OLD
    )

    assert (
        decision.posting_age_days == 336
    )


def test_baseline_boundary_is_inclusive() -> None:
    """A posting exactly at the threshold is still fresh."""

    decision = decide(
        age_days=30,
    )

    assert decision.is_fresh is True

    assert (
        decision.reason
        is FreshnessReason.RECENTLY_POSTED
    )


def test_just_past_boundary_is_suppressed() -> None:
    """One second beyond the threshold is stale."""

    posted_at = (
        OBSERVED_AT
        - timedelta(
            days=30,
            seconds=1,
        )
    )

    decision = evaluate_freshness(
        observation_status=(
            JobObservationStatus.NEW
        ),
        is_baseline=True,
        posted_at=posted_at,
        observed_at=OBSERVED_AT,
        policy=POLICY,
    )

    assert decision.is_fresh is False

    assert (
        decision.reason
        is FreshnessReason.POSTING_TOO_OLD
    )


def test_threshold_is_configurable() -> None:
    """A wider window keeps an otherwise stale posting."""

    decision = decide(
        age_days=45,
        policy=FreshnessPolicy(
            max_posting_age_days=60
        ),
    )

    assert decision.is_fresh is True


# ----------------------------------------------------------------------
# Unknown posting age
# ----------------------------------------------------------------------


def test_unknown_age_on_baseline_is_conservative() -> None:
    """Unknown age on a first snapshot does not pretend to be fresh."""

    decision = decide(
        age_days=None,
    )

    assert decision.is_fresh is False

    assert (
        decision.reason
        is FreshnessReason.UNKNOWN_POSTING_AGE
    )

    assert (
        decision.posting_age_days is None
    )


def test_unknown_age_can_be_opted_into() -> None:
    """Operators may choose to accept unknown-age postings."""

    decision = decide(
        age_days=None,
        policy=FreshnessPolicy(
            max_posting_age_days=30,
            alert_on_unknown_posting_age=(
                True
            ),
        ),
    )

    assert decision.is_fresh is True

    assert (
        decision.reason
        is FreshnessReason
        .UNKNOWN_POSTING_AGE_ALLOWED
    )


# ----------------------------------------------------------------------
# Non-baseline NEW: strong evidence regardless of stated posting date
# ----------------------------------------------------------------------


def test_non_baseline_new_job_always_alerts() -> None:
    """Appearing after an established snapshot is direct evidence."""

    decision = decide(
        is_baseline=False,
        age_days=500,
    )

    assert decision.is_fresh is True

    assert (
        decision.reason
        is FreshnessReason
        .APPEARED_AFTER_BASELINE
    )


def test_non_baseline_new_job_with_unknown_age_alerts() -> None:
    """Missing posted_at must not suppress a genuinely new arrival."""

    decision = decide(
        is_baseline=False,
        age_days=None,
    )

    assert decision.is_fresh is True

    assert (
        decision.reason
        is FreshnessReason
        .APPEARED_AFTER_BASELINE
    )


# ----------------------------------------------------------------------
# REOPENED
# ----------------------------------------------------------------------


def test_reopened_job_is_always_fresh() -> None:
    """Reopening is present-tense evidence of an open role."""

    decision = decide(
        observation_status=(
            JobObservationStatus.REOPENED
        ),
        age_days=400,
    )

    assert decision.is_fresh is True

    assert (
        decision.reason
        is FreshnessReason
        .REOPENED_IS_CURRENT_EVIDENCE
    )


def test_reopened_job_with_unknown_age_is_fresh() -> None:
    """Reopening does not depend on a stated posting date."""

    decision = decide(
        observation_status=(
            JobObservationStatus.REOPENED
        ),
        is_baseline=True,
        age_days=None,
    )

    assert decision.is_fresh is True


# ----------------------------------------------------------------------
# UPDATED
# ----------------------------------------------------------------------


def test_updated_recent_job_alerts() -> None:
    """A meaningful change to a current opening is worth reporting."""

    decision = decide(
        observation_status=(
            JobObservationStatus.UPDATED
        ),
        is_baseline=False,
        age_days=5,
    )

    assert decision.is_fresh is True

    assert (
        decision.reason
        is FreshnessReason.RECENTLY_POSTED
    )


def test_updated_stale_job_is_suppressed() -> None:
    """A minor edit does not make a 478-day-old posting current."""

    decision = decide(
        observation_status=(
            JobObservationStatus.UPDATED
        ),
        is_baseline=False,
        age_days=478,
    )

    assert decision.is_fresh is False

    assert (
        decision.reason
        is FreshnessReason.POSTING_TOO_OLD
    )


# ----------------------------------------------------------------------
# Determinism and validation
# ----------------------------------------------------------------------


def test_future_posting_is_treated_as_fresh() -> None:
    """Provider clock skew must not silently drop a posting."""

    decision = decide(
        age_days=-2,
    )

    assert decision.is_fresh is True

    assert decision.posting_age_days == 0


def test_naive_observed_at_is_rejected() -> None:
    """Deterministic comparison requires an aware reference instant."""

    with pytest.raises(
        ValueError
    ):
        evaluate_freshness(
            observation_status=(
                JobObservationStatus.NEW
            ),
            is_baseline=True,
            posted_at=OBSERVED_AT,
            observed_at=datetime(
                2026,
                9,
                5,
            ),
            policy=POLICY,
        )


def test_naive_posted_at_is_rejected() -> None:
    """A naive posting timestamp is ambiguous and must be refused."""

    with pytest.raises(
        ValueError
    ):
        evaluate_freshness(
            observation_status=(
                JobObservationStatus.NEW
            ),
            is_baseline=True,
            posted_at=datetime(
                2026,
                9,
                1,
            ),
            observed_at=OBSERVED_AT,
            policy=POLICY,
        )


def test_policy_rejects_non_positive_threshold() -> None:
    """A zero-day freshness window is a configuration error."""

    with pytest.raises(
        ValueError
    ):
        FreshnessPolicy(
            max_posting_age_days=0
        )


def test_decision_is_deterministic_across_calls() -> None:
    """Re-evaluating the same observation yields the same answer."""

    first = decide(
        age_days=31,
    )

    second = decide(
        age_days=31,
    )

    assert first == second
