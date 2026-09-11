"""Saying why a company is out of reach, not only that it is.

Coverage reported 154 companies as unreachable and could not say why
any of them were. Auditing that list by hand found most of them were
not unreachable at all -- they were on an ATS ACE could already read
and had never probed, or had been refused over a spelling, or had a
careers page a little larger than the buffer that read it.

Each case below is one of those, kept so the next round of it is a
query rather than an afternoon.
"""

from __future__ import annotations

from backend.app.coverage.diagnosis import (
    NO_BOARD_FOUND,
    NO_POSTINGS,
    OTHER_ATS,
    REACHED,
    REFUSED,
    SITE_UNREACHABLE,
    diagnose,
    foreign_ats_in,
)


def no_json(
    _url: str,
):
    """A board that does not answer."""

    return None


def no_pages(
    _url: str,
) -> str:
    """A company with no website ACE can find."""

    return ""


def test_an_ats_ace_cannot_read_is_named_rather_than_shrugged_at(
) -> None:
    """"Rivian is on iCIMS" is a decision waiting to be made.
    "Rivian is unreachable" is a shrug."""

    def fetch_text(
        url: str,
    ) -> str:
        return (
            "<title>Rivian</title>"
            '<a href="https://us-careers-rivian'
            '.icims.com/jobs">Search jobs</a>'
        )

    result = diagnose(
        "Rivian",
        fetch=no_json,
        fetch_text=fetch_text,
    )

    assert result.outcome == OTHER_ATS

    assert "iCIMS" in result.detail


def test_a_readable_board_with_nothing_on_it_is_not_a_failure(
) -> None:
    """Chronosphere's Ashby board answers and is empty. That is worth
    distinguishing from a board ACE cannot find, because there is
    nothing to fix."""

    def fetch_text(
        url: str,
    ) -> str:
        if "ashbyhq" in url:
            return ""

        return (
            "<title>Chronosphere</title>"
            '<a href="https://jobs.ashbyhq.com/'
            'chronospherejobs">Careers</a>'
        )

    def fetch(
        url: str,
    ):
        if "chronospherejobs" in url:
            return {
                "jobs": [],
            }

        return None

    result = diagnose(
        "Chronosphere",
        fetch=fetch,
        fetch_text=fetch_text,
    )

    assert result.outcome == NO_POSTINGS

    assert (
        "chronospherejobs"
        in result.detail
    )


def test_a_board_naming_someone_else_is_reported_as_refused(
) -> None:
    """Sana Labs' careers page links Workday's own tenant, because
    they are a Workday customer. The refusal is right, and saying so
    is better than reporting the company as simply missing."""

    def fetch_text(
        url: str,
    ) -> str:
        if "myworkdayjobs" in url:
            return ""

        return (
            "<title>Sana</title>"
            '<a href="https://workday.wd5'
            '.myworkdayjobs.com/Workday/job/x">'
            "Open roles</a>"
        )

    result = diagnose(
        "Sana Labs",
        fetch=no_json,
        fetch_text=fetch_text,
        post=lambda url, payload: {
            "jobPostings": [
                {
                    "title": (
                        "Software Engineer"
                    ),
                },
            ],
        },
    )

    assert result.outcome == REFUSED

    assert "workday" in result.detail


def test_a_site_that_points_nowhere_says_so() -> None:
    """The genuinely hard case: a careers page that builds itself in
    the browser. Worth separating from the cases ACE can fix."""

    result = diagnose(
        "Glean",
        fetch=no_json,
        fetch_text=lambda url: (
            "<title>Glean | Work AI</title>"
            "<div id=root></div>"
        ),
    )

    assert result.outcome == NO_BOARD_FOUND


def test_a_name_no_website_answers_for_is_its_own_outcome() -> None:
    """These are the ones the paste-a-link box fixes outright, so they
    are worth telling apart from the ones it cannot."""

    result = diagnose(
        "Some Company That Does Not Exist",
        fetch=no_json,
        fetch_text=no_pages,
    )

    assert result.outcome == SITE_UNREACHABLE


def test_a_board_that_is_found_is_reported_with_its_evidence(
) -> None:
    """The reached case still carries why it was believed."""

    def fetch(
        url: str,
    ):
        if "sourcegraph91" in url:
            return {
                "name": "Sourcegraph",
                "jobs": [
                    {
                        "title": (
                            "Software Engineer"
                        ),
                    },
                ],
            }

        return None

    result = diagnose(
        "Sourcegraph",
        fetch=fetch,
        fetch_text=lambda url: (
            '<a href="https://boards.greenhouse'
            '.io/sourcegraph91">Roles</a>'
        ),
    )

    assert result.outcome == REACHED

    assert result.candidate is not None

    assert (
        result.candidate.source_account
        == "sourcegraph91"
    )


def test_every_named_ats_is_one_ace_genuinely_cannot_read() -> None:
    """The list is a work queue, so a name on it has to mean an
    adapter that does not exist -- not one ACE simply forgot to probe,
    which is what Workday and SmartRecruiters were."""

    assert foreign_ats_in(
        "https://careers-jobyaviation.icims.com/jobs"
    ) == "iCIMS"

    assert foreign_ats_in(
        "https://zendesk.wd1.myworkdayjobs.com/zendesk"
    ) is None

    assert foreign_ats_in(
        "https://careers.smartrecruiters.com/Freshworks"
    ) is None
