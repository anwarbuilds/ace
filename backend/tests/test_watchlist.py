"""Reading an aggregator for names and nothing else.

The standing invariant is that an apply link is always the employer's
own posting, and an aggregator lane was built once and deleted the
next day for failing it. Nothing here revisits that. What this covers
is the narrower claim that made the lane worth revisiting at all: the
*name* is useful even when the link is not. Told that Algolia is
hiring, ACE reads Algolia's own board and gets all of it.

So the thing worth pinning is the boundary. If anything but a name
ever comes out of here, the deleted lane is back.
"""

from __future__ import annotations

import httpx

from backend.app.discovery.watchlist import (
    WATCHED_CATEGORIES,
    fetch_watchlist,
    parse_companies,
)


def page(
    *companies: str,
) -> str:
    """One category page, shaped like the real embedded state."""

    listed = ",".join(
        '{"jobTitle":"Software Engineer",'
        f'"companyName":"{name}",'
        '"applyLink":"https://jobright.ai/jobs/info/abc"}'
        for name in companies
    )

    return (
        "<!doctype html><html><body>"
        '<script id="__NEXT_DATA__" type="application/json">'
        f'{{"props":{{"jobs":[{listed}]}}}}'
        "</script></body></html>"
    )


def test_the_employers_are_read_off_the_page() -> None:
    assert parse_companies(
        page(
            "Algolia",
            "Upstart",
        )
    ) == {
        "Algolia",
        "Upstart",
    }


def test_an_escaped_name_arrives_as_it_is_written() -> None:
    """"Moody\\u2019s" is Moody's. Probing for the literal backslash
    would find nobody, and the company would read as unreachable when
    it had simply never been asked for properly."""

    assert parse_companies(
        '"companyName":"Moody\\u2019s"',
    ) == {
        "Moody’s",
    }


def test_a_page_naming_nobody_yields_nobody() -> None:
    """A layout change should cost ACE the names, not raise."""

    assert parse_companies(
        "<html><body>nothing here</body></html>",
    ) == set()


def _transport(
    pages: dict[str, str],
) -> httpx.MockTransport:
    def handle(
        request: httpx.Request,
    ) -> httpx.Response:
        slug = request.url.path.rsplit(
            "/",
            1,
        )[-1]

        if slug not in pages:
            return httpx.Response(
                404,
                text="gone",
            )

        return httpx.Response(
            200,
            text=pages[slug],
        )

    return httpx.MockTransport(
        handle,
    )


def test_every_watched_category_is_read_and_merged() -> None:
    client = httpx.Client(
        transport=_transport(
            {
                "software-engineering": page(
                    "Algolia",
                    "Ramp",
                ),
                "ai-engineer": page(
                    "Upstart",
                    "Ramp",
                ),
            }
        ),
    )

    assert fetch_watchlist(
        categories=(
            "software-engineering",
            "ai-engineer",
        ),
        client=client,
    ) == [
        "Algolia",
        "Ramp",
        "Upstart",
    ]


def test_one_dead_category_does_not_lose_the_rest() -> None:
    """This is a tip-off, and a partial tip-off is still worth acting
    on. A slug that stops existing must not cost ACE the others."""

    client = httpx.Client(
        transport=_transport(
            {
                "software-engineering": page(
                    "Algolia",
                ),
            }
        ),
    )

    assert fetch_watchlist(
        categories=(
            "software-engineering",
            "a-category-that-was-renamed",
        ),
        client=client,
    ) == [
        "Algolia",
    ]


def test_nothing_but_names_comes_out() -> None:
    """The boundary, stated as a test.

    The page carries a title and an apply link for every role, and
    both are deliberately left behind: the link is the aggregator's
    own, which is the exact thing the deleted lane was deleted for. If
    this ever returns anything but a company name, that lane is back.
    """

    client = httpx.Client(
        transport=_transport(
            {
                "software-engineering": page(
                    "Algolia",
                ),
            }
        ),
    )

    names = fetch_watchlist(
        categories=(
            "software-engineering",
        ),
        client=client,
    )

    assert names == [
        "Algolia",
    ]

    for name in names:
        assert isinstance(
            name,
            str,
        )

        assert "jobright" not in name.lower()
        assert "http" not in name.lower()


def test_the_watched_categories_are_ones_this_user_would_apply_to() -> None:
    """A category nobody here would apply to is a page not worth
    fetching, and this list is the whole reason the request count
    stays small."""

    assert WATCHED_CATEGORIES

    assert any(
        "software" in slug
        for slug in WATCHED_CATEGORIES
    )
