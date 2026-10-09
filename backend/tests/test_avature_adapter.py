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
    parse_job_locations,
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


# --- a portal keyed on its listing page: EA's -------------------------


EA = "https://jobs.example-games.com/en_US/careers/SearchJobs"


def ea_article(
    *,
    job_id: str,
    title: str,
    location: str = "Redwood City, United States of America",
) -> str:
    """One row of a SearchJobs listing, shaped like EA's."""

    return (
        '<article class="article article--result article--non-toggle">'
        '<h3 class="article__header__text__title title title--04 ">'
        '<a class="link link_result" href="https://jobs.example-games.com'
        f'/en_US/careers/JobDetail/{title.replace(" ", "-")}/{job_id}">'
        f" {title} </a></h3>"
        '<div class="article__header__text__subtitle">'
        f'<span class="list-item-location">{location}</span> '
        f'<span class="list-item-id">Role ID {job_id}</span>'
        "</div></article>"
    )


def ea_listing(
    *articles: str,
) -> str:
    """A SearchJobs page, linking to the pages after it."""

    return listing(
        *articles,
        '<a href="SearchJobs?jobOffset=20">2</a>'
        '<a href="SearchJobs?jobOffset=40">3</a>',
    )


EA_JOB_PAGE = """<html><body>
<div class="article__content">
  <div class="article__content__view__field__value">
    <strong>Locations</strong>: Vancouver, British Columbia, Canada&nbsp;
    <ul class="MultipleDataSetFields"><li class="MultipleDataSetField">
    <span class="MultipleDataSetFieldLabel">Location:</span>
    <span class="MultipleDataSetFieldValue">Kirkland</span></li>
    <li class="MultipleDataSetField">
    <span class="MultipleDataSetFieldLabel">State:</span>
    <span class="MultipleDataSetFieldValue">Washington</span></li>
    <li class="MultipleDataSetField">
    <span class="MultipleDataSetFieldLabel">Country:</span>
    <span class="MultipleDataSetFieldValue">United States of America</span>
    </li></ul><br/><br>
  </div>
  <div class="article__content__view__field">
    <p>Build gameplay systems. 0-2 years of experience.</p>
  </div>
</div>
<footer>Share</footer>
</body></html>"""


def test_a_listing_page_portal_is_read_there_in_its_own_steps() -> None:
    asked: list[str] = []

    def handle(
        request: httpx.Request,
    ) -> httpx.Response:
        asked.append(
            str(request.url)
        )

        if "JobDetail" in request.url.path:
            return httpx.Response(
                200,
                text=EA_JOB_PAGE,
            )

        offset = int(
            request.url.params.get(
                "jobOffset",
                0,
            )
        )

        pages = {
            0: ea_listing(
                ea_article(
                    job_id="216200",
                    title="Software Engineer I",
                )
            ),
            20: ea_listing(
                ea_article(
                    job_id="216290",
                    title="Software Engineer II",
                )
            ),
        }

        return httpx.Response(
            200,
            text=pages.get(
                offset,
                ea_listing(),
            ),
        )

    jobs = fetch_avature_jobs(
        source_account=EA,
        company_name="Electronic Arts",
        client=httpx.Client(
            transport=httpx.MockTransport(
                handle,
            ),
        ),
        concurrency=1,
    )

    listings = [
        url
        for url in asked
        if "SearchJobs" in url
    ]

    assert listings == [
        EA,
        f"{EA}?jobOffset=20",
        f"{EA}?jobOffset=40",
    ]

    assert {
        job.external_id
        for job in jobs
    } == {
        "216200",
        "216290",
    }


def test_the_listing_location_is_read_from_a_searchjobs_row() -> None:
    rows = parse_listing(
        ea_listing(
            ea_article(
                job_id="216200",
                title="Software Engineer I",
                location="Hyderabad, India",
            )
        ),
        base_url=EA,
    )

    assert rows[0][3] == "Hyderabad, India"


def test_every_location_the_posting_names_is_kept() -> None:
    """The listing names one place; a Vancouver role open in Kirkland
    too is a US role."""

    assert parse_job_locations(
        EA_JOB_PAGE,
    ) == (
        "Vancouver, British Columbia, Canada; "
        "Kirkland, Washington, United States of America"
    )


def test_a_single_location_page_names_one_place() -> None:
    assert parse_job_locations(
        "<div><strong>Locations</strong>: Hyderabad, Telangana, "
        "India&nbsp; <br></div>"
    ) == "Hyderabad, Telangana, India"


def test_a_title_the_gate_rejects_is_never_read_in_full() -> None:
    read: list[str] = []

    def handle(
        request: httpx.Request,
    ) -> httpx.Response:
        if "JobDetail" in request.url.path:
            read.append(
                request.url.path
            )

            return httpx.Response(
                200,
                text=EA_JOB_PAGE,
            )

        if request.url.params.get(
            "jobOffset"
        ):
            return httpx.Response(
                200,
                text=listing(),
            )

        return httpx.Response(
            200,
            text=listing(
                ea_article(
                    job_id="1",
                    title="Art Director",
                ),
                ea_article(
                    job_id="2",
                    title="Software Engineer I",
                ),
            ),
        )

    jobs = fetch_avature_jobs(
        source_account=EA,
        company_name="Electronic Arts",
        client=httpx.Client(
            transport=httpx.MockTransport(
                handle,
            ),
        ),
        concurrency=1,
        should_fetch_detail=lambda title: "Software" in title,
    )

    assert [
        path.rsplit("/", 1)[-1]
        for path in read
    ] == [
        "2",
    ]

    by_id = {
        job.external_id: job
        for job in jobs
    }

    assert by_id["1"].description == ""

    assert by_id["1"].location == (
        "Redwood City, United States of America"
    )

    assert "Kirkland" in by_id["2"].location
