"""Reading Workday by each career site's own sitemap (2026-11-18).

From 2026-11-16 Workday refused nearly every automated request to its job
API, while the sitemap its robots.txt names for each career site, and the
posting pages it lists, kept answering. These tests hold that reading: the
sitemap's postings, what a page says of itself, a held posting handed back
unchanged, the job API resting after a refusal, separate paces, Workday's
pause holding every reader, and list copies kept for a board ACE has not
read lately. Every company, board and posting here is fictional.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.adapters.workday import (
    ApiRest,
    SITEMAP_LIMIT,
    StoredDetail,
    WorkdayPace,
    fetch_workday_jobs,
    read_posting_page,
    sitemap_paths,
    slug_title,
)
from backend.app.db.base import Base
from backend.app.db.models import JobSourceRecord, SourceState
from backend.app.discovery.feed_links import is_transient
from backend.app.persistence.hashing import compute_job_content_hash
from backend.app.models.job import CanonicalJob
from backend.app.scheduling import dispatcher as dispatcher_module
from backend.app.scheduling.dispatcher import WorkdaySourceFetcher
from backend.app.scheduling.holds import PlatformHeld, PlatformHold
from backend.app.scheduling.registry import SourceRegistry
from backend.app.scheduling.runtime import SchedulerRuntime
from backend.app.scheduling.types import SourceDefinition, SourceType
from backend.app.verification.employer_page import EmployerPageVerifier


HOST = "fabrikam.wd5.myworkdayjobs.example"
SITE = "Fabrikam_Careers"
ACCOUNT = f"fabrikam/{SITE}"
REFERENCE = datetime(2026, 11, 18, 20, 0, tzinfo=timezone.utc)

HELD = "/job/US-Remote/Platform-Engineer_R1001"
NEW_PASSING = "/job/US-Seattle-WA/Software-Engineer--New-Grad-_R1002"
NEW_OTHER = "/job/US-Denver-CO/Payroll-Specialist_R1003"


class Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class CountingPace:
    """A pace that never waits and remembers what it heard."""

    def __init__(self) -> None:
        self.waits = 0
        self.statuses: list[int] = []

    def wait(self) -> None:
        self.waits += 1

    def note(self, status: int) -> None:
        self.statuses.append(status)


def sitemap(paths, *, host: str = HOST, site: str = SITE) -> str:
    entries = "".join(
        f"<url><loc>https://{host}/{site}{path}</loc>"
        f'<xhtml:link rel="alternate" hreflang="en-US" href="https://{host}/en-US/{site}{path}"/></url>'
        for path in paths
    )
    return (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/TR/xhtml11/xhtml11_schema.html">'
        f"{entries}</urlset>"
    )


def page(title: str, requisition: str, *, locality: str = "Seattle, WA", posted: str = "2026-11-18") -> str:
    posting = {
        "@type": "JobPosting",
        "title": title,
        "identifier": {"@type": "PropertyValue", "name": title, "value": requisition},
        "datePosted": posted,
        "employmentType": "FULL_TIME",
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": locality,
                "addressCountry": "United States of America",
            },
        },
        "description": "Build and run the services behind Fabrikam's storefront. " * 8,
    }
    return (
        "<html><head><script type=\"application/ld+json\">"
        f"{json.dumps(posting)}</script></head><body></body></html>"
    )


def stored_held() -> dict[str, StoredDetail]:
    return {
        HELD: StoredDetail(
            description="Run Fabrikam's platform. " * 20,
            location="US, Remote",
            posted_at=datetime(2026, 11, 10, tzinfo=timezone.utc),
            requisition_id="R1001",
            official_url=f"https://{HOST}/{SITE}{HELD}",
            title="Platform Engineer",
        ),
    }


def transport(log: list[str], *, api_status: int = 200, sitemap_status: int = 200, page_status: int = 200, paths=None):
    paths = paths if paths is not None else [HELD, NEW_PASSING, NEW_OTHER]

    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        log.append(f"{request.method} {path}")
        if path.startswith("/wday/cxs/"):
            if api_status != 200:
                return httpx.Response(api_status, request=request)
            if path.endswith("/jobs"):
                return httpx.Response(
                    200,
                    json={
                        "total": 1,
                        "jobPostings": [
                            {"title": "Platform Engineer", "externalPath": HELD, "locationsText": "US, Remote", "postedOn": "Posted 8 Days Ago"},
                        ],
                    },
                    request=request,
                )
            return httpx.Response(404, request=request)
        if path == f"/{SITE}/siteMap.xml":
            if sitemap_status != 200:
                return httpx.Response(sitemap_status, request=request)
            return httpx.Response(200, text=sitemap(paths), request=request)
        if path.startswith(f"/{SITE}/job/"):
            if page_status != 200:
                return httpx.Response(page_status, request=request)
            if path.endswith("_R1002"):
                return httpx.Response(200, text=page("Software Engineer (New Grad)", "R1002"), request=request)
            if path.endswith("_R1001"):
                return httpx.Response(200, text=page("Platform Engineer", "R1001", locality="Remote - USA"), request=request)
            return httpx.Response(200, text="<html></html>", request=request)
        return httpx.Response(404, request=request)

    return httpx.MockTransport(handle)


def read(log, *, quick=True, api_rest=None, known=None, pace=None, page_pace=None, **kwargs):
    return fetch_workday_jobs(
        source_account=ACCOUNT,
        company_name="Fabrikam",
        source_host=HOST,
        should_fetch_detail=lambda title: "engineer" in title.lower(),
        client=httpx.Client(transport=transport(log, **kwargs)),
        now=REFERENCE,
        known_details=stored_held() if known is None else known,
        quick=quick,
        crawl=True,
        pace=pace,
        page_pace=page_pace,
        api_rest=api_rest,
    )


# The sitemap and the page.


def test_a_sitemap_gives_each_postings_path_in_its_order_once() -> None:
    markup = sitemap([NEW_PASSING, HELD, NEW_PASSING]) + (
        f"<url><loc>https://other.wd1.myworkdayjobs.example/{SITE}/job/X/Y_R9</loc></url>"
        f"<url><loc>https://{HOST}/Other_Site/job/X/Y_R8</loc></url>"
    )

    assert sitemap_paths(markup, host=HOST, site=SITE) == [NEW_PASSING, HELD]


def test_a_sitemap_matches_the_site_whatever_its_capitals() -> None:
    markup = sitemap([HELD], site="fabrikam_careers")

    assert sitemap_paths(markup, host=HOST, site=SITE) == [HELD]


def test_a_title_is_spelled_from_the_link_until_the_page_is_read() -> None:
    assert slug_title(NEW_PASSING) == "Software Engineer New Grad"
    assert slug_title("/job/Remote---USA/Director--Product---Industry-Marketing_R0006042") == (
        "Director Product Industry Marketing"
    )
    assert slug_title("/job/Montreal/Dveloppeur-web--Front-end_R-100000287") == "Dveloppeur web Front end"


def test_a_posting_page_describes_itself_with_its_job_posting() -> None:
    found = read_posting_page(page("Analyst, Risk &amp; Claims", "JR77", locality="Remote - USA"))

    assert found is not None
    assert found.title == "Analyst, Risk & Claims"
    assert found.requisition_id == "JR77"
    assert found.location == "Remote - USA, United States of America"
    assert found.posted_at == datetime(2026, 11, 18, tzinfo=timezone.utc)
    assert len(found.description) > 200


def test_a_page_without_a_job_posting_is_not_a_posting() -> None:
    assert read_posting_page("<html><body>Search for jobs</body></html>") is None


# A quick read by the sitemap.


def test_a_quick_read_goes_by_the_sitemap_and_never_asks_the_job_api() -> None:
    log: list[str] = []

    jobs = read(log)

    assert not any(line.startswith("POST /wday/cxs/") for line in log)
    assert log[0] == f"GET /{SITE}/siteMap.xml"
    # Only the new posting whose title could pass costs a page.
    assert log[1:] == [f"GET /{SITE}{NEW_PASSING}"]
    assert jobs.complete is False
    assert [job.external_id for job in jobs] == [HELD, NEW_PASSING, NEW_OTHER]


def test_a_held_posting_comes_back_exactly_as_ace_holds_it() -> None:
    log: list[str] = []

    jobs = read(log)
    held = next(job for job in jobs if job.external_id == HELD)
    kept = stored_held()[HELD]
    expected = CanonicalJob(
        source="workday",
        company="Fabrikam",
        external_id=HELD,
        requisition_id=kept.requisition_id,
        title=kept.title,
        location=kept.location,
        description=kept.description,
        official_url=kept.official_url,
        posted_at=kept.posted_at,
    )

    assert compute_job_content_hash(held) == compute_job_content_hash(expected)


def test_a_new_posting_takes_its_pages_title_description_place_and_day() -> None:
    log: list[str] = []

    new = next(job for job in read(log) if job.external_id == NEW_PASSING)

    assert new.title == "Software Engineer (New Grad)"
    assert new.requisition_id == "R1002"
    assert new.location == "Seattle, WA, United States of America"
    assert new.posted_at == datetime(2026, 11, 18, tzinfo=timezone.utc)
    assert new.official_url == f"https://{HOST}/{SITE}{NEW_PASSING}"
    assert len(new.description) > 200


def test_a_new_posting_the_gate_rejects_on_its_title_is_kept_shallow() -> None:
    log: list[str] = []

    other = next(job for job in read(log) if job.external_id == NEW_OTHER)

    assert other.title == "Payroll Specialist"
    assert other.description == ""
    assert other.location == "US Denver CO"
    assert not any(line.endswith("_R1003") for line in log)


def test_a_refused_page_stops_page_reads_and_the_stored_text_stands() -> None:
    log: list[str] = []
    second_new = "/job/US-Austin-TX/Backend-Engineer_R1004"

    jobs = read(log, page_status=429, paths=[HELD, NEW_PASSING, second_new])

    page_reads = [line for line in log if "/job/" in line]
    assert len(page_reads) == 1
    assert {job.external_id for job in jobs} == {HELD, NEW_PASSING, second_new}
    held = next(job for job in jobs if job.external_id == HELD)
    assert held.description == stored_held()[HELD].description


def test_a_refused_sitemap_is_the_reads_own_refusal_and_rests_nothing() -> None:
    log: list[str] = []
    rest = ApiRest(clock=Clock())

    with pytest.raises(httpx.HTTPStatusError) as refused:
        read(log, sitemap_status=429, api_rest=rest)

    assert refused.value.response.status_code == 429
    assert rest.resting() is False


def test_a_sitemap_holds_at_most_a_hundred_postings() -> None:
    assert SITEMAP_LIMIT == 100


# A full read, and the job API's rest.


def test_a_full_read_asks_the_job_api_while_it_answers() -> None:
    log: list[str] = []
    rest = ApiRest(clock=Clock())

    jobs = read(log, quick=False, api_rest=rest)

    assert log[0] == f"POST /wday/cxs/fabrikam/{SITE}/jobs"
    assert not any("siteMap.xml" in line for line in log)
    assert jobs.complete is True


def test_a_refused_job_api_rests_and_the_read_goes_by_the_sitemap() -> None:
    log: list[str] = []
    clock = Clock()
    rest = ApiRest(clock=clock)

    jobs = read(log, quick=False, api_rest=rest, api_status=429)

    assert log[0] == f"POST /wday/cxs/fabrikam/{SITE}/jobs"
    assert log[1] == f"GET /{SITE}/siteMap.xml"
    assert jobs.complete is False
    assert rest.resting() is True

    # While it rests, a full read does not ask it at all.
    log.clear()
    read(log, quick=False, api_rest=rest, api_status=429)
    assert not any(line.startswith("POST") for line in log)

    # Once the rest is over it is asked once more; an answer ends the rest.
    clock.now += 31 * 60
    log.clear()
    jobs = read(log, quick=False, api_rest=rest)
    assert log[0].startswith("POST /wday/cxs/")
    assert jobs.complete is True
    assert rest.resting() is False


def test_the_rest_doubles_while_the_api_keeps_refusing_up_to_six_hours() -> None:
    clock = Clock()
    rest = ApiRest(clock=clock)
    rests = []

    for _ in range(6):
        rests.append(rest.refused())
        clock.now += rests[-1]

    assert rests == [1800, 3600, 7200, 14400, 21600, 21600]


def test_boards_refused_together_start_one_rest() -> None:
    clock = Clock()
    rest = ApiRest(clock=clock)

    first = rest.refused()
    clock.now += 5
    second = rest.refused()

    assert first == 1800
    assert second == 1795
    clock.now += 1800
    assert rest.refused() == 3600


def test_without_crawling_a_refusal_is_the_reads_own_as_before() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request)

    with pytest.raises(httpx.HTTPStatusError):
        fetch_workday_jobs(
            source_account=ACCOUNT,
            company_name="Fabrikam",
            source_host=HOST,
            client=httpx.Client(transport=httpx.MockTransport(handle)),
            now=REFERENCE,
        )


def test_sitemap_and_page_requests_wait_on_their_own_pace() -> None:
    log: list[str] = []
    api = CountingPace()
    pages = CountingPace()
    rest = ApiRest(clock=Clock())

    read(log, quick=False, api_rest=rest, api_status=429, pace=api, page_pace=pages)

    assert api.statuses == [429]
    # The sitemap, then the one new posting worth a page.
    assert pages.statuses == [200, 200]
    assert pages.waits == 2


def test_the_two_paces_climb_and_fall_on_their_own() -> None:
    api = WorkdayPace(start=6.0, sleep=lambda _s: None)
    pages = WorkdayPace(start=6.0, sleep=lambda _s: None)

    api.note(429)
    for _ in range(WorkdayPace.RAISE_AFTER):
        pages.note(200)

    assert api.per_minute == 3.0
    assert pages.per_minute == 7.5


# Workday's pause holds every reader.


def workday_source() -> SourceDefinition:
    return SourceDefinition(
        source_type=SourceType.WORKDAY,
        source_account=ACCOUNT,
        source_host=HOST,
        company_name="Fabrikam",
        enabled=True,
        poll_interval_seconds=900,
    )


def test_a_paused_workday_is_not_read_by_a_sweep_and_the_board_is_put_off() -> None:
    hold = PlatformHold(clock=Clock())
    hold.hold(600)
    calls: list[str] = []

    def fetcher(**kwargs):
        calls.append(kwargs["source_account"])
        return []

    with pytest.raises(PlatformHeld) as held:
        WorkdaySourceFetcher(fetcher=fetcher, hold=hold)(workday_source())

    assert calls == []
    assert is_transient(held.value) is True


def test_a_hold_ends_when_the_pause_does() -> None:
    clock = Clock()
    hold = PlatformHold(clock=clock)

    hold.hold(600)
    clock.now += 601

    assert hold.held() is False


def test_the_schedulers_pause_holds_workday_for_every_reader() -> None:
    clock = Clock()
    hold = PlatformHold(clock=clock)
    sources = [
        SourceDefinition(
            source_type=SourceType.WORKDAY,
            source_account=f"tenant{number}/External",
            source_host=f"tenant{number}.wd5.myworkdayjobs.example",
            company_name=f"Tenant {number}",
            enabled=True,
            poll_interval_seconds=900,
        )
        for number in range(4)
    ]

    def poller(_source):
        request = httpx.Request("POST", f"https://{HOST}/wday/cxs/x/y/jobs")
        raise httpx.HTTPStatusError("429", request=request, response=httpx.Response(429, request=request))

    runtime = SchedulerRuntime(
        registry=SourceRegistry(tuple(sources)),
        poller=poller,
        clock=clock,
        sleeper=lambda _seconds: None,
        holds={"workday": hold},
    )

    runtime.run_due_sources()

    assert hold.held() is True


# The employer-page check paces and holds Workday pages.


def test_the_employer_page_check_paces_workday_pages_and_skips_them_while_paused(monkeypatch) -> None:
    url = "https://fabrikam.wd5.myworkdayjobs.com/Fabrikam_Careers/job/US-Seattle-WA/Software-Engineer_R1002"
    requested: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /Fabrikam_Careers/\n", request=request)
        return httpx.Response(200, text=page("Software Engineer", "R1002"), request=request)

    pace = CountingPace()
    paused = {"now": True}

    class Store:
        def __init__(self, *_args) -> None:
            pass

        def load(self, _urls):
            return {}

        def save(self, *_args, **_kwargs) -> None:
            return None

    class NoCopies:
        def load(self, _keys):
            return {}

    monkeypatch.setattr("backend.app.verification.employer_page.ReadingStore", Store)

    verifier = EmployerPageVerifier(
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handle)),
        direct_copies=NoCopies(),
        paced=lambda link: pace if "myworkdayjobs.com" in link else None,
        held=lambda link: paused["now"] and "myworkdayjobs.com" in link,
    )
    job = CanonicalJob(
        source="simplify",
        company="Fabrikam",
        external_id="fabrikam-1",
        title="Software Engineer",
        location="Seattle, WA",
        official_url=url,
    )

    verifier([job])
    assert requested == []

    paused["now"] = False
    verified = verifier([job])

    assert requested[-1] == url
    assert pace.statuses == [200, 200]
    assert "storefront" in verified[0].description


# A list's copy stays while ACE has not read the board lately.


@pytest.fixture(name="sessions")
def fixture_sessions(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session)
    monkeypatch.setattr("backend.app.db.session.SessionLocal", factory)
    return factory


def add_board(session: Session, source_type: str, account: str, read_at: datetime | None) -> None:
    session.add(
        JobSourceRecord(
            source_type=source_type,
            source_account=account,
            company_name=account,
            enabled=True,
            poll_interval_seconds=900,
        )
    )
    if read_at is not None:
        session.add(
            SourceState(
                source=source_type,
                source_account=account,
                initialized_at=read_at,
                last_success_at=read_at,
                last_job_count=3,
            )
        )
    session.flush()


def test_a_board_ace_has_not_read_for_six_hours_does_not_hide_a_lists_copy(sessions) -> None:
    now = datetime(2026, 11, 18, 20, 0, tzinfo=timezone.utc)
    with sessions() as session:
        add_board(session, "greenhouse", "fabrikamfresh", now - timedelta(minutes=20))
        add_board(session, "workday", "fabrikam/Fabrikam_Careers", now - timedelta(hours=30))
        add_board(session, "greenhouse", "fabrikamnew", None)
        session.commit()

    read_directly = dispatcher_module._registered_board_check(now=lambda: now)

    assert read_directly("https://job-boards.greenhouse.io/fabrikamfresh/jobs/4001") is True
    assert read_directly(
        "https://fabrikam.wd5.myworkdayjobs.com/Fabrikam_Careers/job/US-Seattle-WA/Software-Engineer_R1002"
    ) is False
    assert read_directly("https://job-boards.greenhouse.io/fabrikamnew/jobs/4002") is False


def test_a_site_with_no_sitemap_at_its_address_is_read_by_the_job_api() -> None:
    log: list[str] = []
    rest = ApiRest(clock=Clock())

    jobs = read(log, sitemap_status=404, api_rest=rest)

    assert log[0] == f"GET /{SITE}/siteMap.xml"
    assert log[1] == f"POST /wday/cxs/fabrikam/{SITE}/jobs"
    assert [job.external_id for job in jobs] == [HELD]


def test_a_missing_sitemap_while_the_api_rests_is_the_reads_own_failure() -> None:
    log: list[str] = []
    rest = ApiRest(clock=Clock())
    rest.refused()

    with pytest.raises(httpx.HTTPStatusError):
        read(log, sitemap_status=404, api_rest=rest)

    assert not any(line.startswith("POST") for line in log)
