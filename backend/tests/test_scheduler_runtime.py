"""Tests for ACE automatic scheduler runtime."""

from types import (
    SimpleNamespace,
)

from backend.app.scheduling.registry import (
    SourceRegistry,
)
from backend.app.scheduling.runtime import (
    SchedulerRuntime,
)
from backend.app.scheduling.types import (
    SourceDefinition,
    SourceType,
)


class FakeClock:
    """Mutable deterministic monotonic clock."""

    def __init__(
        self,
        *,
        now: float = 100.0,
    ) -> None:
        self.now = now

    def __call__(
        self,
    ) -> float:
        return self.now

    def advance(
        self,
        seconds: float,
    ) -> None:
        self.now += seconds


def make_source(
    *,
    source_account: str = "databricks",
    company_name: str = "Databricks",
    enabled: bool = True,
    poll_interval_seconds: int = 300,
) -> SourceDefinition:
    """Create one scheduler source."""

    return SourceDefinition(
        source_type=(
            SourceType.GREENHOUSE
        ),
        source_account=(
            source_account
        ),
        company_name=(
            company_name
        ),
        enabled=enabled,
        poll_interval_seconds=(
            poll_interval_seconds
        ),
    )


def make_result():
    """Create the result shape consumed by scheduler logging."""

    return SimpleNamespace(
        fetched_count=10,
        evaluated_count=2,
        alert_candidate_count=1,
        queued_notification_count=1,
    )


def test_runtime_polls_enabled_source_immediately() -> None:
    source = make_source()

    calls: list[
        SourceDefinition
    ] = []

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                source,
            )
        ),
        poller=lambda configured_source: (
            calls.append(
                configured_source
            )
            or make_result()
        ),
        clock=FakeClock(),
        sleeper=lambda _seconds: None,
    )

    result = (
        runtime.run_due_sources()
    )

    assert calls == [
        source,
    ]

    assert (
        result.attempted_count
        == 1
    )

    assert (
        result.succeeded_count
        == 1
    )

    assert (
        result.failed_count
        == 0
    )


def test_runtime_skips_disabled_sources() -> None:
    source = make_source(
        enabled=False
    )

    calls: list[
        SourceDefinition
    ] = []

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                source,
            )
        ),
        poller=lambda configured_source: (
            calls.append(
                configured_source
            )
            or make_result()
        ),
        clock=FakeClock(),
        sleeper=lambda _seconds: None,
    )

    result = (
        runtime.run_due_sources()
    )

    assert calls == []

    assert (
        result.attempted_count
        == 0
    )

    assert (
        runtime.seconds_until_next_poll()
        is None
    )


def test_runtime_records_success_summary_and_duration() -> None:
    source = make_source()

    clock = FakeClock()

    def poller(
        _source: SourceDefinition,
    ):
        clock.advance(
            2.5
        )

        return make_result()

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                source,
            )
        ),
        poller=poller,
        clock=clock,
        sleeper=lambda _seconds: None,
    )

    result = (
        runtime.run_due_sources()
    )

    success = (
        result.succeeded[
            0
        ]
    )

    assert (
        success.source
        is source
    )

    assert (
        success.duration_seconds
        == 2.5
    )

    assert (
        success.result.fetched_count
        == 10
    )


def test_source_failure_does_not_block_later_source() -> None:
    first = make_source(
        source_account="first",
        company_name="First",
    )

    second = make_source(
        source_account="second",
        company_name="Second",
    )

    calls: list[
        str
    ] = []

    def poller(
        source: SourceDefinition,
    ):
        calls.append(
            source.source_account
        )

        if (
            source.source_account
            == "first"
        ):
            raise RuntimeError(
                "synthetic failure"
            )

        return make_result()

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                first,
                second,
            )
        ),
        poller=poller,
        clock=FakeClock(),
        sleeper=lambda _seconds: None,
    )

    result = (
        runtime.run_due_sources()
    )

    assert calls == [
        "first",
        "second",
    ]

    assert (
        result.succeeded_count
        == 1
    )

    assert (
        result.failed_count
        == 1
    )

    failure = (
        result.failed[
            0
        ]
    )

    assert (
        failure.source
        is first
    )

    assert (
        failure.error_type
        == "RuntimeError"
    )

    assert (
        failure.error_message
        == "synthetic failure"
    )


def test_successful_source_is_rescheduled_from_completion_time() -> None:
    source = make_source(
        poll_interval_seconds=300
    )

    clock = FakeClock()

    calls = 0

    def poller(
        _source: SourceDefinition,
    ):
        nonlocal calls

        calls += 1

        clock.advance(
            5
        )

        return make_result()

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                source,
            )
        ),
        poller=poller,
        clock=clock,
        sleeper=lambda _seconds: None,
    )

    runtime.run_due_sources()

    assert calls == 1

    assert (
        runtime.seconds_until_next_poll()
        == 300
    )

    clock.advance(
        299
    )

    not_due = (
        runtime.run_due_sources()
    )

    assert (
        not_due.attempted_count
        == 0
    )

    clock.advance(
        1
    )

    due = (
        runtime.run_due_sources()
    )

    assert (
        due.attempted_count
        == 1
    )

    assert calls == 2


def test_failed_source_is_also_rescheduled() -> None:
    source = make_source(
        poll_interval_seconds=60
    )

    clock = FakeClock()

    calls = 0

    def poller(
        _source: SourceDefinition,
    ):
        nonlocal calls

        calls += 1

        raise RuntimeError(
            "provider unavailable"
        )

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                source,
            )
        ),
        poller=poller,
        clock=clock,
        sleeper=lambda _seconds: None,
    )

    first = (
        runtime.run_due_sources()
    )

    assert (
        first.failed_count
        == 1
    )

    assert (
        runtime.seconds_until_next_poll()
        == 60
    )

    immediate_retry = (
        runtime.run_due_sources()
    )

    assert (
        immediate_retry.attempted_count
        == 0
    )

    clock.advance(
        60
    )

    second = (
        runtime.run_due_sources()
    )

    assert (
        second.failed_count
        == 1
    )

    assert calls == 2


def test_seconds_until_next_poll_uses_earliest_source() -> None:
    slow = make_source(
        source_account="slow",
        company_name="Slow",
        poll_interval_seconds=300,
    )

    fast = make_source(
        source_account="fast",
        company_name="Fast",
        poll_interval_seconds=60,
    )

    clock = FakeClock()

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                slow,
                fast,
            )
        ),
        poller=lambda _source: (
            make_result()
        ),
        clock=clock,
        sleeper=lambda _seconds: None,
    )

    runtime.run_due_sources()

    assert (
        runtime.seconds_until_next_poll()
        == 60
    )


def test_run_forever_sleeps_and_repeats() -> None:
    source = make_source(
        poll_interval_seconds=10
    )

    clock = FakeClock()

    calls = 0

    sleep_calls: list[
        float
    ] = []

    def poller(
        _source: SourceDefinition,
    ):
        nonlocal calls

        calls += 1

        return make_result()

    def sleeper(
        seconds: float,
    ) -> None:
        sleep_calls.append(
            seconds
        )

        clock.advance(
            seconds
        )

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                source,
            )
        ),
        poller=poller,
        clock=clock,
        sleeper=sleeper,
    )

    runtime.run_forever(
        max_cycles=2
    )

    assert calls == 2

    assert sleep_calls == [
        10,
    ]