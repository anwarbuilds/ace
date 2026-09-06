"""Tests for bounded retry of transient provider failures.

The bug behind this: Amazon returned a 504 on page ten of a twenty-page
walk, discarding nine pages of fetched work and failing the whole poll.

Returning the partial result was never an option -- a snapshot is
authoritative for lifecycle, so anything absent from it is treated as
closed, and nine pages of twenty would mark hundreds of live jobs
closed. Retrying briefly is the correct answer.
"""

import httpx
import pytest

from backend.app.adapters.retry import (
    MAX_DELAY_SECONDS,
    RETRYABLE_STATUS_CODES,
    request_with_retry,
)


def responder(
    statuses: list[int],
    *,
    headers: dict | None = None,
):
    """Return a sender yielding the given statuses in order."""

    calls: list[int] = []

    def send() -> httpx.Response:
        status = statuses[
            min(
                len(calls),
                len(statuses) - 1,
            )
        ]

        calls.append(
            status
        )

        return httpx.Response(
            status,
            headers=headers or {},
            request=httpx.Request(
                "GET",
                "https://example.invalid",
            ),
        )

    return send, calls


def no_sleep(
    _seconds: float,
) -> None:
    """Skip real waiting in tests."""


@pytest.mark.parametrize(
    "status",
    sorted(
        RETRYABLE_STATUS_CODES
    ),
)
def test_transient_statuses_are_retried(
    status: int,
) -> None:
    """A transient failure followed by success returns the success."""

    send, calls = responder(
        [
            status,
            200,
        ]
    )

    response = request_with_retry(
        send,
        sleeper=no_sleep,
    )

    assert response.status_code == 200

    assert len(calls) == 2


@pytest.mark.parametrize(
    "status",
    [
        200,
        301,
        400,
        404,
        410,
    ],
)
def test_non_transient_statuses_are_returned_immediately(
    status: int,
) -> None:
    """A 404 is a real answer, not something to retry.

    Retrying it would hide a catalog problem behind a slow poll.
    """

    send, calls = responder(
        [
            status,
        ]
    )

    response = request_with_retry(
        send,
        sleeper=no_sleep,
    )

    assert (
        response.status_code == status
    )

    assert len(calls) == 1


def test_attempts_are_bounded() -> None:
    """A permanently failing provider must not retry forever."""

    send, calls = responder(
        [
            503,
        ]
    )

    response = request_with_retry(
        send,
        max_attempts=3,
        sleeper=no_sleep,
    )

    assert response.status_code == 503

    assert len(calls) == 3


def test_transport_errors_are_retried_then_raised() -> None:
    """A connection failure is transient until it is not."""

    calls: list[int] = []

    def send() -> httpx.Response:
        calls.append(
            1
        )

        raise httpx.ConnectError(
            "no route to host"
        )

    with pytest.raises(
        httpx.ConnectError
    ):
        request_with_retry(
            send,
            max_attempts=3,
            sleeper=no_sleep,
        )

    assert len(calls) == 3


def test_transport_error_recovers_before_the_limit() -> None:
    calls: list[int] = []

    def send() -> httpx.Response:
        calls.append(
            1
        )

        if len(calls) < 2:
            raise httpx.ConnectError(
                "flaky"
            )

        return httpx.Response(
            200,
            request=httpx.Request(
                "GET",
                "https://example.invalid",
            ),
        )

    response = request_with_retry(
        send,
        sleeper=no_sleep,
    )

    assert response.status_code == 200


def test_retry_after_is_honoured() -> None:
    """A provider asking for a specific wait gets it."""

    waits: list[float] = []

    send, _calls = responder(
        [
            429,
            200,
        ],
        headers={
            "Retry-After": "7",
        },
    )

    request_with_retry(
        send,
        sleeper=waits.append,
    )

    assert waits == [
        7.0,
    ]


def test_absurd_retry_after_is_capped() -> None:
    """A poll must not sleep for minutes on one provider's say-so."""

    waits: list[float] = []

    send, _calls = responder(
        [
            503,
            200,
        ],
        headers={
            "Retry-After": "3600",
        },
    )

    request_with_retry(
        send,
        sleeper=waits.append,
    )

    assert waits == [
        MAX_DELAY_SECONDS,
    ]


def test_unparseable_retry_after_falls_back_to_backoff() -> None:
    """The HTTP-date form is valid but rare; backoff still applies."""

    waits: list[float] = []

    send, _calls = responder(
        [
            503,
            200,
        ],
        headers={
            "Retry-After": (
                "Wed, 21 Oct 2026 07:28:00 GMT"
            ),
        },
    )

    request_with_retry(
        send,
        sleeper=waits.append,
    )

    assert len(waits) == 1

    assert 0 < waits[0] <= MAX_DELAY_SECONDS


def test_backoff_grows_and_stays_bounded() -> None:
    """Later attempts wait longer, but never beyond the cap."""

    waits: list[float] = []

    send, _calls = responder(
        [
            503,
        ]
    )

    request_with_retry(
        send,
        max_attempts=5,
        base_delay_seconds=2.0,
        sleeper=waits.append,
    )

    assert len(waits) == 4

    assert waits[0] < waits[-1]

    assert all(
        0 < wait <= MAX_DELAY_SECONDS
        for wait in waits
    )
