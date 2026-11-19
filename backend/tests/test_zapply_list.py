"""Zapply's public new grad list, read as pointers (DIS-12, 2026-11-18).

A row becomes a copy where its employer's posting can be spelled exactly
and ACE does not read that board directly, or, where it cannot be spelled
(Workday among others), linked by zapply's own link until ACE holds that
posting open from the employer; ACE never opens a zapply link itself; the
list's visa column is never read; a copy is a list copy in every count.
Every company, board and posting here is fictional.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.adapters.zapply import (
    LIST_URLS,
    PLACEHOLDER,
    POINTER,
    REPOSITORY,
    employer_link,
    fetch_zapply_jobs,
    is_zapply_link,
    parse_rows,
    posted_from,
    posting_id,
    workday_posting,
    workday_requisitions,
)
from backend.app.adapters.http_cache import CacheValidators
from backend.app.coverage.companies import MULTI_EMPLOYER_SOURCES
from backend.app.coverage.held_out import READING_LISTS
from backend.app.coverage.host_policy import read_targets
from backend.app.coverage.recall import FEED_SOURCES
from backend.app.db.models import Base, JobRecord, JobSourceRecord
from backend.app.intelligence.eligibility import has_verifiable_requirements
from backend.app.scheduling import dispatcher as dispatcher_module
from backend.app.scheduling.dispatcher import ZapplySourceFetcher
from backend.app.scheduling.types import SourceDefinition, SourceType


NOW = datetime(2026, 11, 18, 22, 30, tzinfo=timezone.utc)
UUID = "5b5e7e6d-d59e-410b-9a7f-619717c3c942"

README = f"""
# Software Engineering Jobs 2027

<details>
<summary><h3>Software Engineering</h3></summary>

