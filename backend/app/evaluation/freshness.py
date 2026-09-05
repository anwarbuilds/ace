"""Alert freshness policy for ACE.

Freshness answers exactly one question:

    Is this observation evidence of a *currently opening* opportunity,
    or merely the first time ACE happened to look at an old posting?

Freshness is deliberately NOT part of the eligibility gate.

    - The eligibility gate decides whether a job belongs to ACE at all.
    - Freshness decides only whether the job is worth interrupting the
      user about right now.

A job suppressed by freshness is still persisted, still active, and
still available to the web application. Freshness controls notification
volume, never inclusion.

Why baseline snapshots need this
--------------------------------

ACE intentionally does not suppress evaluation on a source's first
successful snapshot. Blanket baseline suppression would mean a company
discovered today, with an excellent posting from yesterday, never
produces an alert.

The cost of that decision is that the first snapshot of a source also
reports every long-open posting as NEW, because "NEW" means "new to
ACE", not "recently opened".

Freshness resolves this without reintroducing blanket suppression:

    baseline NEW   -> must additionally look recent
    later NEW      -> appeared after an established snapshot, which is
                      direct evidence that it opened while ACE watched
    REOPENED       -> reopening is itself present-tense evidence
    UPDATED        -> a stale posting receiving a minor edit is still a
                      stale posting

Because a source is baseline exactly once, suppressing its unknown-age
backlog is a one-time cost. Every genuinely new posting from that source
afterwards alerts unconditionally.
"""

from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from enum import Enum

from backend.app.persistence.types import (
    JobObservationStatus,
)


DEFAULT_MAX_ALERT_POSTING_AGE_DAYS = 30


class FreshnessReason(
    str,
    Enum,
):
    """Machine-readable explanation of one freshness decision."""

    APPEARED_AFTER_BASELINE = (
        "APPEARED_AFTER_BASELINE"
    )

    REOPENED_IS_CURRENT_EVIDENCE = (
        "REOPENED_IS_CURRENT_EVIDENCE"
    )

    RECENTLY_POSTED = (
        "RECENTLY_POSTED"
    )

    POSTING_TOO_OLD = (
        "POSTING_TOO_OLD"
    )

    UNKNOWN_POSTING_AGE = (
        "UNKNOWN_POSTING_AGE"
    )

    UNKNOWN_POSTING_AGE_ALLOWED = (
        "UNKNOWN_POSTING_AGE_ALLOWED"
    )


@dataclass(
    frozen=True,
    slots=True,
)
class FreshnessPolicy:
    """Configuration governing alert freshness."""

    max_posting_age_days: int = (
        DEFAULT_MAX_ALERT_POSTING_AGE_DAYS
    )

    alert_on_unknown_posting_age: bool = (
        False
    )

    def __post_init__(self) -> None:
        """Validate freshness configuration."""

        if (
            isinstance(
                self.max_posting_age_days,
                bool,
            )
            or not isinstance(
                self.max_posting_age_days,
                int,
            )
            or self.max_posting_age_days < 1
        ):
            raise ValueError(
                (
                    "max_posting_age_days must "
                    "be a positive integer."
                )
            )

    @property
    def max_posting_age(
        self,
    ) -> timedelta:
        """Return the freshness threshold as a duration."""

        return timedelta(
            days=self.max_posting_age_days
        )


@dataclass(
    frozen=True,
    slots=True,
)
class FreshnessDecision:
    """Explainable result of applying the freshness policy."""

    is_fresh: bool

    reason: FreshnessReason

    posting_age_days: int | None = None

    @property
    def explanation(
        self,
    ) -> str:
        """Return a human-readable explanation of this decision."""

        if (
            self.reason
            is FreshnessReason
            .APPEARED_AFTER_BASELINE
        ):
            return (
                "Posting appeared after an "
                "established snapshot of this "
                "source."
            )

        if (
            self.reason
            is FreshnessReason
            .REOPENED_IS_CURRENT_EVIDENCE
        ):
            return (
                "Posting reopened, which is "
                "current evidence of an open "
                "role."
            )

        if (
            self.reason
            is FreshnessReason
            .RECENTLY_POSTED
        ):
            return (
                "Posting is within the "
                "configured freshness window."
            )

        if (
            self.reason
            is FreshnessReason
            .POSTING_TOO_OLD
        ):
            return (
                "Posting predates the "
                "configured freshness window "
                "and is new to ACE only."
            )

        if (
            self.reason
            is FreshnessReason
            .UNKNOWN_POSTING_AGE_ALLOWED
        ):
            return (
                "Posting age is unknown and "
                "configuration allows alerting "
                "on unknown age."
            )

        return (
            "Posting age is unknown and "
            "cannot be confirmed recent."
        )


