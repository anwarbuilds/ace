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

    found = careers_page_token(
        '<script src="https://boards.greenhouse.io/embed/'
        'job_board/js?for=current81"></script>'
    )

    assert found is not None

    assert found.source_type == "greenhouse"

    assert found.token == "current81"


def test_the_embed_path_is_not_mistaken_for_a_token() -> None:
    """"embed" and "job_board" appear in the URL before the token."""

    found = careers_page_token(
        "https://boards.greenhouse.io/embed/job_board?for=acme"
    )

    assert found is not None

    assert found.source_type == "greenhouse"

    assert found.token == "acme"


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


# ----------------------------------------------------------------------
# Reaching the boards that were counted as unreachable
#
# A hundred and fifty-four curated companies were reported as out of
# reach. Almost none of them were. The cases below are each a real
# company that ACE could already have read, blocked by something in
# here rather than by anything the employer did.
# ----------------------------------------------------------------------


def test_a_company_that_writes_its_own_domain_is_the_same_company(
) -> None:
    """Calm's Greenhouse board declares itself "Calm.com".

    Compared for exact equality against "Calm", that rejected a board
    that is plainly theirs, and rejected it early -- the code returns
    immediately once a board names somebody, so no weaker evidence was
    ever consulted. Calm was reported as a company ACE could not see.
    """

    assert board_belongs_to(
        company="Calm",
        source_type="greenhouse",
        token="calm",
        jobs=[],
        fetch=fake_fetch(
            {
                "https://boards-api.greenhouse.io"
                "/v1/boards/calm": {
                    "name": "Calm.com",
                },
            }
        ),
        fetch_text=lambda url: "",
    ) == "board declares itself 'Calm.com'"


def test_a_longer_name_still_does_not_match_a_shorter_board(
) -> None:
    """The guard on the fix above.

    Accepting "Calm.com" for "Calm" must not become accepting anything
    that starts the same way. "Ramp Networks" is not Ramp, and
    "Aurora Innovation" is not Aurora Labs -- ACE polled Aurora Labs
    for a while on exactly that reasoning.
    """

    for company, titled in (
        ("Ramp Networks", "Ramp Jobs"),
        ("Aurora Innovation", "Aurora Labs"),
    ):
        assert board_belongs_to(
            company=company,
            source_type="ashby",
            token="ramp",
            jobs=[],
            fetch=fake_fetch(
                {}
            ),
            fetch_text=lambda url, titled=titled: (
                f"<title>{titled}</title>"
            ),
        ) is None


def test_smartrecruiters_is_verified_by_the_name_on_its_postings(
) -> None:
    """SmartRecruiters publishes no board metadata, but every posting
    carries the employer's own name, which is the same quality of
    evidence rather than the weaker read of posting prose."""

    assert board_belongs_to(
        company="Freshworks",
        source_type="smartrecruiters",
        token="freshworks",
        jobs=[
            {
                "name": "Software Engineer",
                "company": {
                    "identifier": "Freshworks",
                    "name": "Freshworks",
                },
            },
        ],
        fetch=fake_fetch(
            {}
        ),
        fetch_text=lambda url: "",
    ) == "board declares itself 'Freshworks'"


def test_a_workday_url_yields_a_tenant_a_site_and_a_host() -> None:
    """Workday is the one board that cannot be guessed at all.

    The data-centre number is not derivable from anything -- Zendesk
    is on wd1, BigCommerce on wd12, NVIDIA on wd5 -- so all three
    facts have to come off the page together.
    """

    found = careers_page_token(
        '<a href="https://bostondynamics.wd1.myworkdayjobs.com'
        '/en-US/Boston_Dynamics/introduceYourself">Apply</a>'
    )

    assert found is not None

    assert found.source_type == "workday"

    # The locale is not the site name.
    assert found.token == (
        "bostondynamics/Boston_Dynamics"
    )

    assert found.source_host == (
        "bostondynamics.wd1.myworkdayjobs.com"
    )


