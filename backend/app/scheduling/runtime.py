"""Automatic polling runtime for ACE scheduled job sources.

This module owns scheduling only.

It deliberately does not know how Greenhouse works, how jobs are
persisted, how eligibility is evaluated, or how email is delivered.

Its responsibilities are:

    - determine which configured sources are due
    - execute due sources, several at a time
    - isolate one source failure from other sources
    - reschedule every attempted source
    - sleep efficiently between due times
    - emit useful structured log messages

Sources are polled concurrently because they are independent: different
hosts, different database rows, one transaction each. Sequential polling
meant a single slow employer blocked every other source behind it -- one
measured poll took 949 seconds while the median was 0.23.

Concurrency is bounded well below the database pool size, and each
worker holds a connection only for its own short transaction. The limit
is deliberately modest: these are other people's careers sites, and the
goal is to stop one of them blocking the rest, not to hammer all of
them at once.

Provider fetching and transactional source processing remain delegated
to the existing scheduling service.
"""

import logging
import threading
import time
from datetime import (
    datetime,
    timezone,
)
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol

from backend.app.scheduling.registry import (
    SourceRegistry,
)
from backend.app.scheduling.service import (
    SourcePollResult,
)
from backend.app.scheduling.types import (
    SourceDefinition,
)


LOGGER = logging.getLogger(
    "ace.scheduler"
)


# Bounded well below the SQLAlchemy pool so a full cycle cannot exhaust
# database connections.
DEFAULT_CONCURRENCY = 6


# A suspend shorter than this is not worth a line in the log: a
# laptop lid closed for half a minute is not the hour-long gap that
# makes a person ask whether the scheduler died.
SUSPEND_REPORTING_SECONDS = 120


class RegistryReloader(Protocol):
    """Returns the current source registry, read fresh."""

    def __call__(
        self,
    ) -> SourceRegistry:
        """Return the registry as it stands now."""


class MonotonicClock(Protocol):
    """Monotonic scheduler clock."""

    def __call__(self) -> float:
        """Return monotonic seconds."""


class Sleeper(Protocol):
    """Scheduler sleep operation."""

    def __call__(
        self,
        seconds: float,
    ) -> None:
        """Sleep for the requested duration."""


class CycleRecorder(Protocol):
    """Called once per cycle to record what it discovered.

    Injected so the runtime stays free of database knowledge: it can be
    tested without a database, and what a cycle *means* for presentation
    stays out of the scheduling loop.
    """

    def __call__(
        self,
        *,
        started_at: datetime,
    ) -> None:
        """Record the discoveries made during one cycle."""


class SourcePoller(Protocol):
    """Application operation that processes one configured source."""

    def __call__(
        self,
        source: SourceDefinition,
    ) -> SourcePollResult:
        """Process exactly one source poll."""


@dataclass(
    frozen=True,
    slots=True,
)
class SourcePollSuccess:
    """Successful scheduler execution for one source."""

    source: SourceDefinition

    result: SourcePollResult

    duration_seconds: float


@dataclass(
    frozen=True,
    slots=True,
)
class SourcePollFailure:
    """Failed scheduler execution for one source."""

    source: SourceDefinition

    error_type: str

    error_message: str

    duration_seconds: float


@dataclass(
    frozen=True,
    slots=True,
)
class SchedulerCycleResult:
    """Summary of one scheduler due-source scan."""

    succeeded: tuple[
        SourcePollSuccess,
        ...,
    ]

    failed: tuple[
        SourcePollFailure,
        ...,
    ]

    @property
    def succeeded_count(
        self,
    ) -> int:
        """Return successful source count."""

        return len(
            self.succeeded
        )

    @property
    def failed_count(
        self,
    ) -> int:
        """Return failed source count."""

        return len(
            self.failed
        )

    @property
    def attempted_count(
        self,
    ) -> int:
        """Return total attempted source count."""

        return (
            self.succeeded_count
            + self.failed_count
        )


