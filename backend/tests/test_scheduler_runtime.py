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


def test_an_edited_source_is_picked_up_without_a_restart() -> None:
    """Editing a source changes no identity, so nothing noticed it.

    The reload compared only which sources existed, not what they
    said. A corrected company name, a changed poll interval, a fixed
    host: all were read once and then ignored for the life of the
    process.

    That is how 793 Visa postings kept being written under the
    employer name "myworkdayjobs" after the catalog had been
    corrected. Every poll re-applied the stale definition, so fixing
    the rows by hand did not hold either.
    """

    stale = make_source(
        source_account="visa/Visa",
        company_name="myworkdayjobs",
    )

    corrected = make_source(
        source_account="visa/Visa",
        company_name="Visa",
    )

    clock = FakeClock()

    seen: list[str] = []

    def poller(
        definition: SourceDefinition,
    ):
        seen.append(
            definition.company_name
        )

        return make_result()

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                stale,
            )
        ),
        poller=poller,
        clock=clock,
        sleeper=clock.advance,
        reload_registry=lambda: SourceRegistry(
            (
                corrected,
            )
        ),
    )

    runtime.run_forever(
        max_cycles=3
    )

    assert seen, "the source was never polled at all"

    assert seen[-1] == "Visa", (
        "the scheduler kept polling under the name it first read, "
        f"so the correction never took effect: {seen}"
    )


def test_an_unchanged_registry_is_not_reloaded() -> None:
    """The early return still has to earn its place.

    Treating every cycle as a change would rebuild the source list
    forever and reset nothing usefully, so a reload that returns the
    same definitions must still be a no-op.
    """

    source = make_source(
        source_account="one",
        poll_interval_seconds=600,
    )

    clock = FakeClock()

    polled: list[str] = []

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
        reload_registry=lambda: SourceRegistry(
            (
                source,
            )
        ),
    )

    runtime.run_forever(
        max_cycles=3
    )

    assert len(
        polled
    ) == 3, "an unchanged reload disturbed the schedule"


# --- resuming the schedule after a restart -------------------------

from datetime import (  # noqa: E402
    datetime,
    timedelta,
    timezone,
)

import httpx  # noqa: E402
import time  # noqa: E402


RESTARTED_AT = datetime(
    2026,
    10,
    4,
    17,
    45,
    tzinfo=timezone.utc,
)


def _runtime_resuming(
    source: SourceDefinition,
    last_polled,
    clock: FakeClock,
    poller=None,
) -> SchedulerRuntime:
    return SchedulerRuntime(
        registry=SourceRegistry(
            (
                source,
            )
        ),
        poller=poller
        or (
            lambda _source: make_result()
        ),
        clock=clock,
        sleeper=lambda _seconds: None,
        last_polled=last_polled,
        wall_clock=lambda: RESTARTED_AT,
    )


def test_a_restart_waits_out_a_recent_poll() -> None:
    """A deploy used to re-poll every board at once; three in twenty
    minutes got ACE refused by Eightfold on every tenant."""

    source = make_source(
        poll_interval_seconds=900,
    )

    clock = FakeClock()

    runtime = _runtime_resuming(
        source,
        lambda: {
            (
                "greenhouse",
                "databricks",
            ): RESTARTED_AT
            - timedelta(
                seconds=180,
            ),
        },
        clock,
    )

    assert (
        runtime.run_due_sources().attempted_count
        == 0
    )

    assert (
        runtime.seconds_until_next_poll()
        == 720
    )

    clock.advance(
        720
    )

    assert (
        runtime.run_due_sources().succeeded_count
        == 1
    )


def test_a_source_the_machine_slept_through_goes_first() -> None:
    """Overdue is overdue: eight hours with the lid shut must not wait
    another interval."""

    source = make_source(
        poll_interval_seconds=900,
    )

    runtime = _runtime_resuming(
        source,
        lambda: {
            (
                "greenhouse",
                "databricks",
            ): RESTARTED_AT
            - timedelta(
                hours=8,
            ),
        },
        FakeClock(),
    )

    assert (
        runtime.run_due_sources().succeeded_count
        == 1
    )


def test_a_source_never_polled_goes_first() -> None:
    runtime = _runtime_resuming(
        make_source(),
        lambda: {},
        FakeClock(),
    )

    assert (
        runtime.run_due_sources().succeeded_count
        == 1
    )


def test_an_unreadable_history_means_everything_is_due() -> None:
    """Not knowing when a source last polled costs a burst, never a
    gap."""

    def unreadable():
        raise RuntimeError(
            "database unavailable"
        )

    runtime = _runtime_resuming(
        make_source(),
        unreadable,
        FakeClock(),
    )

    assert (
        runtime.run_due_sources().succeeded_count
        == 1
    )


