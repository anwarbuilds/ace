"""Bounded retry for transient provider failures.

Job boards fail intermittently. Amazon returned a 504 on page ten of a
twenty-page walk, which discarded nine pages of already-fetched work and
failed the whole poll.

Returning the partial result instead is not an option: a snapshot is
authoritative for lifecycle, so anything missing from it is treated as
closed. Handing back nine pages of a twenty-page listing would mark
hundreds of live jobs closed -- far worse than failing the poll.

So the transient failure is retried instead, briefly and a bounded
number of times, and a poll only fails when the provider is genuinely
unavailable.

Deliberately narrow
-------------------

Only status codes that mean "try again" are retried. A 404 is a real
answer about a board that no longer exists, and retrying it would hide a
catalog problem behind a slow poll.
"""

from __future__ import annotations

from collections.abc import Callable
import random
import time

import httpx


# Statuses that mean the request may succeed if repeated.
RETRYABLE_STATUS_CODES = frozenset(
    {
        429,
        500,
        502,
        503,
        504,
    }
)


DEFAULT_MAX_ATTEMPTS = 3

DEFAULT_BASE_DELAY_SECONDS = 1.0

# Never wait longer than this for one retry, however large Retry-After
# claims to be: a poll that sleeps for minutes blocks its worker.
MAX_DELAY_SECONDS = 20.0


def _retry_after_seconds(
    response: httpx.Response,
) -> float | None:
    """Read a Retry-After header, if the provider sent a usable one."""

    raw = response.headers.get(
        "retry-after"
    )

    if not raw:
        return None

    try:
        seconds = float(
            raw.strip()
        )

    except ValueError:
        # The HTTP-date form is valid but rare here; falling back to
        # normal backoff is simpler than parsing it.
        return None

    if seconds < 0:
        return None

    return min(
        seconds,
        MAX_DELAY_SECONDS,
    )


def request_with_retry(
    send: Callable[[], httpx.Response],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay_seconds: float = (
        DEFAULT_BASE_DELAY_SECONDS
    ),
    sleeper: Callable[[float], None] = (
        time.sleep
    ),
) -> httpx.Response:
    """Send a request, retrying only genuinely transient failures.

    Args:
        send: Performs one attempt and returns its response.

    Returns:
        The first non-retryable response, which may still be an error
        the caller is expected to raise on.

    Raises:
        httpx.TransportError: The final attempt failed to connect.
    """

    attempts = max(
        1,
        max_attempts,
    )

    last_error: Exception | None = None

    for attempt in range(
        1,
        attempts + 1,
    ):
        try:
            response = send()

        except httpx.TransportError as exc:
            last_error = exc

            if attempt == attempts:
                raise

            _wait(
                attempt=attempt,
                base_delay_seconds=(
                    base_delay_seconds
                ),
                retry_after=None,
                sleeper=sleeper,
            )

            continue

        if (
            response.status_code
            not in RETRYABLE_STATUS_CODES
        ):
            return response

        if attempt == attempts:
            return response

        _wait(
            attempt=attempt,
            base_delay_seconds=(
                base_delay_seconds
            ),
            retry_after=(
                _retry_after_seconds(
                    response
                )
            ),
            sleeper=sleeper,
        )

    # Unreachable: the loop either returns or raises.
    raise (
        last_error
        or RuntimeError(
            "retry loop ended without a result"
        )
    )


def _wait(
    *,
    attempt: int,
    base_delay_seconds: float,
    retry_after: float | None,
    sleeper: Callable[[float], None],
) -> None:
    """Sleep before the next attempt."""

    if retry_after is not None:
        sleeper(
            retry_after
        )

        return

    # Exponential with jitter, so several workers retrying at once do
    # not synchronise into a second burst against the same host.
    delay = min(
        base_delay_seconds
        * (2 ** (attempt - 1)),
        MAX_DELAY_SECONDS,
    )

    sleeper(
        delay * (
            0.5
            + random.random() / 2
        )
    )
