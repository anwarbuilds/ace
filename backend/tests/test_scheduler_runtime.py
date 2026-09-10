"""Tests for ACE automatic scheduler runtime."""

from types import (
    SimpleNamespace,
)

from backend.app.scheduling.registry import (
    SourceRegistry,
)
from backend.app.scheduling import runtime as runtime_module
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
        stale_suppressed_count=1,
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

# ----------------------------------------------------------------------
# Concurrency
#
# Sources are independent: different hosts, different rows, one
# transaction each. Sequential polling let one slow employer block every
# other source behind it.
# ----------------------------------------------------------------------


def test_due_sources_are_polled_concurrently() -> None:
    """A slow source must not block the sources behind it."""

    import threading
    import time as real_time

    sources = tuple(
        SourceDefinition(
            source_type=(
                SourceType.GREENHOUSE
            ),
            source_account=f"board-{index}",
            company_name=f"Company {index}",
        )
        for index in range(6)
    )

    in_flight = 0

    peak = 0

    lock = threading.Lock()

    def poller(
        source: SourceDefinition,
    ):
        nonlocal in_flight, peak

        with lock:
            in_flight += 1
            peak = max(peak, in_flight)

        real_time.sleep(0.05)

        with lock:
            in_flight -= 1

        return make_result()

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            sources
        ),
        poller=poller,
        clock=real_time.monotonic,
        sleeper=lambda _seconds: None,
        concurrency=4,
    )

    result = runtime.run_due_sources()

    assert result.succeeded_count == 6

    # More than one source was genuinely in flight at the same time.
    assert peak > 1

    assert peak <= 4


def test_one_source_failure_does_not_affect_others_concurrently() -> None:
    """Failure isolation must survive the move to threads."""

    import time as real_time

    sources = tuple(
        SourceDefinition(
            source_type=(
                SourceType.GREENHOUSE
            ),
            source_account=f"board-{index}",
            company_name=f"Company {index}",
        )
        for index in range(4)
    )

    def poller(
        source: SourceDefinition,
    ):
        if source.source_account == "board-2":
            raise RuntimeError(
                "provider exploded"
            )

        return make_result()

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            sources
        ),
        poller=poller,
        clock=real_time.monotonic,
        sleeper=lambda _seconds: None,
        concurrency=3,
    )

    result = runtime.run_due_sources()

    assert result.succeeded_count == 3

    assert result.failed_count == 1

    assert (
        result.failed[0].source.source_account
        == "board-2"
    )


def test_every_source_is_rescheduled_after_a_concurrent_cycle() -> None:
    """Both successes and failures get a next-due time."""

    import time as real_time

    sources = tuple(
        SourceDefinition(
            source_type=(
                SourceType.GREENHOUSE
            ),
            source_account=f"board-{index}",
            company_name=f"Company {index}",
        )
        for index in range(3)
    )

    def poller(
        source: SourceDefinition,
    ):
        if source.source_account == "board-1":
            raise RuntimeError(
                "boom"
            )

        return make_result()

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            sources
        ),
        poller=poller,
        clock=real_time.monotonic,
        sleeper=lambda _seconds: None,
        concurrency=3,
    )

    runtime.run_due_sources()

    # Nothing is due again immediately; every source was rescheduled.
    assert (
        runtime.seconds_until_next_poll()
        > 0
    )


# ----------------------------------------------------------------------
# A suspended machine is not a dead scheduler
#
# The user asked why there had been no checks for over an hour. Nothing
# was wrong: the laptop had slept, and time.sleep does not advance while
# suspended, so the scheduler resumed and finished the remainder of its
# sleep. From outside, though, that is indistinguishable from a crash,
# and the container healthcheck cannot tell them apart either -- it was
# suspended too, so on waking it saw a fresh poll and said healthy.
#
# CLOCK_MONOTONIC stops while suspended and CLOCK_BOOTTIME does not, so
# the gap between them is the time spent asleep.
# ----------------------------------------------------------------------


def _sleep_spanning_suspend(
    monkeypatch,
    *,
    suspended_seconds: float,
) -> None:
    """Make the two clocks disagree across the sleep by that much."""

    import time as real_time

    state = {"awake": 0.0, "elapsed": 0.0}

    def clock_gettime(which):
        if which == real_time.CLOCK_BOOTTIME:
            return state["elapsed"]

        return state["awake"]

    monkeypatch.setattr(
        runtime_module.time,
        "clock_gettime",
        clock_gettime,
    )

    return state