def test_a_poll_stamped_in_the_future_waits_one_interval() -> None:
    source = make_source(
        poll_interval_seconds=900,
    )

    runtime = _runtime_resuming(
        source,
        lambda: {
            (
                "greenhouse",
                "databricks",
            ): RESTARTED_AT
            + timedelta(
                hours=5,
            ),
        },
        FakeClock(),
    )

    assert (
        runtime.seconds_until_next_poll()
        == 900
    )


# --- backing off a source that refuses ACE -------------------------


def _refusal(
    status: int,
) -> httpx.HTTPStatusError:
    request = httpx.Request(
        "GET",
        "https://jobs.example.com/api/pcsx/search",
    )

    return httpx.HTTPStatusError(
        f"{status}",
        request=request,
        response=httpx.Response(
            status,
            request=request,
        ),
    )


def test_a_refused_source_is_asked_less_often_until_it_answers() -> None:
    """Eightfold answered 405 on every tenant at once. Asking again on
    the usual schedule keeps knocking on a door just shut."""

    source = make_source(
        poll_interval_seconds=900,
    )

    clock = FakeClock()

    answers = [
        _refusal(405),
        _refusal(405),
        None,
        _refusal(429),
    ]

    def poller(
        _source: SourceDefinition,
    ):
        answer = answers.pop(
            0
        )

        if answer is not None:
            raise answer

        return make_result()

    runtime = _runtime_resuming(
        source,
        lambda: {},
        clock,
        poller,
    )

    # Refused: twice the interval.
    assert (
        runtime.run_due_sources().failed_count
        == 1
    )

    assert (
        runtime.seconds_until_next_poll()
        == 1800
    )

    clock.advance(
        1800
    )

    # Refused again: four times.
    runtime.run_due_sources()

    assert (
        runtime.seconds_until_next_poll()
        == 3600
    )

    clock.advance(
        3600
    )

    # Answered: back to the interval, and the count starts over.
    assert (
        runtime.run_due_sources().succeeded_count
        == 1
    )

    assert (
        runtime.seconds_until_next_poll()
        == 900
    )

    clock.advance(
        900
    )

    runtime.run_due_sources()

    assert (
        runtime.seconds_until_next_poll()
        == 1800
    )


def test_the_backoff_stops_growing_at_the_cap() -> None:
    source = make_source(
        poll_interval_seconds=900,
    )

    clock = FakeClock()

    def poller(
        _source: SourceDefinition,
    ):
        raise _refusal(403)

    runtime = _runtime_resuming(
        source,
        lambda: {},
        clock,
        poller,
    )

    for _ in range(12):
        runtime.run_due_sources()

        clock.advance(
            runtime.seconds_until_next_poll()
        )

    runtime.run_due_sources()

    assert (
        runtime.seconds_until_next_poll()
        == runtime_module.REFUSAL_BACKOFF_CAP_SECONDS
    )


def test_a_wrapped_refusal_is_still_a_refusal() -> None:
    """An adapter that raises its own error from the HTTP one is still
    being refused."""

    source = make_source(
        poll_interval_seconds=900,
    )

    class AdapterError(Exception):
        pass

    def poller(
        _source: SourceDefinition,
    ):
        try:
            raise _refusal(405)
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "board unavailable"
            ) from exc

    runtime = _runtime_resuming(
        source,
        lambda: {},
        FakeClock(),
        poller,
    )

    runtime.run_due_sources()

    assert (
        runtime.seconds_until_next_poll()
        == 1800
    )


def test_an_ordinary_failure_keeps_its_interval() -> None:
    """A 500 or a timeout is "not now", not "not you"."""

    source = make_source(
        poll_interval_seconds=900,
    )

    def poller(
        _source: SourceDefinition,
    ):
        raise _refusal(503)

    runtime = _runtime_resuming(
        source,
        lambda: {},
        FakeClock(),
        poller,
    )

    runtime.run_due_sources()

    assert (
        runtime.seconds_until_next_poll()
        == 900
    )


# --- maintenance between cycles --------------------------------------

import threading  # noqa: E402


def _runtime_with_maintenance(
    maintenance,
    clock: FakeClock,
    *,
    interval: float = 3600,
) -> SchedulerRuntime:
    def sleeper(
        seconds: float,
    ) -> None:
        clock.advance(
            seconds
        )

    return SchedulerRuntime(
        registry=SourceRegistry(
            (
                make_source(
                    poll_interval_seconds=600,
                ),
            )
        ),
        poller=lambda _source: make_result(),
        clock=clock,
        sleeper=sleeper,
        maintenance=maintenance,
        maintenance_interval_seconds=interval,
    )