| Company | Role | Location | Posted | Visa | **Apply** |
|---------|------|----------|--------|------|----------|
| **Fabrikam** | Software Engineer, New Grad | Seattle, WA | 16m | ✅ Sponsor | [<img src="images/apply.png" width="80" alt="Apply">](https://zapply.jobs/l/d/greenhouse-fabrikam-4001234?s=gh) |
| **Contoso Labs** | Backend Engineer I | Remote, US | 2d |  | [<img src="images/apply.png" width="80" alt="Apply">](https://zapply.jobs/l/d/ashby-contoso-labs-{UUID}?s=gh) |
| **Northwind** | Software Developer (New or Recent Graduate) | Chicago, IL | 3h | ✅ Sponsor | [<img src="images/apply.png" width="80" alt="Apply">](https://zapply.jobs/l/d/workday-northwind-external-R-1234?s=gh-new-grad) |
| **Tailspin** | Associate Software Engineer | Austin, TX | 2w |  | [<img src="images/apply.png" width="80" alt="Apply">](https://zapply.jobs/l/d/workable-tailspin-94444F7056?s=gh) |
| **Fabrikam** | Software Engineer, New Grad | Seattle, WA | 16m | ✅ Sponsor | [<img src="images/apply.png" width="80" alt="Apply">](https://zapply.jobs/l/d/greenhouse-fabrikam-4001234?s=gh) |

</details>
"""


def test_each_row_gives_company_role_place_day_and_link_code_once() -> None:
    rows = parse_rows(README, now=NOW)

    assert [row.code for row in rows] == [
        "greenhouse-fabrikam-4001234",
        f"ashby-contoso-labs-{UUID}",
        "workday-northwind-external-R-1234",
        "workable-tailspin-94444F7056",
    ]
    assert rows[2].link == "https://zapply.jobs/l/d/workday-northwind-external-R-1234?s=gh-new-grad"
    first = rows[0]
    assert (first.company, first.title, first.location) == ("Fabrikam", "Software Engineer, New Grad", "Seattle, WA")
    assert first.posted_at == datetime(2026, 11, 18, tzinfo=timezone.utc)


def test_a_posted_day_is_a_day_that_does_not_move_between_reads() -> None:
    assert posted_from("16m", now=NOW) == datetime(2026, 11, 18, tzinfo=timezone.utc)
    assert posted_from("16m", now=NOW.replace(minute=45)) == posted_from("16m", now=NOW)
    assert posted_from("2d", now=NOW) == datetime(2026, 11, 16, tzinfo=timezone.utc)
    assert posted_from("2026-09-18", now=NOW) == datetime(2026, 9, 18, tzinfo=timezone.utc)
    # Too rough to name a day.
    assert posted_from("2w", now=NOW) is None
    assert posted_from("1mo", now=NOW) is None
    assert posted_from("Date unknown", now=NOW) is None


def test_a_link_code_spells_the_employers_own_posting_where_it_can_exactly() -> None:
    assert employer_link("greenhouse-fabrikam-4001234") == "https://job-boards.greenhouse.io/fabrikam/jobs/4001234"
    assert employer_link(f"ashby-contoso-labs-{UUID}") == f"https://jobs.ashbyhq.com/contoso-labs/{UUID}"
    assert employer_link(f"lever-tailspin-{UUID}") == f"https://jobs.lever.co/tailspin/{UUID}"
    assert employer_link("sr-Fabrikam1-744000162353069") == "https://jobs.smartrecruiters.com/Fabrikam1/744000162353069"
    assert employer_link("workable-tailspin-94444f7056") == "https://apply.workable.com/tailspin/j/94444F7056/"
    # Workday's links name no data centre; others name no host ACE can spell.
    assert employer_link("workday-northwind-external-R1234") is None
    assert employer_link("phenom-northwind-1234BR") is None
    assert employer_link("greenhouse-4001234") is None


def respond(log: list[dict], *, status: int = 200):
    def handle(request: httpx.Request) -> httpx.Response:
        log.append({"url": str(request.url), "if_none_match": request.headers.get("If-None-Match")})
        if status == 304:
            return httpx.Response(304, request=request)
        return httpx.Response(200, text=README, headers={"ETag": '"v1"'}, request=request)

    return httpx.MockTransport(handle)


def test_a_copy_is_kept_only_where_ace_does_not_read_the_board_and_never_says_sponsor() -> None:
    log: list[dict] = []

    jobs, unchanged, validators = fetch_zapply_jobs(
        source_account="new-grad-swe",
        client=httpx.Client(transport=respond(log)),
        read_directly=lambda link: "/fabrikam/" in link,
        now=NOW,
    )

    assert unchanged is False
    assert log[0]["url"] == LIST_URLS["new-grad-swe"]
    assert "raw.githubusercontent.com" in log[0]["url"]
    assert [job.official_url for job in jobs] == [
        f"https://jobs.ashbyhq.com/contoso-labs/{UUID}",
        "https://zapply.jobs/l/d/workday-northwind-external-R-1234?s=gh-new-grad",
        "https://apply.workable.com/tailspin/j/94444F7056/",
    ]
    assert all(job.source == "zapply" for job in jobs)
    assert all("ponsor" not in job.description and job.description in (PLACEHOLDER, POINTER) for job in jobs)
    assert REPOSITORY in PLACEHOLDER and REPOSITORY in POINTER
    assert validators.etag == '"v1"'


def test_an_unchanged_list_costs_one_answer_and_changes_nothing() -> None:
    log: list[dict] = []

    jobs, unchanged, _validators = fetch_zapply_jobs(
        source_account="new-grad-swe",
        client=httpx.Client(transport=respond(log, status=304)),
        validators=CacheValidators(etag='"v1"'),
        now=NOW,
    )

    assert (jobs, unchanged) == ([], True)
    assert log[0]["if_none_match"] == '"v1"'


def test_the_dispatcher_reads_the_list_and_checks_copies_on_the_employers_page() -> None:
    checked: list[int] = []

    def fetcher(**kwargs):
        return (
            [
                job
                for job in fetch_zapply_jobs(
                    source_account=kwargs["source_account"],
                    client=httpx.Client(transport=respond([])),
                    read_directly=kwargs["read_directly"],
                    now=NOW,
                )[0]
            ],
            False,
            CacheValidators(etag='"v2"'),
        )

    def verifier(jobs):
        checked.append(len(jobs))
        return list(jobs)

    source = SourceDefinition(
        source_type=SourceType.ZAPPLY,
        source_account="new-grad-swe",
        company_name="Zapply",
        enabled=True,
        poll_interval_seconds=900,
    )

    snapshot = ZapplySourceFetcher(
        fetcher=fetcher,
        verifier=verifier,
        read_directly_factory=lambda: (lambda _link: False),
    )(source)

    # Only employer links reach the page check; zapply's own link never does.
    assert checked == [3]
    assert snapshot.etag == '"v2"'
    assert len(snapshot.jobs) == 4
    assert sum(is_zapply_link(job.official_url) for job in snapshot.jobs) == 1


def test_a_zapply_copy_is_a_list_copy_in_every_count() -> None:
    assert "zapply" in MULTI_EMPLOYER_SOURCES
    assert "zapply" in FEED_SOURCES
    assert "zapply" in READING_LISTS


def test_the_list_is_read_from_githubs_raw_file_host_under_its_robots_verdict() -> None:
    [target] = read_targets("zapply", "new-grad-swe", None)

    assert target.host == "raw.githubusercontent.com"
    assert target.paths == ("/zapplyjobs/New-Grad-Software-Engineering-Positions/main/README.md",)


# A row ACE cannot spell (Workday among others) is linked by zapply's own link.


def test_a_row_ace_cannot_spell_is_a_copy_by_zapplys_link_with_unverified_requirements() -> None:
    jobs, _unchanged, _validators = fetch_zapply_jobs(
        source_account="new-grad-swe",
        client=httpx.Client(transport=respond([])),
        now=NOW,
    )

    [pointer] = [job for job in jobs if is_zapply_link(job.official_url)]

    assert pointer.company == "Northwind"
    assert pointer.external_id == "workday-northwind-external-R-1234"
    assert pointer.description == POINTER
    # Short of the gate's minimum on purpose: the requirements say unverified.
    assert has_verifiable_requirements(pointer) is False


def test_a_row_ace_holds_open_from_the_employer_gives_no_copy() -> None:
    asked: list[list[str]] = []

    def held(rows):
        asked.append([row.code for row in rows])
        return {"workday-northwind-external-R-1234"}

    jobs, _unchanged, _validators = fetch_zapply_jobs(
        source_account="new-grad-swe",
        client=httpx.Client(transport=respond([])),
        held=held,
        now=NOW,
    )

    # Only rows ACE cannot spell are asked about.
    assert asked == [["workday-northwind-external-R-1234"]]
    assert not any(is_zapply_link(job.official_url) for job in jobs)


def test_only_zapplys_own_host_is_its_link() -> None:
    assert is_zapply_link("https://zapply.jobs/l/d/workday-northwind-external-R-1234?s=gh") is True
    assert is_zapply_link("https://app.zapply.jobs/onboarding/") is True
    assert is_zapply_link("https://notzapply.jobs/l/d/x") is False
    assert is_zapply_link("https://job-boards.greenhouse.io/fabrikam/jobs/4001234") is False


def test_the_page_check_never_opens_a_zapply_link() -> None:
    job = fetch_zapply_jobs(
        source_account="new-grad-swe",
        client=httpx.Client(transport=respond([])),
        now=NOW,
    )[0]
    pointer = next(item for item in job if is_zapply_link(item.official_url))

    assert dispatcher_module._employer_page_worth_reading(pointer) is False


def test_a_workday_code_is_read_against_the_boards_ace_holds() -> None:
    boards = ["northwind/External", "northwind/External_Careers", "fabrikam_one/Fabrikam_Jobs"]

    assert workday_posting("workday-northwind-external-R-1234", boards) == ("northwind/External", "r-1234")
    assert workday_posting("workday-northwind-external-careers-JR2026001", boards) == (
        "northwind/External_Careers",
        "jr2026001",
    )
    assert workday_posting("workday-fabrikam-one-fabrikam-jobs-R77", boards) == ("fabrikam_one/Fabrikam_Jobs", "r77")
    assert workday_posting("workday-tailspin-careers-R1", boards) is None
    assert workday_posting("greenhouse-northwind-4001", boards) is None


def test_a_held_workday_posting_gives_its_requisition_however_it_is_written() -> None:
    assert workday_requisitions("/job/Seattle-WA/Software-Engineer_JR2026001") == {"jr2026001"}
    assert "r-1234" in workday_requisitions("/job/Chicago-IL/Software-Developer_R-1234")
    assert "jr55" in workday_requisitions("/job/Austin-TX/Engineer_JR55-1")
    assert workday_requisitions("/job/Austin-TX/no-requisition") == set()


def test_an_identifier_row_names_the_ace_sources_that_hold_it() -> None:
    assert posting_id("apple-200600001") == (("apple",), "200600001")
    assert posting_id("oracle-fabrikam-financial-261001") == (("oracle_recruiting",), "261001")
    assert posting_id("eightfold-northwind-44100001") == (("eightfold", "eightfold_pcsx"), "44100001")
    assert posting_id("phenom-northwind-1234BR") is None
    assert posting_id("bamboohr-tailspin-96") is None


@pytest.fixture(name="sessions")
def fixture_sessions(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session)
    monkeypatch.setattr("backend.app.db.session.SessionLocal", factory)
    return factory


def stored(session: Session, source: str, account: str, external_id: str, *, active: bool = True) -> None:
    session.add(
        JobRecord(
            source=source,
            source_account=account,
            company="Northwind",
            external_id=external_id,
            title="Software Developer",
            location="Chicago, IL",
            description="",
            official_url=f"https://example.invalid/{source}/{external_id}",
            content_hash="x",
            is_active=active,
        )
    )


def test_ace_knows_which_rows_it_holds_open_from_the_employer(sessions) -> None:
    with sessions() as session:
        session.add(
            JobSourceRecord(
                source_type="workday",
                source_account="northwind/External",
                company_name="Northwind",
                enabled=True,
                poll_interval_seconds=900,
            )
        )
        stored(session, "workday", "northwind/External", "/job/Chicago-IL/Software-Developer_R-1234")
        stored(session, "workday", "northwind/External", "/job/Chicago-IL/Software-Developer_R-5678", active=False)
        stored(session, "apple", "apple", "200600001")
        session.commit()

    rows = [
        row._replace(code=code)
        for row, code in zip(
            parse_rows(README, now=NOW)[:4],
            [
                "workday-northwind-external-R-1234",
                "workday-northwind-external-R-5678",
                "apple-200600001",
                "workday-tailspin-careers-R1",
            ],
        )
    ]

    assert dispatcher_module._held_by_employer(rows) == {
        "workday-northwind-external-R-1234",
        "apple-200600001",
    }
