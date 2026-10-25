"""A recent snapshot answers at once and refreshes behind the reader."""

import threading
from contextlib import nullcontext

from backend.app.api.snapshot import Snapshot


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_first_read_computes_and_later_reads_reuse_it() -> None:
    calls = []
    snapshot = Snapshot(lambda session: calls.append(session) or len(calls), max_age=60, sessions=lambda: nullcontext("bg"), clock=Clock())

    assert snapshot.get("request") == 1
    assert snapshot.get("request") == 1
    assert calls == ["request"]


def test_a_stale_read_answers_at_once_and_refreshes_in_the_background() -> None:
    clock = Clock()
    release = threading.Event()
    refreshed = threading.Event()
    values = iter([1, 2])

    def compute(session):
        if session == "background":
            release.wait(5)
            refreshed.set()
        return next(values)

    snapshot = Snapshot(compute, max_age=60, sessions=lambda: nullcontext("background"), clock=clock)
    assert snapshot.get("request") == 1

    clock.now = 61
    # Stale: the old value comes back without waiting for the refresh.
    assert snapshot.get("request") == 1
    # Only one refresh runs however many readers arrive.
    assert snapshot.get("request") == 1
    release.set()
    assert refreshed.wait(5)
    for _ in range(100):
        if snapshot.get("request") == 2:
            break
        threading.Event().wait(0.01)
    assert snapshot.get("request") == 2


def test_a_failed_refresh_keeps_the_last_value() -> None:
    clock = Clock()
    done = threading.Event()

    def compute(session):
        if session == "background":
            done.set()
            raise RuntimeError("database away")
        return "kept"

    snapshot = Snapshot(compute, max_age=60, sessions=lambda: nullcontext("background"), clock=clock)
    assert snapshot.get("request") == "kept"
    clock.now = 61
    assert snapshot.get("request") == "kept"
    assert done.wait(5)
    assert snapshot.get("request") == "kept"
