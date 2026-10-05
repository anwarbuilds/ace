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

Nor does a cycle wait for the slowest source it started. It waits up to
a budget; a source still running after that carries on in the
background, reschedules itself when it finishes, and is not started
again until it has. Waiting for every source meant every source waited
for the slowest: Accenture's poll takes six minutes every fifteen, and
for those six minutes nothing else was polled -- the five-minute
sources, which exist to catch a posting early, included.

Provider fetching and transactional source processing remain delegated
to the existing scheduling service.
"""

import logging
from collections.abc import (
    Callable,
    Mapping,
)
import threading
import time
from datetime import (
    datetime,
    timezone,
)
from concurrent.futures import (
    ThreadPoolExecutor,
    wait,
)
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


# Statuses a provider uses to say "not you", as opposed to "not now".
# 405 is here because that is what Eightfold's edge answered, on every
# tenant at once, minutes after ACE swept all of its boards three times
# in twenty minutes -- the same GET that had returned 200 moments
# before.
REFUSAL_STATUSES = frozenset(
    {
        401,
        403,
        405,
        429,
    }
)


# A refused source is asked again at twice its interval, then four
# times, and so on up to this. Asking on the usual schedule would keep
# knocking on a door that has just been shut, and can keep it shut.
REFUSAL_BACKOFF_CAP_SECONDS = 6 * 60 * 60


# Providers whose tenants all sit behind one edge, keyed by source type.
# Their boards are polled one at a time. Eightfold answers ten postings
# a page whatever is asked for, so one large board is two or three
# hundred requests; several at once, from one address, is a burst. On
# 2026-10-04 Eightfold answered 405 on every tenant at once after three
# such sweeps in twenty minutes.
SHARED_EDGE = {
    "eightfold": "eightfold",
    "eightfold_pcsx": "eightfold",
}


def _edge_of(
    source_type: object,
) -> str | None:
    """The shared edge a source type's boards sit behind, if any."""

    return SHARED_EDGE.get(
        getattr(
            source_type,
            "value",
            source_type,
        )
    )


# How long a cycle waits for the sources it started. Most answer in
# well under a second; one still running after this carries on in the
# background, and the next cycle starts without waiting for it.
CYCLE_BUDGET_SECONDS = 20.0


# While a source is still running, the loop looks in at least this
# often, so what it found is grouped into a pull -- and alerted --
# promptly rather than whenever another source falls due.
IN_FLIGHT_RECHECK_SECONDS = 15.0


# How often the injected maintenance runs -- looking for boards that
# have stopped answering. Their companies are diagnosed again, a few
# requests each, so this is not a sweep of anything.
MAINTENANCE_INTERVAL_SECONDS = 6 * 60 * 60


def _refusal_status(
    exc: BaseException,
) -> int | None:
    """The refusal status behind a failed poll, if a refusal caused it.

    Read off any exception carrying an HTTP response, so an adapter
    that wraps the HTTP error in its own is still recognised.
    """

    current: BaseException | None = exc

    for _ in range(5):
        if current is None:
            return None

        status = getattr(
            getattr(
                current,
                "response",
                None,
            ),
            "status_code",
            None,
        )

        if status in REFUSAL_STATUSES:
            return status

        current = (
            current.__cause__
            or current.__context__
        )

    return None


class RegistryReloader(Protocol):
    """Returns the current source registry, read fresh."""

    def __call__(
        self,
    ) -> SourceRegistry:
        """Return the registry as it stands now."""


