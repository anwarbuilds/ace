"""Shared clock contract for ACE source runners.

Injecting the clock rather than reading it inline is what lets snapshot
timestamps be asserted exactly in tests, and what keeps a poll's
detection time stable across the work that follows it.
"""

from datetime import (
    datetime,
    timezone,
)
from typing import Protocol


class Clock(Protocol):
    """Callable returning the current instant."""

    def __call__(self) -> datetime:
        """Return an aware timestamp."""


def utc_now() -> datetime:
    """Return the current UTC instant."""

    return datetime.now(
        timezone.utc
    )
