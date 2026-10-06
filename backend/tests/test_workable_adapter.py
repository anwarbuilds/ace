"""Workable boards, read directly.

65 employers on Workable reached ACE only through a feed with no
description; Avalore's "SECRET Security Clearance Required" passed
unread.
"""

from __future__ import annotations

import json
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
from sqlalchemy.pool import StaticPool

import backend.app.db.models  # noqa: F401  (tables for the store)
from backend.app.adapters.workable import (
    IncompleteWorkableRead,
    build_location,
    fetch_workable_jobs,
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


NOW = datetime(
    2026,
    10,
    6,
    tzinfo=timezone.utc,
)

ARLINGTON = {
    "country": "United States",
    "countryCode": "US",
    "city": "Arlington",
    "region": "Virginia",
}


def posting(
    shortcode: str,
    *,
    title: str = "Software Engineer",
    kind: str = "full",
) -> dict:
    return {
        "shortcode": shortcode,
        "title": title,
        "location": ARLINGTON,
        "locations": [dict(ARLINGTON, hidden=False)],
        "published": "2026-10-05T00:00:00.000Z",
        "type": kind,
    }


class Board:
    def __init__(
        self,
        postings: list[dict],
        *,
        requirements: dict[str, str] | None = None,
        page_size: int = 10,
    ) -> None:
        self.postings = postings

        self.requirements = requirements or {}

        self.page_size = page_size

        self.list_calls = 0

        self.detail_calls: list[str] = []

    def client(
        self,
    ) -> httpx.Client:
        def handler(
            request: httpx.Request,
        ) -> httpx.Response:
            if request.method == "POST":
                self.list_calls += 1

                body = json.loads(
                    request.content
                )

                start = int(body.get("token") or 0)

                end = start + self.page_size

                return httpx.Response(
                    200,
                    json={
                        "total": len(self.postings),
                        "results": self.postings[start:end],
                        **(
                            {"nextPage": str(end)}
                            if end < len(self.postings)
                            else {}
                        ),
                    },
                )

            shortcode = request.url.path.rstrip("/").rsplit("/", 1)[-1]

            self.detail_calls.append(
                shortcode
            )

            return httpx.Response(
                200,
                json={
                    "description": "<p>Build mission software.</p>",
                    "requirements": self.requirements.get(
                        shortcode,
                        "<ul><li>BS in Computer Science</li></ul>",
                    ),
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
        poolclass=StaticPool,
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
    board: Board,
    store: ReadingStore,
    *,
    now: datetime = NOW,
    **kwargs,
):
    with board.client() as client:
        return fetch_workable_jobs(
            source_account="avalore",
            company_name="Avalore",
            store=store,
            client=client,
            now=lambda: now,
            **kwargs,
        )


def test_every_page_is_read_and_each_posting_links_to_its_own_page(
    store,
) -> None:
    board = Board(
        [posting(f"S{index}") for index in range(25)]
    )

    jobs = fetch(
        board,
        store,
    )

    assert len(jobs) == 25

    assert board.list_calls == 3

    assert jobs[0].official_url == "https://apply.workable.com/avalore/j/S0/"

    assert jobs[0].location == "Arlington, Virginia, United States"


def test_a_clearance_in_the_requirements_is_read_and_rejected(
    store,
) -> None:
    [job] = fetch(
        Board(
            [posting("DC8241F357")],
            requirements={
                "DC8241F357": (
                    "<ul><li>SECRET Security Clearance Required</li></ul>"
                ),
            },
        ),
        store,
    )

    decision = evaluate_job(
        job
    )

    assert decision.status == EligibilityStatus.REJECT

    assert (
        EligibilityReasonCode.CLEARANCE_BLOCKER
        in decision.reason_codes
    )


def test_a_contract_posting_is_typed_as_one(
    store,
) -> None:
    [job] = fetch(
        Board(
            [posting("C1", kind="contract")],
        ),
        store,
    )

    assert job.employment_type == "contract"


def test_descriptions_only_for_titles_that_could_pass_and_weekly(
    store,
) -> None:
    board = Board(
        [
            posting("S1", title="Software Engineer"),
            posting("S2", title="Office Manager"),
        ]
    )

    fetch(
        board,
        store,
        should_fetch_detail=lambda title: "Engineer" in title,
    )

    fetch(
        board,
        store,
        now=NOW + timedelta(hours=1),
        should_fetch_detail=lambda title: "Engineer" in title,
    )

    assert board.detail_calls == ["S1"]


def test_a_board_too_long_to_finish_is_refused_not_cut(
    store,
) -> None:
    with pytest.raises(
        IncompleteWorkableRead,
    ):
        fetch(
            Board(
                [posting(f"S{index}") for index in range(50)],
            ),
            store,
            max_pages=2,
        )


def test_a_hidden_location_is_not_shown_and_remote_is_said() -> None:
    assert build_location(
        {
            "locations": [
                dict(ARLINGTON, hidden=True),
            ],
            "remote": True,
        }
    ) == "Remote"


def test_a_workable_link_names_its_board() -> None:
    from backend.app.discovery.detector import (
        detect_source_from_url,
    )

    detected = detect_source_from_url(
        "https://apply.workable.com/avalore/j/DC8241F357/"
    )

    assert (
        detected.source_type.value,
        detected.source_account,
    ) == ("workable", "avalore")
