"""YC companies marked hiring become name leads (DIS-06). Every company and website here is fictional."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.coverage import diagnosis as diag
from backend.app.coverage.leads import CHECKING, NOREADER, YC, check_due_leads, leads_report
from backend.app.db.base import Base
from backend.app.db.models import EmployerLead, JobSourceRecord, RecallRunRecord
from backend.app.discovery import yc_names as yc

NOW = datetime(2026, 11, 27, 16, 0, tzinfo=timezone.utc)


def company(name, *, website="https://zephyrlabs.example", regions=("United States of America", "America / Canada"),
            status="Active", hiring=True):
    return {"name": name, "website": website, "regions": list(regions), "status": status, "isHiring": hiring,
            "slug": name.lower().replace(" ", "-"), "batch": "Fall 2026"}


FILLER = [company(f"Filler Co {n}", website=f"https://filler{n}.example", regions=("Europe",)) for n in range(yc.MIN_COMPANIES)]

LISTED = [
    company("Zephyr Labs", website="https://www.zephyrlabs.example/"),
    company("Quill Works", website="quillworks.example"),
    company("Orbit Pine", website="https://orbitpine.example", regions=("Canada", "America / Canada")),
    company("Harbor Nine", website="https://harbornine.example", status="Inactive"),
    company("Cobalt Ferry", website="", regions=("United States of America",)),
    company("Zephyr Labs", website="https://zephyrlabs.example"),
]


def test_only_us_companies_marked_hiring_are_kept_with_their_own_website():
    found = yc.parse(LISTED + FILLER)
    assert [(c.name, c.host) for c in found.companies] == [
        ("Zephyr Labs", "zephyrlabs.example"), ("Quill Works", "quillworks.example"), ("Cobalt Ferry", None)]
    assert found.listed == len(LISTED) + len(FILLER) and found.us == 3
    with pytest.raises(yc.ShortList):
        yc.parse(LISTED)
    assert yc.website_host("javascript:alert(1)") is None and yc.website_host("https://bad host.example") is None


@pytest.fixture(name="sessions")
def fixture_sessions():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def test_new_companies_become_leads_and_a_failed_name_search_starts_again_at_the_website(sessions):
    with sessions.begin() as session:
        session.add(JobSourceRecord(source_type="ashby", source_account="quillworks", company_name="Quill Works",
                                    enabled=True, poll_interval_seconds=900, discovery_source="lead_ledger"))
        session.add(EmployerLead(company_key="cobalt ferry", company_name="Cobalt Ferry", origin="network",
                                 origin_details=["network"], state=NOREADER, reason="Nothing found by name.",
                                 boards=[], first_seen_at=NOW, next_check_at=NOW + timedelta(days=20), updated_at=NOW))
    found = yc.parse(LISTED + FILLER)
    found.companies[2].host = "cobaltferry.example"
    with sessions.begin() as session:
        counts = yc.remember(session, found, now=NOW)
    assert counts == {"us_hiring": 3, "read_by_ace": 1, "leads_new": 1, "leads_with_new_site": 1, "leads_known": 0}
    with sessions() as session:
        rows = {row.company_key: row for row in session.scalars(sa.select(EmployerLead))}
    zephyr, cobalt = rows["zephyr"], rows["cobalt ferry"]
    assert zephyr.origin == YC and zephyr.state == CHECKING and zephyr.boards == []
    assert zephyr.origin_details == ["yc", "yc:zephyrlabs.example"]
    assert yc.site_hints(zephyr.origin_details) == ("zephyrlabs.example",)
    # The stronger origin stays; the lead is looked at again now, from its website.
    assert cobalt.origin == "network" and cobalt.state == CHECKING
    assert cobalt.next_check_at.replace(tzinfo=timezone.utc) == NOW
    assert yc.site_hints(cobalt.origin_details) == ("cobaltferry.example",)
    # Reading the same list again changes nothing.
    with sessions.begin() as session:
        again = yc.remember(session, found, now=NOW + timedelta(days=1))
    assert again["leads_new"] == 0 and again["leads_with_new_site"] == 0 and again["leads_known"] == 2
    with sessions() as session:
        labels = {origin["origin"]: origin["label"] for origin in leads_report(session)["origins"]}
    assert labels[YC] == "YC companies"


def test_the_name_search_is_handed_the_website_first(sessions):
    with sessions.begin() as session:
        session.add(EmployerLead(company_key="zephyr", company_name="Zephyr Labs", origin=YC,
                                 origin_details=["yc", "yc:zephyrlabs.example"], state=CHECKING, reason=yc.REASON,
                                 boards=[], first_seen_at=NOW, next_check_at=NOW, updated_at=NOW))
        session.add(EmployerLead(company_key="orbit pine", company_name="Orbit Pine", origin="network",
                                 origin_details=["network"], state=CHECKING, reason="Not looked at yet.",
                                 boards=[], first_seen_at=NOW, next_check_at=NOW, updated_at=NOW))
    asked = []

    def diagnose_name(company, hosts=()):
        asked.append((company, hosts))
        return diag.Diagnosis(company=company, outcome="no_board_found", detail="Nothing found.")

    check_due_leads(sessions, now=lambda: NOW, assess_board=lambda board, company: None,
                    diagnose_name=diagnose_name, pause=lambda s: None)
    assert sorted(asked) == [("Orbit Pine", ()), ("Zephyr Labs", ("zephyrlabs.example",))]


def test_diagnose_tries_the_named_website_before_any_guess(monkeypatch):
    tried = []
    monkeypatch.setattr(diag, "find_board", lambda company, **kwargs: None)

    def fetch_text(url):
        tried.append(url)
        return ""

    diag.diagnose("Zephyr Labs", fetch=lambda url: None, fetch_text=fetch_text, post=lambda *a, **k: None,
                  refuses=lambda *a, **k: False, hosts=("zephyrlabs.example",))
    assert tried[0] == "https://zephyrlabs.example"


def scored(sessions, day=date(2026, 11, 27)):
    with sessions.begin() as session:
        session.add(RecallRunRecord(day=day, checked_at=NOW, summary={"total": {"listed": 1}}, missed=[]))


class FakeList:
    def __init__(self, rows, status=200):
        self.rows, self.status, self.asked = rows, status, []

    def __call__(self, url):
        self.asked.append(url)
        return httpx.Response(self.status, json=self.rows, request=httpx.Request("GET", url))


def test_it_reads_the_list_once_a_day_after_the_score_and_never_opens_yc(sessions):
    get = FakeList(LISTED + FILLER)
    assert yc.harvest_if_due(sessions, now=NOW, allows=lambda url: True, get=get) is None  # no score yet
    scored(sessions)
    mark = yc.harvest_if_due(sessions, now=NOW, allows=lambda url: True, get=get)
    assert mark["finished"] and mark["leads_new"] == 3
    assert get.asked == [yc.LIST_URL] and all("ycombinator.com" not in url for url in get.asked)
    with sessions() as session:
        assert session.scalar(sa.select(RecallRunRecord.summary))["yc"]["leads_new"] == 3
    assert yc.harvest_if_due(sessions, now=NOW + timedelta(hours=3), allows=lambda url: True, get=get) is None
    scored(sessions, day=date(2026, 11, 28))
    refused = yc.harvest_if_due(sessions, now=NOW + timedelta(days=1, hours=1), allows=lambda url: False, get=get)
    assert refused["stopped"] == "the list's robots rules refuse ace" and len(get.asked) == 1
    scored(sessions, day=date(2026, 11, 29))
    failed = yc.harvest_if_due(sessions, now=NOW + timedelta(days=2, hours=1), allows=lambda url: True,
                               get=FakeList([], status=429))
    assert failed["finished"] is False and failed["stopped"] == "HTTPStatusError"