def test_maintenance_runs_on_its_own_schedule() -> None:
    """Once at the start, then once per interval -- not per cycle."""

    clock = FakeClock()

    finished = threading.Semaphore(0)

    def maintenance() -> None:
        finished.release()

    # Nine cycles, 600 s apart, span 4800 s: maintenance every 3600 s
    # runs twice, where once per cycle would be eight times.
    runtime = _runtime_with_maintenance(
        maintenance,
        clock,
    )

    runtime.run_forever(
        max_cycles=9,
    )

    assert finished.acquire(
        timeout=5,
    )

    assert finished.acquire(
        timeout=5,
    )

    assert not finished.acquire(
        timeout=0.3,
    )


def test_slow_maintenance_does_not_hold_up_polling() -> None:
    """It reads other people's websites. One slow site must not delay
    the five-minute sources behind it."""

    clock = FakeClock()

    release = threading.Event()

    started = threading.Event()

    def maintenance() -> None:
        started.set()

        release.wait(
            timeout=10,
        )

    runtime = _runtime_with_maintenance(
        maintenance,
        clock,
        interval=600,
    )

    done = threading.Event()

    def run() -> None:
        runtime.run_forever(
            max_cycles=4,
        )

        done.set()

    threading.Thread(
        target=run,
        daemon=True,
    ).start()

    try:
        assert started.wait(
            timeout=5,
        )

        # Every cycle completes while maintenance is still stuck.
        assert done.wait(
            timeout=5,
        )

    finally:
        release.set()


def test_maintenance_still_running_is_not_started_again() -> None:
    clock = FakeClock()

    release = threading.Event()

    starts: list[float] = []

    def maintenance() -> None:
        starts.append(
            clock.now
        )

        release.wait(
            timeout=10,
        )

    # Due every cycle, but the first never finishes during the run.
    runtime = _runtime_with_maintenance(
        maintenance,
        clock,
        interval=1,
    )

    try:
        runtime.run_forever(
            max_cycles=5,
        )

        assert len(starts) == 1

    finally:
        release.set()


def test_failing_maintenance_does_not_stop_the_scheduler() -> None:
    clock = FakeClock()

    polls = 0

    def poller(
        _source: SourceDefinition,
    ):
        nonlocal polls

        polls += 1

        return make_result()

    def maintenance() -> None:
        raise RuntimeError(
            "diagnosis failed"
        )

    def sleeper(
        seconds: float,
    ) -> None:
        clock.advance(
            seconds
        )

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                make_source(
                    poll_interval_seconds=600,
                ),
            )
        ),
        poller=poller,
        clock=clock,
        sleeper=sleeper,
        maintenance=maintenance,
        maintenance_interval_seconds=1,
    )

    runtime.run_forever(
        max_cycles=4,
    )

    assert polls == 4


# --- a slow source must not hold up the rest -------------------------
#
# Accenture's poll takes six minutes every fifteen. The loop used to
# wait for every source it started before starting any more, so for
# those six minutes the five-minute sources -- the ones that exist to
# catch a posting early -- were not polled at all.


def _blocking_poller(
    release: threading.Event,
    calls: dict[str, int],
    *,
    slow_account: str = "accenture",
    started: threading.Event | None = None,
    started_at: list[datetime] | None = None,
):
    def poller(
        source: SourceDefinition,
    ):
        calls[source.source_account] = (
            calls.get(
                source.source_account,
                0,
            )
            + 1
        )

        if source.source_account == slow_account:
            if started_at is not None:
                started_at.append(
                    datetime.now(
                        timezone.utc
                    )
                )

            if started is not None:
                started.set()

            assert release.wait(
                timeout=10,
            )

        return make_result()

    return poller


def _sources_fast_and_slow(
    *,
    slow_interval: int = 900,
) -> SourceRegistry:
    return SourceRegistry(
        (
            make_source(
                source_account="accenture",
                company_name="Accenture",
                poll_interval_seconds=slow_interval,
            ),
            make_source(
                source_account="cursor",
                company_name="Cursor",
                poll_interval_seconds=300,
            ),
        )
    )


def _advancing(
    clock: FakeClock,
):
    def sleeper(
        seconds: float,
    ) -> None:
        clock.advance(
            seconds
        )

    return sleeper