class SchedulerRuntime:
    """Sequential failure-isolated scheduler for configured ACE sources.

    Every enabled source owns an independent next-due timestamp.

    Poll intervals are measured from completion of the previous attempt.
    This prevents overlapping execution when a provider or database poll
    itself takes significant time.
    """

    def __init__(
        self,
        *,
        registry: SourceRegistry,
        poller: SourcePoller,
        clock: MonotonicClock = (
            time.monotonic
        ),
        sleeper: Sleeper = (
            time.sleep
        ),
        logger: logging.Logger = LOGGER,
        concurrency: int = (
            DEFAULT_CONCURRENCY
        ),
        cycle_recorder: (
            CycleRecorder | None
        ) = None,
        reload_registry: (
            RegistryReloader | None
        ) = None,
    ) -> None:
        self._sources = (
            registry.enabled_sources
        )

        # Re-read the source list between cycles, so a source
        # registered while the scheduler is running is polled without
        # anyone restarting it.
        #
        # The registry used to be a snapshot taken at startup. That was
        # invisible until a source was added from the interface and
        # nothing happened for hours: the row was there, the board was
        # reachable, and it looked like a bug.
        self._reload_registry = (
            reload_registry
        )

        self._poller = poller
        self._clock = clock
        self._sleeper = sleeper
        self._logger = logger

        self._concurrency = max(
            1,
            concurrency,
        )

        self._cycle_recorder = (
            cycle_recorder
        )

        # next-due times are read and written from worker threads.
        self._due_lock = threading.Lock()

        self._next_due_at: dict[
            tuple[
                object,
                str,
            ],
            float,
        ] = {
            source.identity: 0.0
            for source in self._sources
        }

    def _refresh_sources(
        self,
    ) -> None:
        """Pick up sources registered since the last cycle.

        A source that is already known keeps its next-due time, so a
        reload never resets the schedule and never causes a burst of
        re-polling. A source that has gone is dropped.
        """

        if self._reload_registry is None:
            return

        try:
            sources = (
                self._reload_registry()
                .enabled_sources
            )
        except Exception:
            # A database hiccup must not stop the scheduler; it keeps
            # the list it already has and tries again next cycle.
            self._logger.exception(
                "scheduler_registry_reload_failed"
            )

            return

        known = {
            source.identity
            for source in self._sources
        }

        added = [
            source
            for source in sources
            if source.identity not in known
        ]

        removed = known - {
            source.identity
            for source in sources
        }

        if not added and not removed:
            return

        self._sources = sources

        with self._due_lock:
            for source in added:
                self._next_due_at[
                    source.identity
                ] = 0.0

            for identity in removed:
                self._next_due_at.pop(
                    identity,
                    None,
                )

        self._logger.info(
            (
                "scheduler_sources_reloaded "
                "added=%d removed=%d total=%d"
            ),
            len(added),
            len(removed),
            len(sources),
        )

    @property
    def source_count(
        self,
    ) -> int:
        """Return enabled scheduler source count."""

        return len(
            self._sources
        )

    def run_due_sources(
        self,
        *,
        now: float | None = None,
    ) -> SchedulerCycleResult:
        """Poll every source currently due.

        One source failure is captured and logged without preventing
        later due sources from executing.
        """

        cycle_time = (
            self._clock()
            if now is None
            else now
        )

        successes: list[
            SourcePollSuccess
        ] = []

        failures: list[
            SourcePollFailure
        ] = []

        with self._due_lock:
            due_sources = [
                source
                for source in self._sources
                if self._next_due_at[
                    source.identity
                ]
                <= cycle_time
            ]

        if not due_sources:
            return SchedulerCycleResult(
                succeeded=(),
                failed=(),
            )

        cycle_started_at = datetime.now(
            timezone.utc
        )

        results_lock = threading.Lock()

        def run_one(
            source: SourceDefinition,
        ) -> None:
            """Poll one source, isolated from every other source."""

            started_at = self._clock()

            self._logger.info(
                (
                    "source_poll_started "
                    "source_type=%s "
                    "source_account=%s "
                    "company=%r"
                ),
                source.source_type.value,
                source.source_account,
                source.company_name,
            )

            try:
                result = self._poller(
                    source
                )

            except Exception as exc:
                finished_at = self._clock()

                duration_seconds = max(
                    0.0,
                    finished_at - started_at,
                )

                with self._due_lock:
                    self._next_due_at[
                        source.identity
                    ] = (
                        finished_at
                        + source.poll_interval_seconds
                    )

                with results_lock:
                    failures.append(
                        SourcePollFailure(
                            source=source,
                            error_type=(
                                type(exc).__name__
                            ),
                            error_message=str(
                                exc
                            ),
                            duration_seconds=(
                                duration_seconds
                            ),
                        )
                    )

                self._logger.exception(
                    (
                        "source_poll_failed "
                        "source_type=%s "
                        "source_account=%s "
                        "company=%r "
                        "duration_seconds=%.3f "
                        "next_poll_seconds=%d"
                    ),
                    source.source_type.value,
                    source.source_account,
                    source.company_name,
                    duration_seconds,
                    source.poll_interval_seconds,
                )

                return

            finished_at = self._clock()

            duration_seconds = max(
                0.0,
                finished_at - started_at,
            )

            with self._due_lock:
                self._next_due_at[
                    source.identity
                ] = (
                    finished_at
                    + source.poll_interval_seconds
                )

            with results_lock:
                successes.append(
                    SourcePollSuccess(
                        source=source,
                        result=result,
                        duration_seconds=(
                            duration_seconds
                        ),
                    )
                )

            self._logger.info(
                (
                    "source_poll_succeeded "
                    "source_type=%s "
                    "source_account=%s "
                    "company=%r "
                    "fetched=%d "
                    "evaluated=%d "
                    "alert_candidates=%d "
                    "stale_suppressed=%d "
                    "duration_seconds=%.3f "
                    "next_poll_seconds=%d"
                ),
                source.source_type.value,
                source.source_account,
                source.company_name,
                result.fetched_count,
                result.evaluated_count,
                result.alert_candidate_count,
                result.stale_suppressed_count,
                duration_seconds,
                source.poll_interval_seconds,
            )

        if self._concurrency == 1:
            for source in due_sources:
                run_one(
                    source
                )

        else:
            with ThreadPoolExecutor(
                max_workers=self._concurrency
            ) as pool:
                list(
                    pool.map(
                        run_one,
                        due_sources,
                    )
                )

        if (
            self._cycle_recorder
            is not None
        ):
            try:
                self._cycle_recorder(
                    started_at=(
                        cycle_started_at
                    )
                )

            except Exception:
                # Recording is presentation only. Losing it must never
                # fail a cycle that successfully collected jobs.
                self._logger.exception(
                    "cycle_recording_failed"
                )

        return SchedulerCycleResult(
            succeeded=tuple(
                successes
            ),
            failed=tuple(
                failures
            ),
        )

    def seconds_until_next_poll(
        self,
        *,
        now: float | None = None,
    ) -> float | None:
        """Return seconds until the earliest configured source is due."""

        if not self._next_due_at:
            return None

        current_time = (
            self._clock()
            if now is None
            else now
        )

        with self._due_lock:
            next_due_at = min(
                self._next_due_at.values()
            )

        return max(
            0.0,
            next_due_at
            - current_time,
        )

    def run_forever(
        self,
        *,
        max_cycles: int | None = None,
    ) -> None:
        """Continuously execute scheduled source polls.

        `max_cycles` exists primarily for deterministic smoke tests.
        Production execution normally leaves it as None.
        """

        if (
            max_cycles is not None
            and (
                isinstance(
                    max_cycles,
                    bool,
                )
                or not isinstance(
                    max_cycles,
                    int,
                )
                or max_cycles <= 0
            )
        ):
            raise ValueError(
                (
                    "max_cycles must be "
                    "a positive integer."
                )
            )

        if not self._sources:
            self._logger.warning(
                "scheduler_has_no_enabled_sources"
            )

            return

        cycle_count = 0

        self._logger.info(
            (
                "scheduler_started "
                "enabled_sources=%d"
            ),
            len(
                self._sources
            ),
        )

        while True:
            cycle_result = (
                self.run_due_sources()
            )

            cycle_count += 1

            self._logger.info(
                (
                    "scheduler_cycle_completed "
                    "cycle=%d "
                    "attempted=%d "
                    "succeeded=%d "
                    "failed=%d"
                ),
                cycle_count,
                cycle_result.attempted_count,
                cycle_result.succeeded_count,
                cycle_result.failed_count,
            )

            if (
                max_cycles is not None
                and cycle_count
                >= max_cycles
            ):
                self._logger.info(
                    (
                        "scheduler_stopped "
                        "reason=max_cycles "
                        "cycles=%d"
                    ),
                    cycle_count,
                )

                return

            self._refresh_sources()

            sleep_seconds = (
                self.seconds_until_next_poll()
            )

            if sleep_seconds is None:
                self._logger.info(
                    (
                        "scheduler_stopped "
                        "reason=no_enabled_sources"
                    )
                )

                return

            self._logger.info(
                (
                    "scheduler_sleeping "
                    "seconds=%.3f"
                ),
                sleep_seconds,
            )

            # Measured across the sleep, so a machine that suspends
            # mid-sleep is reported rather than leaving an unexplained
            # hole in the activity log.
            #
            # The user asked why there had been no checks for an hour.
            # There was nothing wrong: the laptop had slept, and
            # time.sleep does not advance while it is suspended, so the
            # scheduler simply resumed and finished the remainder. But
            # from the outside that is indistinguishable from a crash,
            # and the healthcheck cannot tell them apart either --
            # it was suspended too, so on waking it saw a fresh poll
            # and reported healthy.
            #
            # CLOCK_MONOTONIC stops while suspended and CLOCK_BOOTTIME
            # does not, so the difference between them is the time
            # spent asleep, and no privileged log is needed to find it.
            before_awake = time.clock_gettime(
                time.CLOCK_MONOTONIC
            )

            before_elapsed = time.clock_gettime(
                time.CLOCK_BOOTTIME
            )

            self._sleeper(
                sleep_seconds
            )

            awake = (
                time.clock_gettime(
                    time.CLOCK_MONOTONIC
                )
                - before_awake
            )

            elapsed = (
                time.clock_gettime(
                    time.CLOCK_BOOTTIME
                )
                - before_elapsed
            )

            suspended = elapsed - awake

            if suspended >= SUSPEND_REPORTING_SECONDS:
                self._logger.warning(
                    (
                        "scheduler_resumed_after_suspend "
                        "suspended_seconds=%.0f "
                        "slept_seconds=%.0f"
                    ),
                    suspended,
                    awake,
                )