def test_a_workday_board_on_somebody_elses_tenant_is_refused(
) -> None:
    """Sana Labs' careers page links Workday's own tenant, because
    they run their hiring on Workday the product. Believing the link
    would have subscribed ACE to Workday Inc's vacancies under the
    name "Sana Labs"."""

    from backend.app.coverage.probing import (
        workday_belongs_to,
    )

    assert workday_belongs_to(
        company="Sana Labs",
        token="workday/Workday",
    ) is None

    assert workday_belongs_to(
        company="Slack",
        token="salesforce/Slack",
    ) is None

    # Their own tenant, abbreviated the way employers abbreviate.
    assert workday_belongs_to(
        company="Devoted Health",
        token="devoted/Devoted",
    ) is not None


def test_the_wrong_companys_website_is_not_searched() -> None:
    """Guessing "<name>.com" landed on Omron's robotics division for
    "Adept" and on an unrelated software firm for "Beta Technologies".

    Nothing bad reached the database, because a board is verified
    against the employer's own name afterwards. But the one failure
    that check cannot catch is the wrong page linking a board that
    passes anyway, which is how ACE came to poll Aurora Labs.
    """

    from backend.app.coverage.probing import (
        page_claims_another_company,
        page_names_company,
    )

    assert page_claims_another_company(
        "Adept",
        "<title>Omron Robotics and Safety "
        "Technologies</title>",
    )

    # Column Bank publishes at column.com as "Column". Demanding the
    # whole name rejected the right site.
    assert page_names_company(
        "Column Bank",
        "<title>Column | The nationally "
        "chartered bank</title>",
    )

    # A page that names nobody is not evidence of anybody. Rejecting
    # it would lose the careers pages that are a bare list of links,
    # and the board it points at is verified regardless.
    assert not page_claims_another_company(
        "Sourcegraph",
        '<a href="https://boards.greenhouse.io/'
        'sourcegraph91">Open roles</a>',
    )


def test_a_board_linked_by_the_company_may_name_itself_more_briefly(
) -> None:
    """Column Bank's own careers page links a board titled "Column".

    That is weaker evidence than a board naming the company outright,
    and it is only ever reachable from a page already confirmed to be
    this company's. What is not relaxed is that the board must name a
    company, and it must be recognisably this one.
    """

    from backend.app.coverage.probing import (
        linked_board_belongs_to,
    )

    assert linked_board_belongs_to(
        company="Column Bank",
        source_type="ashby",
        token="column",
        fetch=fake_fetch(
            {}
        ),
        fetch_text=lambda url: (
            "<title>Column</title>"
        ),
    ) is not None

    # The Sana Labs failure again, one tier down.
    assert linked_board_belongs_to(
        company="Sana Labs",
        source_type="ashby",
        token="workday",
        fetch=fake_fetch(
            {}
        ),
        fetch_text=lambda url: (
            "<title>Workday</title>"
        ),
    ) is None


def test_a_name_that_is_already_a_domain_is_not_flattened() -> None:
    """"Bill.com" reduced to "billcom.com", which is somebody else."""

    from backend.app.coverage.probing import (
        domain_candidates,
    )

    assert domain_candidates(
        "Bill.com"
    )[0] == "bill.com"

    # Clay Labs is clay.com; the descriptive word is worth dropping
    # for a guess, and never for deciding two names are one company.
    assert "clay.com" in domain_candidates(
        "Clay Labs"
    )


# ----------------------------------------------------------------------
# The four boards that passed every check and were wrong anyway
#
# A sweep of the curated list proposed 26 boards. Auditing them by
# hand -- reading what each employer says it does -- found four that
# every automated check had accepted. Each one is below, because a
# failure that was caught by a person reading carefully will not be
# caught that way twice.
# ----------------------------------------------------------------------


def test_a_foundation_named_astera_is_not_astera_labs() -> None:
    """The Aurora failure again, one evidence tier down.

    normalise_company drops "Labs", so "Astera Labs" reduces to
    "astera" -- and the Astera Institute, a private research
    foundation, opens every posting with "ABOUT ASTERA". That board
    was proposed as the semiconductor company's.

    Posting prose is the weakest evidence ACE has, so it is held to
    the whole name: a board belonging to Astera Labs says "Astera
    Labs" somewhere, and a foundation called Astera does not.
    """

    assert board_belongs_to(
        company="Astera Labs",
        source_type="ashby",
        token="a-board",
        jobs=[
            {
                "title": (
                    "Machine Learning "
                    "Researcher"
                ),
                "descriptionPlain": (
                    "ABOUT ASTERA Astera is a "
                    "private foundation on a "
                    "mission to steer science."
                ),
            },
        ],
        fetch=fake_fetch(
            {}
        ),
        fetch_text=lambda url: "",
    ) is None


