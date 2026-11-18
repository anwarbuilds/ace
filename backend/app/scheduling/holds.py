"""A platform's pause, seen by every reader in the scheduler's process.

The scheduler pauses all of Workday after a few refusals close together
(``runtime.LANE_PAUSES``). Until 2026-11-18 only the scheduler's own turns
knew of it: the feed-link sweep and the lead check kept reading Workday
boards through the pause (GIRO's board was asked at 17:31Z and 18:01Z, inside
an 80-minute pause), and the employer-page check kept reading Workday posting
pages. Each now asks here first, and a read the pause holds back is put off,
not counted against the board.
"""

from __future__ import annotations

from collections.abc import Callable
import threading
import time


class PlatformHeld(RuntimeError):
    """A read was not made because its platform is paused after refusals."""


class PlatformHold:
    """When a platform's pause ends, on this process's own clock."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._until = 0.0

    def hold(
        self,
        seconds: float,
    ) -> None:
        """Hold the platform for this long from now (never shortening a hold)."""

        with self._lock:
            self._until = max(
                self._until,
                self._clock() + max(0.0, float(seconds)),
            )

    def release(self) -> None:
        with self._lock:
            self._until = 0.0

    def held(self) -> bool:
        with self._lock:
            return self._clock() < self._until

    def check(
        self,
        platform: str,
    ) -> None:
        """Raise ``PlatformHeld`` while the platform is paused."""

        if self.held():
            raise PlatformHeld(
                f"{platform} is paused after refusals; this read waits for the pause to end"
            )


# The process's holds, by platform. The scheduler sets them (runtime, given
# ``holds``); tests build their own runtime without them.
HOLDS: dict[str, PlatformHold] = {
    "workday": PlatformHold(),
}
