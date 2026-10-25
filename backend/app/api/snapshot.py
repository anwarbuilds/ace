"""A slow aggregate over slowly changing data, kept as a recent snapshot.

Some figures are counted over the whole corpus and change only as new
postings arrive: Coverage's employers that will not sponsor read about
659,000 postings for one list that moves by minutes, not by requests.
Recomputing it for every page view made the page wait seconds for an
answer that had not changed.

The first read computes the value. Later reads return it at once; a read
after ``max_age`` seconds also starts one recomputation in the
background, so the next reader gets the newer value and nobody waits.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Generic, TypeVar

from sqlalchemy.orm import Session


LOGGER = logging.getLogger("ace.snapshot")

T = TypeVar("T")


class Snapshot(Generic[T]):
    def __init__(
        self,
        compute: Callable[[Session], T],
        *,
        max_age: float,
        sessions: Callable[[], AbstractContextManager[Session]],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._compute = compute
        self._max_age = max_age
        self._sessions = sessions
        self._clock = clock
        self._lock = threading.Lock()
        self._value: T | None = None
        self._taken_at: float | None = None
        self._refreshing = False

    def get(self, session: Session) -> T:
        """The latest value, computing it with ``session`` the first time."""

        with self._lock:
            taken_at, value = self._taken_at, self._value
            stale = taken_at is not None and self._clock() - taken_at >= self._max_age
            refresh = stale and not self._refreshing
            if refresh:
                self._refreshing = True

        if taken_at is None:
            value = self._compute(session)
            with self._lock:
                self._value, self._taken_at = value, self._clock()
            return value

        if refresh:
            threading.Thread(target=self._refresh, name="ace-snapshot", daemon=True).start()

        return value  # type: ignore[return-value]

    def _refresh(self) -> None:
        try:
            with self._sessions() as session:
                value = self._compute(session)
            with self._lock:
                self._value, self._taken_at = value, self._clock()
        except Exception:
            # The previous value stays; the next stale read tries again.
            LOGGER.exception("snapshot_refresh_failed")
        finally:
            with self._lock:
                self._refreshing = False
