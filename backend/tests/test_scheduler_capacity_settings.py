"""The scheduler's worker count and platform limits are settings (OPS-05)."""

import pytest
from pydantic import ValidationError

from backend.app.config import (
    SCHEDULER_MAX_WORKERS,
    Settings,
    parse_platform_limits,
)


def settings(**values) -> Settings:
    return Settings(
        database_url="sqlite://",
        _env_file=None,
        **values,
    )


def test_defaults_keep_todays_eight_workers_with_slow_platforms_limited() -> None:
    current = settings()

    assert current.scheduler_workers == 8

    assert current.scheduler_platform_limit_map == {
        "workday": 5,
        "oracle_recruiting": 2,
    }


def test_a_measured_step_up_is_a_setting() -> None:
    current = settings(
        scheduler_workers=10,
        scheduler_platform_limits="workday=6, oracle_recruiting=2",
    )

    assert current.scheduler_workers == 10

    assert current.scheduler_platform_limit_map == {
        "workday": 6,
        "oracle_recruiting": 2,
    }


@pytest.mark.parametrize(
    "workers",
    [0, SCHEDULER_MAX_WORKERS + 1],
)
def test_a_worker_count_the_pool_cannot_carry_is_refused(
    workers: int,
) -> None:
    with pytest.raises(ValidationError):
        settings(
            scheduler_workers=workers,
        )


@pytest.mark.parametrize(
    "text",
    ["workday", "workday=0", "workday=five", "=3"],
)
def test_a_mistyped_limit_is_refused_at_startup(
    text: str,
) -> None:
    with pytest.raises(ValidationError):
        settings(
            scheduler_platform_limits=text,
        )


def test_no_limits_is_allowed() -> None:
    assert parse_platform_limits("") == {}
