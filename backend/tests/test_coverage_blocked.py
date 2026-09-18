"""Telling "nothing answered" apart from "answered, and refused".

Both arrive at the diagnosis as an empty string, so both were reported
as SITE_UNREACHABLE: "No website answered for this name. The company
may trade under another one." For a company that answers and turns ACE
away, every word of that is wrong, and it sends the user looking for a
domain that does not exist.

Indeed is the case that exposed it. Its own job board is its own
product: robots.txt disallows the posting pages, and the careers site
answers 403 to anything automated. That is deliberate and is respected
rather than worked around -- but it has to be *recorded* as that, or
it reads as a company ACE has not tried properly.
"""

from __future__ import annotations

import urllib.error

import pytest

from backend.app.coverage import probing
from backend.app.coverage.probing import (
    REFUSAL_STATUSES,
    refuses_automation,
)


class _Response:
    """A urlopen context manager answering with one status."""

    def __init__(
        self,
        status: int,
    ) -> None:
        self.status = status

    def __enter__(
        self,
    ):
        return self

    def __exit__(
        self,
        *exc,
    ) -> bool:
        return False


def test_a_refusal_status_is_a_refusal(
    monkeypatch,
) -> None:
    """401, 403 and 429 all mean the site answered and said no."""

    for status in sorted(
        REFUSAL_STATUSES
    ):
        monkeypatch.setattr(
            probing.urllib.request,
            "urlopen",
            lambda *a, status=status, **k: _Response(
                status
            ),
        )

        assert refuses_automation(
            "https://example.com"
        ), status


def test_a_refusal_raised_as_an_error_still_counts(
    monkeypatch,
) -> None:
    """urllib raises on 403 rather than returning it.

    Reading the status only off a returned response would miss every
    real refusal, which is the shape this is most likely to take.
    """

    def raise_403(
        *args,
        **kwargs,
    ):
        raise urllib.error.HTTPError(
            "https://example.com",
            403,
            "Forbidden",
            {},
            None,
        )

    monkeypatch.setattr(
        probing.urllib.request,
        "urlopen",
        raise_403,
    )

    assert refuses_automation(
        "https://example.com"
    )


def test_a_site_that_does_not_answer_is_not_a_refusal(
    monkeypatch,
) -> None:
    """The distinction only earns its place if it is narrow.

    A domain that does not resolve is still "nothing answered", and
    calling that a refusal would lose the difference in the other
    direction.
    """

    def raise_dns(
        *args,
        **kwargs,
    ):
        raise OSError(
            "name or service not known"
        )

    monkeypatch.setattr(
        probing.urllib.request,
        "urlopen",
        raise_dns,
    )

    assert not refuses_automation(
        "https://example.invalid"
    )


def test_an_ordinary_page_is_not_a_refusal(
    monkeypatch,
) -> None:
    """A 200 is a site ACE can read, whatever it then finds there."""

    monkeypatch.setattr(
        probing.urllib.request,
        "urlopen",
        lambda *a, **k: _Response(
            200
        ),
    )

    assert not refuses_automation(
        "https://example.com"
    )


def test_a_404_is_not_a_refusal(
    monkeypatch,
) -> None:
    """A missing page is a missing page. Only the statuses that mean
    "you specifically are not allowed" count, or every dead careers
    URL would be reported as deliberate blocking.
    """

    def raise_404(
        *args,
        **kwargs,
    ):
        raise urllib.error.HTTPError(
            "https://example.com",
            404,
            "Not Found",
            {},
            None,
        )

    monkeypatch.setattr(
        probing.urllib.request,
        "urlopen",
        raise_404,
    )

    assert not refuses_automation(
        "https://example.com"
    )
