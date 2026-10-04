"""Finding a company's board when it is on Eightfold.

The probe searched by token -- greenhouse/<slug>, ashby/<slug> -- and
Eightfold has no token: each tenant lives on a host the company
chooses. So every company on Eightfold was reported "no board found",
indistinguishable from a careers page ACE genuinely cannot read.

Microsoft was one. A Software Engineering II role it posted on 15
September reached the queue on 4 October, nineteen days late, through
a curated feed -- while its own board was readable the whole time by an
adapter ACE already had. Re-probing with the fix found seven more:
Applied Materials, Arcadis, Eaton, John Deere, Qualcomm, Ralliant and
Starbucks.

Those hosts are the companies' own careers domains, so robots.txt is
asked before anything is registered there. All of these run against
recorded shapes, never the live site: the live site rate-limited this
probe once already.
"""

from __future__ import annotations

from backend.app.coverage.probing import (
    find_eightfold_board,
    robots_allows,
)


# The robots.txt every Eightfold tenant seen so far publishes. It denies
# everything, then opens the API routes by name.
EIGHTFOLD_ROBOTS = """User-agent: *
Disallow: /
Allow: /$
Allow: /careers
Allow: /api/apply
Allow: /api/pcsx
"""

MICROSOFT_SEARCH = {
    "data": {
        "count": 2314,
        "positions": [
            {
                "id": 1,
                "name": "Software Engineer",
            }
        ],
    },
}


def responder(
    answers: dict[str, object],
):
    """A fetch that answers only the URLs it is given."""

    asked: list[str] = []

    def fetch(
        url: str,
        **kwargs,
    ):
        asked.append(
            url
        )

        for prefix, payload in answers.items():
            if url.startswith(
                prefix
            ):
                return payload

        return None

    fetch.asked = asked

    return fetch


def robots(
    text: str | None = "",
):
    """A robots fetcher answering every host the same way."""

    asked: list[str] = []

    def fetch_robots(
        host: str,
    ):
        asked.append(
            host
        )

        return text

    fetch_robots.asked = asked

    return fetch_robots


# --- finding the board -----------------------------------------------


def test_microsoft_s_pcsx_board_is_found() -> None:
    """The case that went nineteen days unnoticed."""

    found = find_eightfold_board(
        "Microsoft",
        [
            "microsoft.com",
        ],
        fetch=responder(
            {
                "https://apply.careers.microsoft.com/api/pcsx/search": (
                    MICROSOFT_SEARCH
                ),
            }
        ),
        fetch_robots=robots(
            EIGHTFOLD_ROBOTS
        ),
    )

    assert found is not None, (
        "Microsoft's Eightfold board was not found, which is what "
        "left its jobs to arrive weeks late through a curated feed"
    )

    assert found.source_type == "eightfold_pcsx"
    assert found.source_host == "apply.careers.microsoft.com"
    assert found.source_account == "microsoft.com"
    assert found.job_count == 2314


def test_a_classic_eightfold_tenant_is_found_too() -> None:
    found = find_eightfold_board(
        "Acme",
        [
            "acme.com",
        ],
        fetch=responder(
            {
                "https://acme.eightfold.ai/api/apply/v2/jobs": {
                    "count": 40,
                    "positions": [
                        {
                            "id": 7,
                        }
                    ],
                },
            }
        ),
        fetch_robots=robots(
            EIGHTFOLD_ROBOTS
        ),
    )

    assert found is not None
    assert found.source_type == "eightfold"
    assert found.source_host == "acme.eightfold.ai"


def test_a_tenant_answering_with_nothing_is_not_a_board() -> None:
    """A 200 with no postings says nothing about whose board it is."""

    assert find_eightfold_board(
        "Acme",
        [
            "acme.com",
        ],
        fetch=responder(
            {
                "https://careers.acme.com/api/pcsx/search": {
                    "data": {
                        "count": 0,
                        "positions": [],
                    },
                },
            }
        ),
        fetch_robots=robots(
            ""
        ),
    ) is None


