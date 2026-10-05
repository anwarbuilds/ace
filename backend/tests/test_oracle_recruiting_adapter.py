"""Oracle Recruiting Cloud, read directly.

Fifteen employers whose roles reached ACE only through a feed -- American
Express, JPMorgan Chase, Oracle, BNY, Dell, Honeywell, Fortinet among
them -- hire through Oracle Recruiting, whose pages render in the
browser and could not even be checked.
"""

from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.adapters.oracle_recruiting import (
    PAGE_SIZE,
    IncompleteOracleRead,
    build_location,
    fetch_oracle_recruiting_jobs,
    parse_source_account,
)
from backend.app.db.base import Base
from backend.app.intelligence.eligibility import (
    EligibilityReasonCode,
    EligibilityStatus,
    evaluate_job,
)
from backend.app.verification.employer_page import (
    ReadingStore,
)


HOST = "egug.fa.us2.oraclecloud.com"

ACCOUNT = f"{HOST}/CX_1"

NOW = datetime(
    2026,
    10,
    5,
    12,
    tzinfo=timezone.utc,
)

CLEARED = (
    "<p>Build mission software.</p><ul><li>Active TS/SCI security "
    "clearance is required.</li></ul>"
)


def requisition(
    requisition_id: str,
    *,
    title: str = "Software Engineer I",
    location: str = "Charlotte, NC, United States",
) -> dict:
    return {
        "Id": requisition_id,
        "Title": title,
        "PostedDate": "2026-10-04",
        "PrimaryLocation": location,
        "PrimaryLocationCountry": "US",
        "secondaryLocations": [],
    }


class Tenant:
    def __init__(
        self,
        requisitions: list[dict],
        *,
        details: dict[str, str] | None = None,
        total: int | None = None,
    ) -> None:
        self.requisitions = requisitions

        self.details = details or {}

        self.total = (
            total
            if total is not None
            else len(requisitions)
        )

        self.detail_calls: list[str] = []

        self.list_calls = 0

    def client(
        self,
    ) -> httpx.Client:
        def handler(
            request: httpx.Request,
        ) -> httpx.Response:
            finder = request.url.params["finder"]

            fields = dict(
                part.split("=", 1)
                for part in finder.split(";", 1)[1].split(",")
            )

            if request.url.path.endswith(
                "recruitingCEJobRequisitions"
            ):
                self.list_calls += 1

                offset = int(fields["offset"])

                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "TotalJobsCount": self.total,
                                "requisitionList": self.requisitions[
                                    offset:offset + PAGE_SIZE
                                ],
                            },
                        ],
                    },
                )

            requisition_id = fields["Id"].strip('"')

            self.detail_calls.append(
                requisition_id
            )

            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "ExternalDescriptionStr": self.details.get(
                                requisition_id,
                                "<p>Build software.</p>",
                            ),
                            "ExternalQualificationsStr": (
                                "<ul><li>BS in Computer Science</li></ul>"
                            ),
                        },
                    ],
                },
            )

        return httpx.Client(
            transport=httpx.MockTransport(
                handler
            )
        )


@pytest.fixture(name="store")
def fixture_store():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
    )

    Base.metadata.create_all(
        engine
    )

    return ReadingStore(
        sessionmaker(
            bind=engine,
            class_=Session,
            expire_on_commit=False,
        )
    )


def fetch(
    tenant: Tenant,
    store: ReadingStore,
    *,
    now: datetime = NOW,
    **kwargs,
):
    with tenant.client() as client:
        return fetch_oracle_recruiting_jobs(
            source_account=ACCOUNT,
            company_name="American Express",
            store=store,
            client=client,
            now=lambda: now,
            **kwargs,
        )


def test_the_account_names_host_and_site() -> None:
    assert parse_source_account(
        ACCOUNT
    ) == (HOST, "CX_1")

    with pytest.raises(ValueError):
        parse_source_account(
            HOST
        )


def test_every_page_is_read_and_each_posting_links_to_its_own_page(
    store,
) -> None:
    tenant = Tenant(
        [
            requisition(str(index))
            for index in range(PAGE_SIZE + 5)
        ]
    )

    jobs = fetch(
        tenant,
        store,
    )

    assert len(jobs) == PAGE_SIZE + 5

    assert tenant.list_calls == 2

    assert jobs[0].official_url == (
        f"https://{HOST}/hcmUI/CandidateExperience/en/sites/CX_1/job/0"
    )


def test_the_posting_is_judged_on_its_full_description(
    store,
) -> None:
    [job] = fetch(
        Tenant(
            [requisition("26013256")],
            details={"26013256": CLEARED},
        ),
        store,
    )

    assert "TS/SCI" in job.description

    decision = evaluate_job(
        job
    )

    assert decision.status == EligibilityStatus.REJECT

    assert (
        EligibilityReasonCode.CLEARANCE_BLOCKER
        in decision.reason_codes
    )


def test_descriptions_are_fetched_only_for_titles_that_could_pass(
    store,
) -> None:
    tenant = Tenant(
        [
            requisition("1", title="Software Engineer I"),
            requisition("2", title="Branch Manager"),
        ]
    )

    fetch(
        tenant,
        store,
        should_fetch_detail=lambda title: "Engineer" in title,
    )

    assert tenant.detail_calls == ["1"]


def test_a_description_is_fetched_once_a_week_not_every_poll(
    store,
) -> None:
    tenant = Tenant(
        [requisition("1")],
    )

    fetch(tenant, store)

    [job] = fetch(
        tenant,
        store,
        now=NOW + timedelta(hours=1),
    )

    assert tenant.detail_calls == ["1"]

    assert "Build software" in job.description

    fetch(
        tenant,
        store,
        now=NOW + timedelta(days=8),
    )

    assert tenant.detail_calls == ["1", "1"]


def test_fresh_descriptions_per_poll_are_bounded(
    store,
) -> None:
    tenant = Tenant(
        [requisition(str(index)) for index in range(5)]
    )

    jobs = fetch(
        tenant,
        store,
        fresh_details=2,
    )

    assert len(tenant.detail_calls) == 2

    # Every posting is still in the snapshot; the rest are described on
    # later polls.
    assert len(jobs) == 5


def test_a_tenant_too_large_to_finish_is_refused_not_cut(
    store,
) -> None:
    with pytest.raises(
        IncompleteOracleRead,
    ):
        fetch(
            Tenant(
                [requisition(str(index)) for index in range(PAGE_SIZE * 4)],
            ),
            store,
            max_pages=2,
        )


def test_every_location_is_kept() -> None:
    assert build_location(
        {
            "PrimaryLocation": "Charlotte, NC, United States",
            "secondaryLocations": [
                {"Name": "Gurugram, HR, India"},
                {"Name": "Charlotte, NC, United States"},
            ],
        }
    ) == "Charlotte, NC, United States; Gurugram, HR, India"