def test_a_slow_source_does_not_hold_up_the_others() -> None:
    clock = FakeClock()

    release = threading.Event()

    calls: dict[str, int] = {}

    runtime = SchedulerRuntime(
        registry=_sources_fast_and_slow(),
        poller=_blocking_poller(
            release,
            calls,
        ),
        clock=clock,
        sleeper=_advancing(
            clock
        ),
        cycle_budget_seconds=0.05,
    )

    try:
        # Well over 300 s of scheduler time with Accenture stuck.
        runtime.run_forever(
            max_cycles=40,
        )

        assert calls["cursor"] >= 2

        # And the stuck one is not started a second time meanwhile.
        assert calls["accenture"] == 1

    finally:
        release.set()


def test_a_single_run_still_waits_for_everything() -> None:
    """--once exits when it returns; a poll left running would be cut
    off mid-transaction."""

    release = threading.Event()

    started = threading.Event()

    calls: dict[str, int] = {}

    runtime = SchedulerRuntime(
        registry=_sources_fast_and_slow(),
        poller=_blocking_poller(
            release,
            calls,
            started=started,
        ),
        clock=FakeClock(),
        sleeper=lambda _seconds: None,
    )

    finished = threading.Event()

    def run() -> None:
        result = runtime.run_due_sources()

        assert result.succeeded_count == 2

        finished.set()

    threading.Thread(
        target=run,
        daemon=True,
    ).start()

    try:
        assert started.wait(
            timeout=5,
        )

        assert not finished.wait(
            timeout=0.3,
        )

    finally:
        release.set()

    assert finished.wait(
        timeout=5,
    )


def test_what_a_late_finisher_found_is_grouped_from_when_it_started() -> None:
    """Discoveries are grouped into a pull from a start time. A poll
    that began cycles ago and finished in this one must still have its
    jobs grouped, or they never reach an alert."""

    clock = FakeClock()

    release = threading.Event()

    calls: dict[str, int] = {}

    slow_started: list[datetime] = []

    recorded: list[datetime] = []

    finished = threading.Event()

    def poller(
        source: SourceDefinition,
    ):
        result = _blocking_poller(
            release,
            calls,
            started_at=slow_started,
        )(
            source
        )

        if source.source_account == "accenture":
            finished.set()

        return result

    sleeps = 0

    def sleeper(
        seconds: float,
    ) -> None:
        nonlocal sleeps

        sleeps += 1

        if sleeps == 3:
            release.set()

            assert finished.wait(
                timeout=5,
            )

            # Let the worker leave its finally block.
            time.sleep(
                0.2
            )

        clock.advance(
            seconds
        )

    runtime = SchedulerRuntime(
        registry=_sources_fast_and_slow(),
        poller=poller,
        clock=clock,
        sleeper=sleeper,
        cycle_budget_seconds=0.05,
        cycle_recorder=lambda *, started_at: recorded.append(
            started_at
        ),
    )

    try:
        runtime.run_forever(
            max_cycles=6,
        )

    finally:
        release.set()

    [started] = slow_started

    # The first cycle records from its own start; the one after the
    # release must reach back to when Accenture began.
    assert any(
        moment <= started
        for moment in recorded[1:]
    )


def test_the_loop_keeps_going_while_everything_is_running() -> None:
    """With every source running there is no next due time -- which
    must not read as "no sources", the signal to stop."""

    release = threading.Event()

    calls: dict[str, int] = {}

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                make_source(
                    source_account="accenture",
                ),
            )
        ),
        poller=_blocking_poller(
            release,
            calls,
        ),
        clock=FakeClock(),
        sleeper=lambda _seconds: None,
    )

    try:
        result = runtime.run_due_sources(
            budget_seconds=0.05,
        )

        assert result.still_running == 1

        assert (
            runtime.seconds_until_next_poll()
            == runtime_module.IN_FLIGHT_RECHECK_SECONDS
        )

    finally:
        release.set()


def test_a_source_removed_while_running_is_not_brought_back() -> None:
    """Its due time, put back after removal, would belong to no source.
    Nothing would ever poll it forward again, so once it passed it
    would stay in the past -- and the loop would wake for it, without
    sleeping, forever."""

    clock = FakeClock()

    release = threading.Event()

    finished = threading.Event()

    calls: dict[str, int] = {}

    def poller(
        source: SourceDefinition,
    ):
        result = _blocking_poller(
            release,
            calls,
        )(
            source
        )

        if source.source_account == "accenture":
            finished.set()

        return result

    registries = [
        _sources_fast_and_slow(),
        SourceRegistry(
            (
                make_source(
                    source_account="cursor",
                    company_name="Cursor",
                    poll_interval_seconds=300,
                ),
            )
        ),
    ]

    runtime = SchedulerRuntime(
        registry=registries[0],
        poller=poller,
        clock=clock,
        sleeper=lambda _seconds: None,
        reload_registry=lambda: registries[1],
    )

    try:
        runtime.run_due_sources(
            budget_seconds=0.05,
        )

        # Accenture is removed from the catalog while still running.
        runtime._refresh_sources()

    finally:
        release.set()

    assert finished.wait(
        timeout=5,
    )

    time.sleep(
        0.2
    )

    # Long past when Accenture would have been due again.
    clock.advance(
        1000
    )

    runtime.run_due_sources(
        budget_seconds=5,
    )

    # Only Cursor is left, polled just now and due in 300 s -- not a
    # ghost overdue for ever.
    assert (
        runtime.seconds_until_next_poll()
        == 300
    )


