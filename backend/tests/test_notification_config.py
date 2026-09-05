"""Tests for ACE notification configuration and worker CLI contracts."""

from datetime import time

import pytest

from backend.app.config import Settings
from backend.app.evaluation.freshness import (
    FreshnessPolicy,
)
from backend.scripts.send_pending_notifications import (
    build_parser,
)


def make_settings(
    **overrides,
) -> Settings:
    """Build settings without reading the developer's real .env."""

    values = {
        "database_url": (
            "postgresql+psycopg://"
            "ace:ace@localhost:5432/ace"
        ),
        "notification_digest_timezone": (
            "America/Los_Angeles"
        ),
        "notification_digest_times": (
            "07:30,17:30"
        ),
        "max_alert_posting_age_days": 30,
        "notification_digest_max_jobs": 100,
        "_env_file": None,
    }

    values.update(
        overrides
    )

    return Settings(
        **values
    )


# ----------------------------------------------------------------------
# Freshness configuration
# ----------------------------------------------------------------------


def test_default_freshness_threshold_is_thirty_days() -> None:
    assert (
        make_settings()
        .max_alert_posting_age_days
        == 30
    )


def test_freshness_threshold_is_configurable() -> None:
    assert (
        make_settings(
            max_alert_posting_age_days=7
        ).max_alert_posting_age_days
        == 7
    )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
    ],
)
def test_invalid_freshness_threshold_is_rejected(
    value: int,
) -> None:
    with pytest.raises(
        Exception
    ):
        make_settings(
            max_alert_posting_age_days=(
                value
            )
        )


def test_settings_build_a_valid_freshness_policy() -> None:
    settings = make_settings(
        max_alert_posting_age_days=14,
        alert_on_unknown_posting_age=True,
    )

    policy = FreshnessPolicy(
        max_posting_age_days=(
            settings
            .max_alert_posting_age_days
        ),
        alert_on_unknown_posting_age=(
            settings
            .alert_on_unknown_posting_age
        ),
    )

    assert (
        policy.max_posting_age_days == 14
    )

    assert (
        policy.alert_on_unknown_posting_age
        is True
    )


# ----------------------------------------------------------------------
# Digest configuration
# ----------------------------------------------------------------------


def test_digest_schedule_is_built_from_settings() -> None:
    schedule = (
        make_settings()
        .digest_schedule
    )

    assert schedule.times == (
        time(
            7,
            30,
        ),
        time(
            17,
            30,
        ),
    )

    assert (
        schedule.timezone_name
        == "America/Los_Angeles"
    )


def test_single_digest_window_is_allowed() -> None:
    assert (
        make_settings(
            notification_digest_times=(
                "06:45"
            )
        )
        .digest_schedule
        .window_count
        == 1
    )


def test_three_digest_windows_are_rejected() -> None:
    """Configuration cannot exceed the daily volume promise."""

    with pytest.raises(
        Exception
    ):
        make_settings(
            notification_digest_times=(
                "06:00,12:00,18:00"
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-time",
        "25:00",
        "07:30,07:30",
    ],
)
def test_invalid_digest_times_are_rejected(
    value: str,
) -> None:
    with pytest.raises(
        Exception
    ):
        make_settings(
            notification_digest_times=(
                value
            )
        )


def test_invalid_digest_timezone_is_rejected() -> None:
    with pytest.raises(
        Exception
    ):
        make_settings(
            notification_digest_timezone=(
                "Not/AZone"
            )
        )


def test_valid_alternative_timezone_is_accepted() -> None:
    assert (
        make_settings(
            notification_digest_timezone=(
                "Asia/Kolkata"
            )
        )
        .digest_schedule
        .timezone_name
        == "Asia/Kolkata"
    )


def test_invalid_digest_size_limit_is_rejected() -> None:
    with pytest.raises(
        Exception
    ):
        make_settings(
            notification_digest_max_jobs=0
        )


# ----------------------------------------------------------------------
# Worker CLI contract
# ----------------------------------------------------------------------


def test_legacy_max_messages_flag_still_parses() -> None:
    """The previous compose command must not break on upgrade."""

    args = build_parser().parse_args(
        [
            "--loop",
            "--max-messages",
            "25",
            "--idle-sleep-seconds",
            "30",
        ]
    )

    assert args.max_jobs == 25

    assert args.loop is True

    assert (
        args.idle_sleep_seconds == 30.0
    )


def test_max_jobs_flag_is_preferred_spelling() -> None:
    args = build_parser().parse_args(
        [
            "--max-jobs",
            "40",
        ]
    )

    assert args.max_jobs == 40


def test_max_jobs_defaults_to_settings() -> None:
    """An unset flag defers to NOTIFICATION_DIGEST_MAX_JOBS."""

    assert (
        build_parser()
        .parse_args(
            []
        )
        .max_jobs
        is None
    )


@pytest.mark.parametrize(
    "argv",
    [
        [
            "--max-messages",
            "0",
        ],
        [
            "--max-jobs",
            "-1",
        ],
        [
            "--idle-sleep-seconds",
            "0",
        ],
        [
            "--now",
            "not-a-timestamp",
        ],
        [
            "--now",
            "2026-09-05T09:00:00",
        ],
    ],
)
def test_invalid_worker_arguments_are_rejected(
    argv: list[str],
) -> None:
    with pytest.raises(
        SystemExit
    ):
        build_parser().parse_args(
            argv
        )


def test_dry_run_flag_is_available() -> None:
    assert (
        build_parser()
        .parse_args(
            [
                "--dry-run",
            ]
        )
        .dry_run
        is True
    )


def test_aware_now_override_is_accepted() -> None:
    args = build_parser().parse_args(
        [
            "--now",
            "2026-09-05T09:00:00+00:00",
        ]
    )

    assert (
        args.now.utcoffset()
        is not None
    )