class LastPolledReader(Protocol):
    """Returns when each source last polled successfully.

    Keyed by source type value and source account, the way
    source_states stores them. Injected so this module keeps no
    database import.
    """

    def __call__(
        self,
    ) -> Mapping[
        tuple[str, str],
        datetime,
    ]:
        """Return the last successful poll of every source known."""


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
        checks_since: Callable[
            [datetime],
            tuple[int, int],
        ],
    ) -> None:
        """Record the discoveries made during one cycle.

        ``checks_since(moment)`` answers how many distinct boards were
        read since then, and how many postings they held.
        """


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

    # Sources started by this cycle or an earlier one and not yet
    # finished; they carry on in the background.
    still_running: int = 0

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
        alert_sender: (
            Callable[[], None] | None
        ) = None,
        last_polled: (
            LastPolledReader | None
        ) = None,
        wall_clock: Callable[
            [],
            datetime,
        ] = (
            lambda: datetime.now(
                timezone.utc
            )
        ),
        maintenance: (
            Callable[[], None] | None
        ) = None,
        maintenance_interval_seconds: float = (
            MAINTENANCE_INTERVAL_SECONDS
        ),
        cycle_budget_seconds: float = (
            CYCLE_BUDGET_SECONDS
        ),
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

        # Injected rather than reached for, so this module keeps no
        # database import and an alert failure stays the caller's
        # problem rather than the scheduler's.
        self._alert_sender = alert_sender

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

        # Consecutive refusals per source; cleared by a success.
        self._refusals: dict[
            tuple[
                object,
                str,
            ],
            int,
        ] = {}

        self._maintenance = maintenance

        self._maintenance_interval = (
            maintenance_interval_seconds
        )

        self._maintenance_due_at = 0.0

        self._maintenance_thread: (
            threading.Thread | None
        ) = None

        self._cycle_budget = (
            cycle_budget_seconds
        )

        # Sources started and not yet finished. Guarded by _due_lock.
        self._in_flight: set[
            tuple[
                object,
                str,
            ]
        ] = set()

        # Earliest start of any poll finished since discoveries were
        # last grouped. Guarded by _due_lock.
        self._unrecorded_since: (
            datetime | None
        ) = None

        self._pool: (
            ThreadPoolExecutor | None
        ) = None

        self._wall_clock = wall_clock

        # Each board's latest successful read: when, and how many
        # postings it held. What a pull reports as checked, alongside
        # what was new. Guarded by _due_lock.
        self._last_checked: dict[
            tuple[
                object,
                str,
            ],
            tuple[datetime, int],
        ] = {}

        self._resume_schedule(
            last_polled,
            wall_clock,
        )

    def _resume_schedule(
        self,
        last_polled: (
            LastPolledReader | None
        ),
        wall_clock: Callable[
            [],
            datetime,
        ],
    ) -> None:
        """Start each source where its last successful poll left it.

        Every source used to be due the moment the scheduler started,
        so each deploy re-polled all of them at once. Three restarts in
        twenty minutes swept every Eightfold board in full three times,
        and Eightfold then refused ACE on every tenant. A source polled
        three minutes before a restart is not stale: it waits out the
        rest of its interval. One the machine slept through is overdue
        and goes in the first cycle, as before.
        """

        if last_polled is None:
            return

        try:
            polled = last_polled()

            now = wall_clock()

        except Exception:
            # Not knowing means overdue: the old behaviour, which costs
            # a burst but never a gap.
            self._logger.exception(
                "scheduler_last_polled_unavailable"
            )

            return

        clock_now = self._clock()

        waiting = 0

        with self._due_lock:
            for source in self._sources:
                polled_at = polled.get(
                    (
                        source.source_type.value,
                        source.source_account,
                    )
                )

                if polled_at is None:
                    continue

                if polled_at.tzinfo is None:
                    polled_at = polled_at.replace(
                        tzinfo=timezone.utc,
                    )

                interval = (
                    source.poll_interval_seconds
                )

                # A poll stamped in the future -- a clock that moved --
                # waits one interval, never longer.
                remaining = min(
                    interval,
                    interval
                    - (
                        now - polled_at
                    ).total_seconds(),
                )

                if remaining <= 0:
                    continue

                self._next_due_at[
                    source.identity
                ] = (
                    clock_now
                    + remaining
                )

                waiting += 1

        self._logger.info(
            (
                "scheduler_schedule_resumed "
                "due_now=%d waiting=%d"
            ),
            len(self._sources) - waiting,
            waiting,
        )

    def _start_due_maintenance(
        self,
    ) -> None:
        """Start the maintenance in the background, if it is due.

        In the background because it reads other people's websites,
        and one slow site must not hold back the five-minute sources
        behind it. Never two at once.
        """

        if self._maintenance is None:
            return

        now = self._clock()

        if now < self._maintenance_due_at:
            return

        if (
            self._maintenance_thread is not None
            and self._maintenance_thread.is_alive()
        ):
            return

        self._maintenance_due_at = (
            now
            + self._maintenance_interval
        )

        maintenance = self._maintenance

        def run() -> None:
            try:
                maintenance()

            except Exception:
                self._logger.exception(
                    "scheduler_maintenance_failed"
                )

        self._maintenance_thread = threading.Thread(
            target=run,
            name="ace-maintenance",
            daemon=True,
        )

        self._maintenance_thread.start()

    def _send_due_alerts(
        self,
    ) -> None:
        """Email any pull that has finished and not been alerted.

        Called every cycle, which sounds expensive and is not: the
        query asks for pulls with no `notified_at`, which is almost
        always empty, and a pull is only ever consumed once.

        Wrapped the same way as the source reload: a mail provider
        being down, or the database hiccuping, must not stop ACE
        polling. The jobs are in the queue either way; an alert is a
        nudge, and losing a nudge is survivable in a way that losing
        the scheduler is not.
        """

        if self._alert_sender is None:
            return

        try:
            self._alert_sender()
        except Exception:
            self._logger.exception(
                "scheduler_alerts_failed",
            )

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

        current = {
            source.identity: source
            for source in self._sources
        }

        added = [
            source
            for source in sources
            if source.identity not in current
        ]

        removed = set(
            current
        ) - {
            source.identity
            for source in sources
        }

        # An edit to a source already known changes no identity: a
        # corrected company name, a changed poll interval, a fixed
        # host. Comparing only identities meant the scheduler kept
        # running on whichever definition it happened to read first,
        # for as long as the process lived.
        #
        # That is how 793 Visa postings kept being written under the
        # employer name "myworkdayjobs" after the name had been
        # corrected in the catalog: every poll re-applied the stale
        # definition, so fixing the rows by hand did not hold either.
        changed = [
            source
            for source in sources
            if source.identity in current
            and source != current[source.identity]
        ]

        if (
            not added
            and not removed
            and not changed
        ):
            return

        self._sources = sources

        with self._due_lock:
            for source in added:
                self._next_due_at[
                    source.identity
                ] = 0.0

            # A new interval counts from the last poll, not the next
            # one already booked. Amazon, moved from daily to fifteen
            # minutes, would otherwise have waited out the rest of its
            # day first. A longer interval leaves the booking alone.
            for source in changed:
                previous = current[
                    source.identity
                ]

                due_at = self._next_due_at.get(
                    source.identity
                )

                if (
                    due_at is None
                    or source.poll_interval_seconds
                    >= previous.poll_interval_seconds
                ):
                    continue

                self._next_due_at[
                    source.identity
                ] = min(
                    due_at,
                    due_at
                    - previous.poll_interval_seconds
                    + source.poll_interval_seconds,
                )

            for identity in removed:
                self._next_due_at.pop(
                    identity,
                    None,
                )

        self._logger.info(
            (
                "scheduler_sources_reloaded "
                "added=%d removed=%d changed=%d "
                "total=%d"
            ),
            len(added),
            len(removed),
            len(changed),
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
        budget_seconds: float | None = None,
    ) -> SchedulerCycleResult:
        """Poll every source currently due.

        One source failure is captured and logged without preventing
        later due sources from executing.

        With no budget, waits for every source it started -- what a
        single run (--once) needs, since the process exits after it.

        With a budget, waits that long and no longer. A source still
        running carries on in the background, finishes and reschedules
        itself, and is not started again until it has. This is what
        the continuous loop uses, because waiting for the slowest
        source meant every other source waited too: Accenture's poll
        takes six minutes every fifteen, and for those six minutes the
        five-minute sources -- the ones that exist to catch a posting
        early -- were not polled at all.
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
            busy_edges = self._busy_edges()

            due_sources = []

            for source in self._sources:
                if (
                    source.identity
                    in self._in_flight
                    or self._next_due_at[
                        source.identity
                    ]
                    > cycle_time
                ):
                    continue

                edge = _edge_of(
                    source.source_type
                )

                # One board per shared edge at a time. The rest stay
                # due and go when it finishes.
                if edge is not None:
                    if edge in busy_edges:
                        continue

                    busy_edges.add(
                        edge
                    )

                due_sources.append(
                    source
                )

            for source in due_sources:
                self._in_flight.add(
                    source.identity
                )

            still_running_before = len(
                self._in_flight
            ) - len(
                due_sources
            )

        if not due_sources:
            # A poll that finished in the background since the last
            # cycle still has what it found grouped into a pull.
            self._record_cycle(
                None
            )

            return SchedulerCycleResult(
                succeeded=(),
                failed=(),
                still_running=(
                    still_running_before
                ),
            )

        cycle_started_at = datetime.now(
            timezone.utc
        )

        results_lock = threading.Lock()

        def run_one(
            source: SourceDefinition,
        ) -> None:
            """Poll one source, isolated from every other source.

            However it ends, it reschedules itself and leaves the
            in-flight set: a source stuck as "running" would never be
            polled again, which is worse than any single failed poll.
            """

            started_at = self._clock()

            started_wall = datetime.now(
                timezone.utc
            )

            delay = (
                source.poll_interval_seconds
            )

            try:
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

                    refused_with = _refusal_status(
                        exc
                    )

                    if refused_with is not None:
                        with self._due_lock:
                            refusals = (
                                self._refusals.get(
                                    source.identity,
                                    0,
                                )
                                + 1
                            )

                            self._refusals[
                                source.identity
                            ] = refusals

                        # Never sooner than the source's own interval,
                        # even where that is longer than the cap.
                        delay = max(
                            delay,
                            min(
                                delay
                                * 2**refusals,
                                REFUSAL_BACKOFF_CAP_SECONDS,
                            ),
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

                    if refused_with is not None:
                        # Expected, and its cause is in the status: a
                        # traceback per refusal would bury the log.
                        self._logger.warning(
                            (
                                "source_poll_refused "
                                "source_type=%s "
                                "source_account=%s "
                                "company=%r "
                                "status=%d "
                                "refusals=%d "
                                "duration_seconds=%.3f "
                                "next_poll_seconds=%d"
                            ),
                            source.source_type.value,
                            source.source_account,
                            source.company_name,
                            refused_with,
                            refusals,
                            duration_seconds,
                            delay,
                        )

                        return

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
                        delay,
                    )

                    return

                finished_at = self._clock()

                duration_seconds = max(
                    0.0,
                    finished_at - started_at,
                )

                with self._due_lock:
                    self._refusals.pop(
                        source.identity,
                        None,
                    )

                    self._last_checked[
                        source.identity
                    ] = (
                        self._wall_clock(),
                        int(
                            getattr(
                                result,
                                "checked_count",
                                getattr(
                                    result,
                                    "fetched_count",
                                    0,
                                ),
                            )
                            or 0
                        ),
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

            finally:
                with self._due_lock:
                    # Absent only if the source was removed while it
                    # ran. Putting it back would leave a due time no
                    # source owns -- always in the past, so the loop
                    # would wake for it forever.
                    if (
                        source.identity
                        in self._next_due_at
                    ):
                        self._next_due_at[
                            source.identity
                        ] = (
                            self._clock()
                            + delay
                        )

                    self._in_flight.discard(
                        source.identity
                    )

                    # What it found is grouped into a pull from the
                    # time it started, which may be several cycles ago.
                    if (
                        self._unrecorded_since is None
                        or started_wall
                        < self._unrecorded_since
                    ):
                        self._unrecorded_since = (
                            started_wall
                        )

        if (
            self._concurrency == 1
            and budget_seconds is None
        ):
            for source in due_sources:
                run_one(
                    source
                )

            still_running = 0

        else:
            futures = [
                self._worker_pool().submit(
                    run_one,
                    source,
                )
                for source in due_sources
            ]

            done, not_done = wait(
                futures,
                timeout=budget_seconds,
            )

            for future in done:
                crash = future.exception()

                if crash is not None:
                    self._logger.error(
                        "scheduler_worker_crashed",
                        exc_info=crash,
                    )

            with self._due_lock:
                still_running = len(
                    self._in_flight
                )

        self._record_cycle(
            cycle_started_at
        )

        with results_lock:
            return SchedulerCycleResult(
                succeeded=tuple(
                    successes
                ),
                failed=tuple(
                    failures
                ),
                still_running=still_running,
            )

    def _busy_edges(
        self,
    ) -> set[str]:
        """Shared edges with a board being polled. Caller holds the lock."""

        return {
            edge
            for edge in (
                _edge_of(
                    identity[0]
                )
                for identity in self._in_flight
            )
            if edge is not None
        }

    def _worker_pool(
        self,
    ) -> ThreadPoolExecutor:
        """The pool every poll runs on, kept for the life of the loop.

        One pool rather than one per cycle, because a cycle no longer
        waits for its sources to finish: a poll outlives the cycle that
        started it.
        """

        if self._pool is None:
            self._pool = ThreadPoolExecutor(
                max_workers=self._concurrency,
                thread_name_prefix="ace-poll",
            )

        return self._pool

    def _record_cycle(
        self,
        cycle_started_at: datetime | None,
    ) -> None:
        """Group what was discovered into a pull.

        From the earliest start of any poll that has finished since the
        last time, or this cycle's start if that is earlier -- so a
        poll that began three cycles ago and finished in this one still
        has what it found grouped and alerted.
        """

        if self._cycle_recorder is None:
            return

        with self._due_lock:
            since = self._unrecorded_since

            self._unrecorded_since = None

        if cycle_started_at is not None and (
            since is None
            or cycle_started_at < since
        ):
            since = cycle_started_at

        if since is None:
            return

        try:
            self._cycle_recorder(
                started_at=since,
                checks_since=self.checks_since,
            )

        except Exception:
            # Recording is presentation only. Losing it must never
            # fail a cycle that successfully collected jobs.
            self._logger.exception(
                "cycle_recording_failed"
            )

    def checks_since(
        self,
        moment: datetime,
    ) -> tuple[int, int]:
        """Distinct boards read since ``moment``, and postings they held.

        Each board counts once, at its latest read: a five-minute board
        read three times in a quarter hour is one board, not three.
        """

        if moment.tzinfo is None:
            moment = moment.replace(
                tzinfo=timezone.utc,
            )

        with self._due_lock:
            recent = [
                count
                for checked_at, count in (
                    self._last_checked.values()
                )
                if checked_at >= moment
            ]

        return (
            len(recent),
            sum(recent),
        )

    def seconds_until_next_poll(
        self,
        *,
        now: float | None = None,
    ) -> float | None:
        """Return seconds until the loop next has something to do.

        That is the earliest due time among sources not already
        running -- or, while any source is running, no later than
        IN_FLIGHT_RECHECK_SECONDS, so what it finds is grouped and
        alerted promptly rather than whenever another source happens
        to fall due. None only when there are no sources at all.
        """

        if not self._next_due_at:
            return None

        current_time = (
            self._clock()
            if now is None
            else now
        )

        with self._due_lock:
            busy_edges = self._busy_edges()

            # A board held back behind its edge is due but cannot go
            # yet. Counting it would make the loop wake for it at once,
            # and again, and again, until the edge was free.
            waiting = [
                due_at
                for identity, due_at in (
                    self._next_due_at.items()
                )
                if identity
                not in self._in_flight
                and _edge_of(
                    identity[0]
                )
                not in busy_edges
            ]

            running = bool(
                self._in_flight
            )

        if not waiting:
            return IN_FLIGHT_RECHECK_SECONDS

        seconds = max(
            0.0,
            min(
                waiting
            )
            - current_time,
        )

        if running:
            seconds = min(
                seconds,
                IN_FLIGHT_RECHECK_SECONDS,
            )

        return seconds

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
                self.run_due_sources(
                    budget_seconds=(
                        self._cycle_budget
                    ),
                )
            )

            cycle_count += 1

            self._logger.info(
                (
                    "scheduler_cycle_completed "
                    "cycle=%d "
                    "attempted=%d "
                    "succeeded=%d "
                    "failed=%d "
                    "still_running=%d"
                ),
                cycle_count,
                cycle_result.attempted_count,
                cycle_result.succeeded_count,
                cycle_result.failed_count,
                cycle_result.still_running,
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

            # Before the refresh, so a board it registered on an
            # earlier run is picked up here rather than a cycle later.
            self._start_due_maintenance()

            self._refresh_sources()

            self._send_due_alerts()

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