def test_a_worker_that_breaks_unexpectedly_still_reschedules() -> None:
    """A source stuck as "running" would never be polled again, which
    is worse than any single failed poll."""

    class BrokenLogger:
        def info(
            self,
            message: str,
            *args,
        ) -> None:
            if message.startswith(
                "source_poll_succeeded"
            ):
                raise RuntimeError(
                    "log handler failed"
                )

        def warning(self, *args, **kwargs) -> None:
            pass

        def error(self, *args, **kwargs) -> None:
            pass

        def exception(self, *args, **kwargs) -> None:
            pass

    source = make_source(
        poll_interval_seconds=300,
    )

    clock = FakeClock()

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                source,
            )
        ),
        poller=lambda _source: make_result(),
        clock=clock,
        sleeper=lambda _seconds: None,
        logger=BrokenLogger(),
        concurrency=2,
    )

    runtime.run_due_sources(
        budget_seconds=5,
    )

    assert (
        runtime.seconds_until_next_poll()
        == 300
    )

    clock.advance(
        300
    )

    # Polled again on schedule, not stuck as running.
    assert (
        runtime.run_due_sources(
            budget_seconds=5,
        ).still_running
        == 0
    )


# --- one board at a time behind a shared edge ------------------------


def _eightfold(
    account: str,
) -> SourceDefinition:
    return SourceDefinition(
        source_type=SourceType.EIGHTFOLD_PCSX,
        source_account=account,
        company_name=account,
        enabled=True,
        poll_interval_seconds=3600,
        source_host=f"careers.{account}",
    )


def test_eightfold_boards_are_polled_one_at_a_time() -> None:
    """Eightfold answered 405 on every tenant at once after its boards
    were swept together. Other providers are not held back."""

    release = threading.Event()

    started: list[str] = []

    lock = threading.Lock()

    def poller(
        source: SourceDefinition,
    ):
        with lock:
            started.append(
                source.source_account
            )

        if source.source_account == "qualcomm.com":
            assert release.wait(
                timeout=10,
            )

        return make_result()

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                _eightfold("qualcomm.com"),
                _eightfold("microsoft.com"),
                make_source(
                    source_account="cursor",
                ),
            )
        ),
        poller=poller,
        clock=FakeClock(),
        sleeper=lambda _seconds: None,
    )

    try:
        first = runtime.run_due_sources(
            budget_seconds=0.2,
        )

        # Qualcomm and Cursor went; Microsoft waits its turn.
        assert sorted(started) == [
            "cursor",
            "qualcomm.com",
        ]

        assert first.still_running == 1

        # Still waiting while Qualcomm runs.
        runtime.run_due_sources(
            budget_seconds=0.2,
        )

        assert "microsoft.com" not in started

    finally:
        release.set()

    time.sleep(
        0.2
    )

    runtime.run_due_sources(
        budget_seconds=1,
    )

    assert "microsoft.com" in started


def test_a_board_held_behind_its_edge_does_not_spin_the_loop() -> None:
    """It is due but cannot go. Counting it as due would wake the loop
    at once, over and over, until the edge was free."""

    release = threading.Event()

    def poller(
        source: SourceDefinition,
    ):
        if source.source_account == "qualcomm.com":
            assert release.wait(
                timeout=10,
            )

        return make_result()

    runtime = SchedulerRuntime(
        registry=SourceRegistry(
            (
                _eightfold("qualcomm.com"),
                _eightfold("microsoft.com"),
            )
        ),
        poller=poller,
        clock=FakeClock(),
        sleeper=lambda _seconds: None,
    )

    try:
        runtime.run_due_sources(
            budget_seconds=0.1,
        )

        assert (
            runtime.seconds_until_next_poll()
            == runtime_module.IN_FLIGHT_RECHECK_SECONDS
        )

    finally:
        release.set()
