"""Finding a company's board when it is on Eightfold.

The probe searched by token -- greenhouse/<slug>, ashby/<slug> -- and
Eightfold has no token: each tenant lives on a host the company
chooses. So every company on Eightfold was reported "no board found",
indistinguishable from a careers page ACE genuinely cannot read.

Microsoft was one. A Software Engineering II role it posted on 15
September reached the queue on 4 October, nineteen days late, through
a curated feed -- while its own board was readable the whole time by an
adapter ACE already had.

All of these run against recorded shapes, never the live site: the
live site rate-limited this probe once already.
"""

from __future__ import annotations

from backend.app.coverage.probing import (
    find_eightfold_board,
)


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


def test_microsoft_s_pcsx_board_is_found() -> None:
    """The case that went nineteen days unnoticed."""

    fetch = responder(
        {
            "https://apply.careers.microsoft.com/api/pcsx/search": {
                "data": {
                    "count": 2314,
                    "positions": [
                        {
                            "id": 1,
                            "name": "Software Engineer",
                        }
                    ],
                },
            },
        }
    )

    found = find_eightfold_board(
        "Microsoft",
        [
            "microsoft.com",
        ],
        fetch=fetch,
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
    fetch = responder(
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
    )

    found = find_eightfold_board(
        "Acme",
        [
            "acme.com",
        ],
        fetch=fetch,
    )

    assert found is not None
    assert found.source_type == "eightfold"
    assert found.source_host == "acme.eightfold.ai"


def test_a_tenant_answering_with_nothing_is_not_a_board() -> None:
    """A 200 with no postings says nothing about whose board it is."""

    fetch = responder(
        {
            "https://careers.acme.com/api/pcsx/search": {
                "data": {
                    "count": 0,
                    "positions": [],
                },
            },
        }
    )

    assert find_eightfold_board(
        "Acme",
        [
            "acme.com",
        ],
        fetch=fetch,
    ) is None


def test_nothing_answering_is_none_and_the_request_count_is_bounded() -> None:
    """Most companies are not on Eightfold, and the probe runs over
    hundreds of them. The cost of finding that out has to stay small:
    two domain guesses, four hosts, two routes."""

    fetch = responder(
        {}
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
    ) is None

    assert len(
        fetch.asked
    ) == 2 * 4 * 2, len(
        fetch.asked
    )