def test_the_company_named_in_a_posting_still_counts() -> None:
    """The guard on the fix above: prose remains real evidence when
    the posting actually names the company."""

    assert board_belongs_to(
        company="Astera Labs",
        source_type="ashby",
        token="a-board",
        jobs=[
            {
                "title": "Design Engineer",
                "descriptionPlain": (
                    "Astera Labs is a "
                    "semiconductor connectivity "
                    "company."
                ),
            },
        ],
        fetch=fake_fetch(
            {}
        ),
        fetch_text=lambda url: "",
    ) is not None


def test_a_board_holding_only_test_postings_is_refused() -> None:
    """SmartRecruiters' "uber" board holds one posting, "Test UAT",
    and its "bigcommerce" board holds "Rene's Test Job" and "Test Job
    2". Both declare the right employer, so every name check passes.

    Subscribing to either would make the coverage page report a
    company as reached while ACE saw nothing real from it, which is
    the number lying -- the one thing that page exists to stop.
    """

    from backend.app.coverage.probing import (
        looks_like_a_sandbox,
    )

    assert looks_like_a_sandbox(
        [
            {
                "name": "Test UAT",
            },
        ]
    )

    assert looks_like_a_sandbox(
        [
            {
                "name": "Rene's Test Job",
            },
            {
                "name": "Test Job 2",
            },
        ]
    )

    # Real roles with "test" in the title, which is why the rule
    # needs more than that word to fire.
    assert not looks_like_a_sandbox(
        [
            {
                "title": (
                    "Test Infrastructure "
                    "Engineer"
                ),
            },
        ]
    )

    assert not looks_like_a_sandbox(
        [
            {
                "title": (
                    "SDET - Test Automation"
                ),
            },
        ]
    )

    # One test posting left on an otherwise real board is still a
    # real board.
    assert not looks_like_a_sandbox(
        [
            {
                "title": "Test Job",
            },
            {
                "title": (
                    "Senior Software Engineer"
                ),
            },
        ]
    )


def test_a_different_company_of_the_same_name_stays_refused() -> None:
    """Two real companies are called Glean: an enterprise search
    company and an expense-management fintech. The board declares
    "Glean", the list says "Glean", and they match because they are
    the same name.

    No rule separates them. The finding is recorded instead, so the
    next sweep does not propose it again and the reason does not live
    only in whoever remembered rejecting it.
    """

    assert board_belongs_to(
        company="Glean",
        source_type="smartrecruiters",
        token="glean",
        jobs=[
            {
                "name": (
                    "Senior Software Engineer"
                ),
                "company": {
                    "name": "Glean",
                },
            },
        ],
        fetch=fake_fetch(
            {}
        ),
        fetch_text=lambda url: "",
    ) is None


def test_a_domain_for_sale_is_not_the_company() -> None:
    """The site check's one blind spot.

    A parking page's title is the domain itself, so it contains the
    company's name and reads as a positive identification.
    worldlabs.com is titled "WORLDLABS.COM | Strategic-Grade domain
    names for established businesses and funds" -- and because finding
    a company's site ends the search, that cost the real World Labs at
    worldlabs.ai, whose careers page links an Ashby board in plain
    HTML.
    """

    from backend.app.coverage.probing import (
        looks_like_a_parked_domain,
    )

    assert looks_like_a_parked_domain(
        "<title>WORLDLABS.COM | "
        "Strategic-Grade domain names for "
        "established businesses</title>"
    )

    assert looks_like_a_parked_domain(
        "<h1>Buy this domain</h1>"
    )

    # Selling language, not the word "domain": a registrar describing
    # its own product is a real company with real vacancies.
    assert not looks_like_a_parked_domain(
        "<title>Namecheap</title><p>Register "
        "your domain name today.</p>"
    )

    assert not looks_like_a_parked_domain(
        "<title>World Labs</title>"
        "<p>We build spatial intelligence.</p>"
    )