def _require_aware_datetime(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    """Require an aware datetime and normalize it to UTC."""

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            (
                f"{field_name} must be "
                "timezone-aware."
            )
        )

    return value.astimezone(
        timezone.utc
    )


def _posting_age_days(
    *,
    posted_at: datetime,
    observed_at: datetime,
) -> int:
    """Return whole days between posting and observation."""

    elapsed = (
        observed_at
        - posted_at
    )

    return max(
        0,
        elapsed.days,
    )


def evaluate_freshness(
    *,
    observation_status: JobObservationStatus,
    is_baseline: bool,
    posted_at: datetime | None,
    observed_at: datetime,
    policy: FreshnessPolicy,
) -> FreshnessDecision:
    """Decide whether one observation may produce an alert.

    ``observed_at`` is the snapshot's deterministic reference instant.
    The wall clock is never consulted here, so re-evaluating the same
    snapshot always yields the same decision.

    The freshness boundary is inclusive: a posting exactly at the
    configured threshold is still considered fresh.
    """

    normalized_observed_at = (
        _require_aware_datetime(
            observed_at,
            field_name="observed_at",
        )
    )

    if (
        observation_status
        is JobObservationStatus.REOPENED
    ):
        return FreshnessDecision(
            is_fresh=True,
            reason=(
                FreshnessReason
                .REOPENED_IS_CURRENT_EVIDENCE
            ),
            posting_age_days=(
                None
                if posted_at is None
                else _posting_age_days(
                    posted_at=(
                        _require_aware_datetime(
                            posted_at,
                            field_name=(
                                "posted_at"
                            ),
                        )
                    ),
                    observed_at=(
                        normalized_observed_at
                    ),
                )
            ),
        )

    if (
        observation_status
        is JobObservationStatus.NEW
        and not is_baseline
    ):
        return FreshnessDecision(
            is_fresh=True,
            reason=(
                FreshnessReason
                .APPEARED_AFTER_BASELINE
            ),
            posting_age_days=(
                None
                if posted_at is None
                else _posting_age_days(
                    posted_at=(
                        _require_aware_datetime(
                            posted_at,
                            field_name=(
                                "posted_at"
                            ),
                        )
                    ),
                    observed_at=(
                        normalized_observed_at
                    ),
                )
            ),
        )

    if posted_at is None:
        if policy.alert_on_unknown_posting_age:
            return FreshnessDecision(
                is_fresh=True,
                reason=(
                    FreshnessReason
                    .UNKNOWN_POSTING_AGE_ALLOWED
                ),
                posting_age_days=None,
            )

        return FreshnessDecision(
            is_fresh=False,
            reason=(
                FreshnessReason
                .UNKNOWN_POSTING_AGE
            ),
            posting_age_days=None,
        )

    normalized_posted_at = (
        _require_aware_datetime(
            posted_at,
            field_name="posted_at",
        )
    )

    age_days = _posting_age_days(
        posted_at=normalized_posted_at,
        observed_at=(
            normalized_observed_at
        ),
    )

    threshold = (
        normalized_observed_at
        - policy.max_posting_age
    )

    if normalized_posted_at >= threshold:
        return FreshnessDecision(
            is_fresh=True,
            reason=(
                FreshnessReason
                .RECENTLY_POSTED
            ),
            posting_age_days=age_days,
        )

    return FreshnessDecision(
        is_fresh=False,
        reason=(
            FreshnessReason
            .POSTING_TOO_OLD
        ),
        posting_age_days=age_days,
    )
