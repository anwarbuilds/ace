"""Tests for the Avature adapter.

The fixtures are trimmed copies of the real portal, including the Two
Sigma campus software engineering post in Houston that prompted the
source existing: a role on the company's own board that ACE had never
looked for, because five of its roles arriving through a feed had made
the company count as already reached.
"""

from __future__ import annotations

import httpx

from backend.app.adapters.avature import (
    fetch_avature_jobs,
    parse_job_page,
    parse_listing,
)


BASE = "https://careers.twosigma.com/careers"


def article(
    *,
    job_id: str,
    title: str,
    location: str = "United States - TX Houston",
) -> str:
    """One listing row, shaped like the real portal."""

    return (
        '<article class="article article--result">'
        '<div class="article__header">'
        '<h3 class="article__header__text__title title">'
        f'<a class="link" href="{BASE}/JobDetail/'
        f'Houston-Texas-{title.replace(" ", "-")}/{job_id}">'
        f" {title} </a></h3>"
        '<div class="article__header__content">'
        f'<span class="paragraph_inner-span">{location}</span>'
        "</div></div></article>"
    )


def listing(
    *articles: str,
) -> str:
    return (
        '<html><body><div class="results">'
        + "".join(
            articles
        )
        + "</div></body></html>"
    )


JOB_PAGE = """<html><body>
<div class="article__content">
  <div class="article__content__view__field">
    <h2>Software Engineering Full-Time Campus Hire (Houston)</h2>
  </div>
  <div class="article__content__view__field">
    <p>Build trading infrastructure.</p>
    <ul><li>0-2 years of experience.</li></ul>
  </div>
</div>
<footer>Share this job</footer>
</body></html>"""


# --- the listing is the snapshot ------------------------------------


def test_a_listing_row_gives_identity_title_and_location() -> None:
    rows = parse_listing(
        listing(
            article(
                job_id="14018",
                title="Software Engineering Full Time Campus Hire",
            )
        ),
        base_url=BASE,
    )

    assert len(
        rows
    ) == 1

    job_id, url, title, location = rows[0]

    assert job_id == "14018"
    assert url.endswith(
        "/14018"
    )
    assert title == (
        "Software Engineering Full Time Campus Hire"
    )
    assert location == (
        "United States - TX Houston"
    )


def test_a_row_with_no_link_is_dropped() -> None:
    """It could be neither fetched nor applied to."""

    assert parse_listing(
        '<article class="article article--result">'
        "<h3>Software Engineer</h3></article>",
        base_url=BASE,
    ) == []


def test_the_description_survives_as_readable_text() -> None:
    """The gate reads requirement text, so the paragraphs must not run
    together into one line."""

    text = parse_job_page(
        JOB_PAGE,
    )

    assert "Build trading infrastructure." in text
    assert "0-2 years of experience." in text
    assert "<p>" not in text

    assert "infrastructure.0-2" not in text


def test_a_page_with_no_content_region_is_empty_not_raised() -> None:
    """A posting whose description could not be read is still a real
    posting, and the gate treats missing requirement text as unknown
    rather than as disqualifying."""

    assert parse_job_page(
        "<html><body>nothing here</body></html>",
    ) == ""


# --- the whole fetch ------------------------------------------------


def _transport(
    pages: dict[int, str],
    *,
    job_pages: dict[str, str] | None = None,
) -> httpx.MockTransport:
    def handle(
        request: httpx.Request,
    ) -> httpx.Response:
        if "JobDetail" in request.url.path:
            job_id = request.url.path.rsplit(
                "/",
                1,
            )[-1]

            body = (
                job_pages or {}
            ).get(
                job_id,
                JOB_PAGE,
            )

            if body is None:
                return httpx.Response(
                    404,
                    text="gone",
                )

            return httpx.Response(
                200,
                text=body,
            )

        offset = int(
            request.url.params.get(
                "jobOffset",
                0,
            )
        )

        return httpx.Response(
            200,
            text=pages.get(
                offset,
                listing(),
            ),
        )

    return httpx.MockTransport(
        handle,
    )


def test_every_page_of_the_listing_is_walked() -> None:
    client = httpx.Client(
        transport=_transport(
            {
                0: listing(
                    article(
                        job_id="14018",
                        title="Campus Hire Houston",
                    )
                ),
                10: listing(
                    article(
                        job_id="14014",
                        title="Campus Hire NYC",
                    )
                ),
            }
        ),
    )

    jobs = fetch_avature_jobs(
        source_account=BASE,
        company_name="Two Sigma",
        client=client,
        concurrency=2,
    )

    assert {
        job.external_id
        for job in jobs
    } == {
        "14018",
        "14014",
    }

    assert {
        job.company
        for job in jobs
    } == {
        "Two Sigma",
    }


def test_a_repeated_page_ends_the_walk() -> None:
    """The portal repeats its last page rather than returning an empty
    one, so "nothing new" is the end. Stopping only on an empty page
    would never stop.
    """

    repeated = listing(
        article(
            job_id="14018",
            title="Campus Hire Houston",
        )
    )

    client = httpx.Client(
        transport=_transport(
            {
                offset: repeated
                for offset in range(
                    0,
                    900,
                    10,
                )
            }
        ),
    )

    jobs = fetch_avature_jobs(
        source_account=BASE,
        company_name="Two Sigma",
        client=client,
        concurrency=2,
    )

    assert [
        job.external_id
        for job in jobs
    ] == [
        "14018",
    ]


def test_one_dead_posting_does_not_empty_the_snapshot() -> None:
    """The failure that matters most.

    A snapshot missing most of its postings would not be refused by
    persistence -- it would close them. So a page that 404s is dropped
    and the rest still arrive.
    """

    client = httpx.Client(
        transport=_transport(
            {
                0: listing(
                    article(
                        job_id="14018",
                        title="Campus Hire Houston",
                    ),
                    article(
                        job_id="99999",
                        title="Gone",
                    ),
                )
            },
            job_pages={
                "99999": None,
            },
        ),
    )

    jobs = fetch_avature_jobs(
        source_account=BASE,
        company_name="Two Sigma",
        client=client,
        concurrency=2,
    )

    assert [
        job.external_id
        for job in jobs
    ] == [
        "14018",
    ]


def test_the_apply_link_is_the_employer_s_own_posting() -> None:
    """No exception needed here, unlike RippleMatch: an Avature portal
    is the company's own board, whatever domain it is served from."""

    client = httpx.Client(
        transport=_transport(
            {
                0: listing(
                    article(
                        job_id="14018",
                        title="Campus Hire Houston",
                    )
                )
            }
        ),
    )

    jobs = fetch_avature_jobs(
        source_account=BASE,
        company_name="Two Sigma",
        client=client,
    )

    assert jobs[0].official_url.startswith(
        "https://careers.twosigma.com/careers/JobDetail/"
    )