def test_the_request_count_is_bounded() -> None:
    """Most companies are not on Eightfold, and the probe runs over
    hundreds of them: two domain guesses, four hosts, one robots.txt
    per host and at most two routes on each."""

    fetch = responder(
        {}
    )

    fetch_robots = robots(
        ""
    )

    assert find_eightfold_board(
        "Acme",
        [
            "acme.com",
            "acme.ai",
            "acme.io",
            "acme.co",
        ],
        fetch=fetch,
        fetch_robots=fetch_robots,
    ) is None

    assert len(
        fetch_robots.asked
    ) == 2 * 4

    assert len(
        fetch.asked
    ) == 2 * 4 * 2


# --- robots.txt decides ----------------------------------------------


def test_a_route_robots_txt_forbids_is_never_asked() -> None:
    """A company that closes its API to crawlers is not crawled, however
    readable the API would turn out to be."""

    fetch = responder(
        {
            "https://apply.careers.microsoft.com/api/pcsx/search": (
                MICROSOFT_SEARCH
            ),
        }
    )

    found = find_eightfold_board(
        "Microsoft",
        [
            "microsoft.com",
        ],
        fetch=fetch,
        fetch_robots=robots(
            "User-agent: *\nDisallow: /api/\n"
        ),
    )

    assert found is None

    assert not any(
        "/api/" in url
        for url in fetch.asked
    ), "a route robots.txt forbids was requested anyway"


def test_an_unreadable_robots_txt_means_hands_off() -> None:
    """RFC 9309: if the rules cannot be read because of a server or
    network error, assume everything is disallowed. It also spares the
    API requests on guessed hosts that do not exist."""

    fetch = responder(
        {
            "https://apply.careers.microsoft.com/api/pcsx/search": (
                MICROSOFT_SEARCH
            ),
        }
    )

    assert find_eightfold_board(
        "Microsoft",
        [
            "microsoft.com",
        ],
        fetch=fetch,
        fetch_robots=robots(
            None
        ),
    ) is None

    assert fetch.asked == []


def test_the_eightfold_template_allows_the_api() -> None:
    """The trap. Python's urllib.robotparser applies the first matching
    rule, so on this template "Disallow: /" wins and every Eightfold
    tenant -- Microsoft included -- reads as closed. RFC 9309 says the
    longest match wins, and "/api/pcsx" is longer than "/"."""

    assert robots_allows(
        EIGHTFOLD_ROBOTS,
        "https://careers.qualcomm.com/api/pcsx/search"
        "?domain=qualcomm.com&query=&start=0",
    )

    assert robots_allows(
        EIGHTFOLD_ROBOTS,
        "https://careers.qualcomm.com/api/apply/v2/jobs"
        "?domain=qualcomm.com&start=0&num=10",
    )

    # And the rest of the site is still closed, as the company asked.
    assert not robots_allows(
        EIGHTFOLD_ROBOTS,
        "https://careers.qualcomm.com/internal/admin",
    )


def test_a_tie_goes_to_allow() -> None:
    assert robots_allows(
        "User-agent: *\nDisallow: /api\nAllow: /api\n",
        "https://example.com/api/x",
    )


def test_the_end_anchor_and_the_wildcard() -> None:
    rules = (
        "User-agent: *\n"
        "Disallow: /*.json$\n"
        "Allow: /$\n"
        "Disallow: /\n"
    )

    # "/$" matches the root only, so the root is open...
    assert robots_allows(
        rules,
        "https://example.com/",
    )

    # ...and nothing else is.
    assert not robots_allows(
        rules,
        "https://example.com/careers",
    )

    assert not robots_allows(
        rules,
        "https://example.com/feed/jobs.json",
    )


def test_a_group_naming_this_agent_overrides_the_star_group() -> None:
    rules = (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        "User-agent: ACE-source-discovery\n"
        "Disallow: /\n"
    )

    assert not robots_allows(
        rules,
        "https://example.com/api/pcsx/search",
    )


def test_no_robots_txt_means_no_rules() -> None:
    assert robots_allows(
        "",
        "https://example.com/anything",
    )