def test_a_suspended_machine_is_reported(
    monkeypatch,
    caplog,
) -> None:
    """An hour-long hole in the activity log gets a reason attached."""

    source = make_source(
        poll_interval_seconds=10
    )

    clock = FakeClock()

    state = _sleep_spanning_suspend(
        monkeypatch,
        suspended_seconds=3600,
    )

    def sleeper(
        seconds: float,
    ) -> None:
        # Both clocks advance by the sleep, and only BOOTTIME advances
        # by the hour the machine spent suspended on top of it.
        state["awake"] += seconds
        state["elapsed"] += seconds + 3600

        clock.advance(
            seconds
        )

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                source,
            )
        ),
        poller=lambda _source: make_result(),
        clock=clock,
        sleeper=sleeper,
    )

    with caplog.at_level(
        "WARNING"
    ):
        runtime.run_forever(
            max_cycles=2
        )

    assert any(
        "scheduler_resumed_after_suspend"
        in record.getMessage()
        for record in caplog.records
    )


def test_an_ordinary_sleep_is_not_reported(
    monkeypatch,
    caplog,
) -> None:
    """The common case must stay silent, or the warning means nothing."""

    source = make_source(
        poll_interval_seconds=10
    )

    clock = FakeClock()

    state = _sleep_spanning_suspend(
        monkeypatch,
        suspended_seconds=0,
    )

    def sleeper(
        seconds: float,
    ) -> None:
        state["awake"] += seconds
        state["elapsed"] += seconds

        clock.advance(
            seconds
        )

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                source,
            )
        ),
        poller=lambda _source: make_result(),
        clock=clock,
        sleeper=sleeper,
    )

    with caplog.at_level(
        "WARNING"
    ):
        runtime.run_forever(
            max_cycles=2
        )

    assert not any(
        "scheduler_resumed_after_suspend"
        in record.getMessage()
        for record in caplog.records
    )


# ----------------------------------------------------------------------
# Picking up a source registered while running
#
# The registry used to be a snapshot taken at startup, so a company
# added from the interface sat unpolled until someone restarted the
# scheduler. The row was there and the board was reachable, which made
# it look like a bug rather than a missing step.
# ----------------------------------------------------------------------


def test_a_source_added_while_running_is_picked_up() -> None:
    """What makes adding a company from the interface actually work."""

    first = make_source(
        source_account="one",
        poll_interval_seconds=10,
    )

    second = make_source(
        source_account="two",
        poll_interval_seconds=10,
    )

    clock = FakeClock()

    polled: list[str] = []

    def poller(
        source: SourceDefinition,
    ):
        polled.append(
            source.source_account
        )

        return make_result()

    registries = [
        SourceRegistry(
            (
                first,
            )
        ),
        SourceRegistry(
            (
                first,
                second,
            )
        ),
    ]

    def reload_registry():
        # Grows by one between the first cycle and the second.
        return registries[
            min(
                len(
                    registries
                )
                - 1,
                1,
            )
        ]

    runtime = SchedulerRuntime(
        registry=registries[0],
        poller=poller,
        clock=clock,
        sleeper=clock.advance,
        reload_registry=reload_registry,
    )

    runtime.run_forever(
        max_cycles=2
    )

    assert "two" in polled


def test_a_reload_does_not_reset_an_existing_schedule() -> None:
    """A reload must not re-poll everything it already knew about.

    Otherwise every added company would cause a burst across every
    board, which is neither necessary nor polite.
    """

    source = make_source(
        source_account="one",
        poll_interval_seconds=600,
    )

    clock = FakeClock()

    polled: list[str] = []

    def poller(
        definition: SourceDefinition,
    ):
        polled.append(
            definition.source_account
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
        sleeper=clock.advance,
        reload_registry=lambda: SourceRegistry(
            (
                source,
            )
        ),
    )

    runtime.run_forever(
        max_cycles=3
    )

    # Polled once per interval, not once per reload.
    assert len(
        polled
    ) == 3


def test_a_failing_reload_does_not_stop_the_scheduler() -> None:
    """A database hiccup must not take the scheduler down with it."""

    source = make_source(
        source_account="one",
        poll_interval_seconds=10,
    )

    clock = FakeClock()

    polled: list[str] = []

    def boom():
        raise RuntimeError(
            "database unavailable"
        )

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                source,
            )
        ),
        poller=lambda definition: (
            polled.append(
                definition.source_account
            )
            or make_result()
        ),
        clock=clock,
        sleeper=clock.advance,
        reload_registry=boom,
    )

    runtime.run_forever(
        max_cycles=2
    )

    assert polled
