"""Tests for finding a company's board without being told the token.

The dangerous failure is not missing a board, it is subscribing to the
wrong company's. Most of these cases are drawn from real boards where
that nearly happened.
"""

from __future__ import annotations

import json

from backend.app.coverage.probing import (
    board_belongs_to,
    careers_page_token,
    find_board,
    token_guesses,
)


def fake_fetch(
    responses: dict,
):
    """Return a fetch that answers from a url -> payload mapping."""

    def fetch(
        url: str,
        **_,
    ):
        for fragment, payload in responses.items():
            if fragment in url:
                return payload

        return None

    return fetch


def test_guesses_are_few_and_ordered() -> None:
    """Every extra guess is a request against someone else's API and
    another chance to match an unrelated board."""

    assert token_guesses(
        "Lucid Software"
    ) == [
        "lucidsoftware",
        "lucid-software",
        "lucid",
    ]

    # A short first word matches anything, so it is not guessed alone.
    assert "ai" not in token_guesses(
        "AI Labs"
    )


def test_a_board_naming_another_company_is_refused() -> None:
    """"Applied Materials" reduces to "applied", which is a live Ashby
    board belonging to Applied Intuition. Subscribing to it would fill
    the queue with another employer's jobs under a name the user
    recognises."""

    assert board_belongs_to(
        fetch_text=lambda url: "",
        company="Applied Materials",
        source_type="greenhouse",
        token="applied",
        jobs=[
            {
                "title": "Engineer",
                "descriptionPlain": (
                    "Applied Intuition builds "
                    "autonomy software."
                ),
            }
        ],
        fetch=fake_fetch(
            {
                "boards/applied": {
                    "name": "Applied Intuition",
                },
            }
        ),
    ) is None


def test_a_url_built_from_the_guess_is_not_evidence() -> None:
    """A Greenhouse job's absolute_url is boards.greenhouse.io/<token>,
    so checking it for a token derived from the company name proves
    only that the guess was consistent with itself."""

    assert board_belongs_to(
        fetch_text=lambda url: "",
        company="Current",
        source_type="greenhouse",
        token="current",
        jobs=[
            {
                "absolute_url": (
                    "https://boards.greenhouse.io"
                    "/current/jobs/1"
                ),
            }
        ],
        fetch=fake_fetch(
            {}
        ),
    ) is None


def test_the_board_declaring_itself_is_evidence() -> None:
    """The employer writes the board name; ACE does not."""

    assert board_belongs_to(
        company="Pinterest",
        source_type="greenhouse",
        token="pinterest",
        jobs=[],
        fetch=fake_fetch(
            {
                "boards/pinterest": {
                    "name": "Pinterest",
                },
            }
        ),
    ) == "board declares itself 'Pinterest'"


def test_a_board_page_title_names_the_employer() -> None:
    """Ashby and Lever publish no board metadata, but both put the
    employer in the page title: "Ramp Jobs", "Wealthfront". Written by
    the employer and not derived from the token."""

    assert board_belongs_to(
        company="Ramp",
        source_type="ashby",
        token="ramp",
        jobs=[],
        fetch=fake_fetch(
            {}
        ),
        fetch_text=lambda url: (
            "<title>Ramp Jobs</title>"
        ),
    ) == "board page titled 'Ramp'"


def test_a_board_page_naming_another_employer_is_refused(
) -> None:
    """The same check that admits Ramp has to exclude everyone else."""

    assert board_belongs_to(
        company="Ramp Networks",
        source_type="ashby",
        token="ramp",
        jobs=[],
        fetch=fake_fetch(
            {}
        ),
        fetch_text=lambda url: (
            "<title>Ramp Jobs</title>"
        ),
    ) is None


def test_posting_text_carries_boards_with_no_title() -> None:
    """Last resort when neither metadata nor a title is available."""

    assert board_belongs_to(
        company="Anyscale",
        source_type="ashby",
        token="anyscale",
        jobs=[
            {
                "descriptionPlain": (
                    "Anyscale is the company "
                    "behind Ray."
                ),
            }
        ],
        fetch=fake_fetch(
            {}
        ),
        fetch_text=lambda url: "",
    ) == "company named in posting descriptionPlain"


def test_an_unverifiable_board_is_dropped() -> None:
    """A wrong subscription is harder to notice than a gap, so silence
    is the safe answer."""

    assert find_board(
        "Some Startup",
        fetch=fake_fetch(
            {
                "greenhouse.io/v1/boards/somestartup/jobs": {
                    "jobs": [
                        {
                            "title": "Engineer",
                        }
                    ],
                },
            }
        ),
        fetch_text=lambda url: "",
    ) is None


def test_a_token_unlike_the_name_is_read_from_the_page() -> None:
    """Current's board is "current81" while "current" is a different
    employer's live board, so guessing cannot reach it."""

    assert careers_page_token(
        '<script src="https://boards.greenhouse.io/embed/'
        'job_board/js?for=current81"></script>'
    ) == (
        "greenhouse",
        "current81",
    )


def test_the_embed_path_is_not_mistaken_for_a_token() -> None:
    """"embed" and "job_board" appear in the URL before the token."""

    found = careers_page_token(
        "https://boards.greenhouse.io/embed/job_board?for=acme"
    )

    assert found == (
        "greenhouse",
        "acme",
    )


# ----------------------------------------------------------------------
# Reading the token off a company's own careers page
#
# The route that reaches a board named nothing like its employer.
# Sourcegraph publishes at "sourcegraph91"; no guess derived from the
# name gets there, and their careers page says so plainly.
# ----------------------------------------------------------------------


def test_a_token_read_from_a_page_is_still_verified() -> None:
    """Reading is not trusting.

    Mistral's careers page links a jobs.ashbyhq.com/mistral board that
    returns 404. A route that registered what it read would have
    subscribed ACE to nothing at all, under a name the user recognises.
    """

    from backend.app.coverage.probing import (
        find_board_via_careers_page,
    )

    def fetch_text(
        _url: str,
    ) -> str:
        return (
            '<a href="https://jobs.ashbyhq.com/'
            'ghosttown">Careers</a>'
        )

    def fetch(
        _url: str,
    ):
        # The board the page pointed at does not answer.
        return None

    assert find_board_via_careers_page(
        "Ghost Town",
        fetch=fetch,
        fetch_text=fetch_text,
    ) is None


def test_a_verified_token_from_a_page_is_accepted() -> None:
    """The Sourcegraph case, which name-guessing cannot reach."""

    from backend.app.coverage.probing import (
        find_board_via_careers_page,
    )

    def fetch_text(
        url: str,
    ) -> str:
        if "careers" in url:
            return (
                '<a href="https://boards.greenhouse.io/'
                'sourcegraph91">Open roles</a>'
            )

        return ""

    def fetch(
        url: str,
    ):
        if "sourcegraph91" in url:
            return {
                "jobs": [
                    {
                        "title": (
                            "Software Engineer"
                        ),
                        "location": {
                            "name": "Remote",
                        },
                    },
                ],
                "name": "Sourcegraph",
            }

        return None

    found = find_board_via_careers_page(
        "Sourcegraph",
        fetch=fetch,
        fetch_text=fetch_text,
    )

    assert found is not None

    assert (
        found.source_account
        == "sourcegraph91"
    )
