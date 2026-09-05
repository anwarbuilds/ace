"""Automatic polling runtime for ACE scheduled job sources.

This module owns scheduling only.

It deliberately does not know how Greenhouse works, how jobs are
persisted, how eligibility is evaluated, or how email is delivered.

Its responsibilities are:

    - determine which configured sources are due
    - execute due sources
    - isolate one source failure from other sources
    - reschedule every attempted source
    - sleep efficiently between due times
    - emit useful structured log messages

Provider fetching and transactional source processing remain delegated
to the existing scheduling service.
"""

import logging
import time
from dataclasses import dataclass
from typing import (
    Callable,
    Protocol,
)

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
    ) -> None:
        self._sources = (
            registry.enabled_sources
        )

        self._poller = poller
        self._clock = clock
        self._sleeper = sleeper
        self._logger = logger

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

        for source in self._sources:
            next_due_at = (
                self._next_due_at[
                    source.identity
                ]
            )

            if next_due_at > cycle_time:
                continue

            started_at = (
                self._clock()
            )

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
                result = (
                    self._poller(
                        source
                    )
                )

            except Exception as exc:
                finished_at = (
                    self._clock()
                )

                duration_seconds = max(
                    0.0,
                    finished_at
                    - started_at,
                )

                self._next_due_at[
                    source.identity
                ] = (
                    finished_at
                    + source.poll_interval_seconds
                )

                failure = (
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

                failures.append(
                    failure
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

                continue

            finished_at = (
                self._clock()
            )

            duration_seconds = max(
                0.0,
                finished_at
                - started_at,
            )

            self._next_due_at[
                source.identity
            ] = (
                finished_at
                + source.poll_interval_seconds
            )

            success = SourcePollSuccess(
                source=source,
                result=result,
                duration_seconds=(
                    duration_seconds
                ),
            )

            successes.append(
                success
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
                    "queued_notifications=%d "
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
                result.queued_notification_count,
                duration_seconds,
                source.poll_interval_seconds,
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

            self._sleeper(
                sleep_seconds
            )