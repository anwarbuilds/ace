"""Company identity across discovery, hand-add and official petition joins.

Every employer, board and record in this file is fictional.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.api.routers.companies import company_intelligence, company_intelligence_batch
from backend.app.coverage import identity
from backend.app.coverage.identity import BoardEvidence, page_evidence, resolve_employer, same_employer
from backend.app.coverage.leads import AGENCY, CHECKING, finding_from
from backend.app.coverage.leads import sync_leads
from backend.app.coverage.petition_identity import petition_reports_for
from backend.app.coverage.probing import BoardRef, board_belongs_to, ref_belongs_to, workday_belongs_to
from backend.app.coverage.service import add_source
from backend.app.db.base import Base
from backend.app.db.models import CompanyPetitionReportRecord, EmployerLead, JobRecord, JobSourceRecord
from backend.app.discovery.feed_links import boards_named_in, read_boards, register_confirmed_boards
from backend.app.models.job import CanonicalJob
from backend.scripts.register_network_boards import Candidate, assess, register


NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
URL = "https://jobs.ashbyhq.com/fictional-vc/job-1"


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def reviewed(monkeypatch):
    monkeypatch.setattr(identity, "REVIEWED_SHARED_BOARDS", {
        ("ashby", "fictional-vc"): "Reviewed fictional shared portfolio board.",
    })


def job(title="Software Engineer, New Grad"):
    return CanonicalJob(source="ashby", company="Fictional VC", external_id=title,
        title=title, location="New York, NY", description="Build software with a team. " * 30,
        official_url=URL)


@pytest.mark.parametrize("a,b", [
    ("Fictional Works", "Fictional Works Inc."),
    ("Fictional AI", "Fictional.ai"),
    ("Fictional-Works", "fictional works LLC"),
])
def test_safe_spelling_and_legal_endings(a, b):
    assert same_employer(a, b)


@pytest.mark.parametrize("a,b", [
    ("Fictional", "Fictional Labs"),
    ("Fictional AI", "Fictional"),
    ("Fictional Bank", "Fictional Bank Payments"),
    ("FSI", "Fictional Space Intelligence"),
    ("Fictional Robotics", "Fictional Robotics Holdings"),
    ("", "Fictional"),
])
def test_related_words_initials_and_subsidiaries_do_not_prove_identity(a, b):
    assert not same_employer(a, b)


def test_owner_evidence_controls_display_without_claiming_a_legal_alias():
    found = resolve_employer("Old Fictional", BoardEvidence(owner="Fictional Acquirer", basis="official board metadata"))
    assert found.company == "Fictional Acquirer"
    assert found.state == "confirmed"
    assert not same_employer("Old Fictional", found.company)
    assert resolve_employer("Fictional Parent", BoardEvidence(owner="Fictional Subsidiary")).company == "Fictional Subsidiary"


def test_copied_board_name_is_not_independent_job_employer_evidence():
    found = resolve_employer("Fictional VC", None, titles=[job().title])
    assert found.state == "unknown" and found.company is None


def test_matching_investor_labels_cannot_rescue_different_portfolio_jobs():
    outcome = assess(Candidate("ashby", "fictional-capital", "Fictional Capital"),
        lambda definition: [job("Software Engineer - Fictional Birch"), job("Software Engineer - Fictional Acorn")],
        lambda candidate: "Fictional Capital")
    assert not outcome.added and outcome.reason.startswith("identity:")
    finding = finding_from(outcome, {"source_type": "ashby"})
    assert finding.state == CHECKING and not finding.gone


def test_an_ordinary_employer_named_capital_can_be_confirmed():
    found = resolve_employer("Fictional Capital", BoardEvidence(
        owner="Fictional Capital Inc", employers=("Fictional Capital",)),
        titles=["Software Engineer - Backend", "Software Engineer - Frontend"])
    assert found.company == "Fictional Capital" and found.state == "confirmed"


def test_explicit_portfolio_heading_wins_even_when_names_agree():
    evidence = page_evidence("<title>Fictional VC</title><h1>Jobs at our portfolio companies</h1>", "Fictional VC", basis="fixture board")
    assert resolve_employer("Fictional VC", evidence).state == "shared"
    # A job mentioning its employer's investment portfolio is not a shared board.
    normal = page_evidence("<title>Fictional Capital Jobs</title><p>Manage our portfolio companies.</p>", "Fictional Capital", basis="fixture")
    assert not normal.shared


def test_multiple_structured_hiring_employers_are_a_shared_board():
    page = '''<script type="application/ld+json">{"@graph":[
        {"@type":"JobPosting","hiringOrganization":{"name":"Fictional Acorn"}},
        {"@type":"JobPosting","hiringOrganization":{"name":"Fictional Birch"}},
        {"@type":"Organization","name":"Fictional VC"}]}</script>'''
    found = resolve_employer("Fictional VC", page_evidence(page, "Fictional VC", basis="fixture"))
    assert found.state == "shared" and found.company is None


def test_a_conflicting_board_owner_and_job_employer_abstains():
    found = resolve_employer("Fictional Parent", BoardEvidence(owner="Fictional Parent", employers=("Fictional Child",)))
    assert found.state == "unknown" and found.company is None


def test_unrelated_company_mentions_cannot_rescue_a_wrong_declared_owner():
    fetch = lambda url: {"name": "Fictional Other"}
    assert ref_belongs_to(company="Fictional Target", ref=BoardRef("greenhouse", "fictional"),
        jobs=[{"title": "Software Engineer", "descriptionPlain": "Fictional Target is a customer."}],
        fetch=fetch, fetch_text=lambda url: "Fictional Target is a customer.") is None


def test_a_parent_tenant_does_not_prove_subsidiary_or_abbreviated_ownership():
    assert workday_belongs_to(company="Fictional Parent", token="fictionalparent/External")
    assert workday_belongs_to(company="Fictional Parent Inc", token="fictionalparent/External")
    assert workday_belongs_to(company="Fictional Parent Child", token="fictionalparent/External") is None
    assert workday_belongs_to(company="Fictional Labs", token="fictional/External") is None


def test_eu_lever_identity_stays_on_the_original_host():
    requests = []
    def page(url):
        requests.append(url)
        return "<title>Fictional Works</title>"
    found = identity.read_board_evidence("lever", "fictional", source_host="jobs.eu.lever.co", fetch_text=page)
    assert found.owner == "Fictional Works"
    assert requests == ["https://jobs.eu.lever.co/fictional"]


def test_reviewed_shared_board_rejected_before_network_and_never_registered(db, reviewed):
    fail = lambda *args: pytest.fail("a reviewed shared board must not be requested")
    result = assess(Candidate("ashby", "Fictional-VC", "Fictional VC"), fail, fail)
    assert not result.added and result.reason.startswith("shared:")
    assert finding_from(result, {"source_type": "ashby"}).state == AGENCY
    assert not register(db, result, now=NOW)
    assert db.scalar(select(JobSourceRecord)) is None
    assert board_belongs_to(company="Fictional VC", source_type="ashby", token="fictional-vc", jobs=[], fetch=fail, fetch_text=fail) is None


def test_shared_feed_and_conflicting_feed_labels_need_authoritative_owner(db, reviewed):
    [board] = boards_named_in([(URL, "Fictional Acorn"), (URL, "Fictional Birch")])
    assert board.listed_names == ("Fictional Acorn", "Fictional Birch")
    [result] = read_boards([board], lambda definition: pytest.fail("do not read a reviewed shared board"))
    assert not result.registered and result.error.startswith("shared:")
    assert not register_confirmed_boards(db, [result], now=NOW)
    [row] = db.scalars(select(JobSourceRecord)).all()
    assert not row.enabled


def test_feed_job_count_and_matching_input_name_are_not_proof():
    [board] = boards_named_in([("https://jobs.ashbyhq.com/fictional-one/job-1", "Fictional One")])
    [result] = read_boards([board], lambda definition: [job()])
    assert not result.registered and result.error.startswith("identity:")
    [renamed] = read_boards([board], lambda definition: [job()], lambda board: BoardEvidence(owner="Fictional Acquirer"))
    assert renamed.registered and renamed.board.company_name == "Fictional Acquirer"


def hand_add(db, url, *, page="", fetch=None):
    return add_source(db, text=url, fetch=fetch or (lambda url: {"jobs": [{"title": "Software Engineer"}]}),
        fetch_text=lambda url: page, post=lambda *args: None, robots=lambda host: "",
        fetch_robots=lambda host: (404, ""), refuses=lambda url: False, now=NOW)


def test_manual_paste_of_reviewed_shared_board_is_kept_as_lead_not_employer(db, reviewed):
    result = hand_add(db, URL, fetch=lambda url: pytest.fail("do not read shared board"))
    assert result.status == "saved_looking" and "shared" in result.detail
    assert db.scalar(select(JobSourceRecord)) is None
    lead = db.scalar(select(EmployerLead))
    assert lead.state == AGENCY and lead.owner_added_at is not None
    assert lead.boards[0]["source_account"] == "fictional-vc"


def test_pasted_token_is_not_a_company_but_authoritative_name_is_used(db):
    url = "https://jobs.ashbyhq.com/fictional-board/job-1"
    unresolved = hand_add(db, url)
    assert unresolved.status == "saved_looking" and "confirm" in unresolved.detail
    assert db.scalar(select(JobSourceRecord)) is None
    confirmed = hand_add(db, url, page="<title>Fictional Acquirer Jobs</title>")
    assert confirmed.status == "added" and confirmed.company == "Fictional Acquirer"
    assert db.scalar(select(JobSourceRecord)).company_name == "Fictional Acquirer"


def test_new_shared_board_caught_from_its_own_page_without_a_reviewed_entry(db):
    result = hand_add(db, "https://jobs.ashbyhq.com/fictional-new/job-1",
        page="<title>Fictional Capital Jobs</title><h1>Portfolio company jobs</h1>")
    assert result.status == "saved_looking" and "portfolio" in result.detail
    assert db.scalar(select(JobSourceRecord)) is None
    assert db.scalar(select(EmployerLead)).state == AGENCY


def test_a_customer_mention_cannot_turn_a_pasted_token_into_an_employer(db):
    result = hand_add(db, "https://jobs.ashbyhq.com/fictional/job-1",
        fetch=lambda url: {"jobs": [{"title": "Software Engineer", "descriptionPlain": "Fictional is our customer, not our employer."}]})
    assert result.status == "saved_looking"
    assert db.scalar(select(JobSourceRecord)) is None
    assert db.scalar(select(EmployerLead)).state == CHECKING


def test_a_name_search_with_only_a_prose_mention_remains_a_lead(db, monkeypatch):
    from types import SimpleNamespace
    from backend.app.coverage.probing import BoardCandidate
    monkeypatch.setattr("backend.app.coverage.service.diagnose", lambda *args, **kwargs: SimpleNamespace(
        candidate=BoardCandidate(company="Fictional Target", source_type="ashby", source_account="fictional", job_count=1,
            evidence="company named in posting descriptionPlain")))
    result = add_source(db, text="Fictional Target", fetch=lambda url: None,
        fetch_text=lambda url: "", post=lambda *args: None, robots=lambda host: "",
        fetch_robots=lambda host: (404, ""), refuses=lambda url: False, now=NOW)
    assert result.status == "saved_looking" and "mentions" in result.detail
    assert db.scalar(select(JobSourceRecord)) is None


def test_an_exact_tenant_cannot_rescue_conflicting_structured_employers(monkeypatch):
    from backend.app.coverage.service import _verify
    monkeypatch.setattr("backend.app.coverage.service.board_jobs", lambda *args, **kwargs: [
        {"title": "Software Engineer", "hiringOrganization": {"name": "Fictional Acorn"}},
        {"title": "Software Engineer", "hiringOrganization": {"name": "Fictional Birch"}},
    ])
    found = _verify(BoardRef("workday", "fictional/External", "fictional.wd5.myworkdayjobs.example"), "Fictional",
        fetch=lambda url: None, fetch_text=lambda url: "", post=lambda *args: None, default_evidence="pasted board")
    assert found.evidence.startswith("shared:")


def test_a_switched_off_shared_board_stays_off(db, reviewed):
    db.add(JobSourceRecord(source_type="ashby", source_account="fictional-vc", company_name="Fictional VC",
        enabled=False, poll_interval_seconds=900, discovery_source="owner decision"))
    db.commit()
    result = hand_add(db, URL)
    assert result.status == "known_off"
    assert not db.scalar(select(JobSourceRecord)).enabled


def test_shared_board_names_become_unverified_leads_not_sources_or_employer_aliases(db, reviewed, tmp_path):
    network = tmp_path / "network.json"
    network.write_text('{"boards": []}')
    db.add(JobSourceRecord(source_type="ashby", source_account="fictional-vc", company_name="Fictional VC",
        enabled=True, poll_interval_seconds=900, discovery_source="talent_network"))
    for index, title in enumerate(("Software Engineer - Fictional Birch", "Software Engineer - Fictional Labs",
                                   "Software Engineer - Remote", "Software Engineer - Backend")):
        db.add(JobRecord(source="ashby", source_account="fictional-vc", company="Fictional VC", external_id=str(index),
            title=title, location="US", description="Fictional", official_url=URL, content_hash="fixture", is_active=True))
    db.flush()
    sync_leads(db, now=NOW, network_file=network)
    row = db.scalar(select(EmployerLead).where(EmployerLead.company_name == "Fictional Birch"))
    original_id = row.id
    assert row.state == CHECKING and row.next_check_at is not None
    assert row.boards == [] and row.owner_added_at is None
    assert any("Unverified" in detail for detail in row.origin_details)
    assert db.scalar(select(EmployerLead).where(EmployerLead.company_name == "Fictional VC")).state == AGENCY
    assert db.scalar(select(EmployerLead).where(EmployerLead.company_name == "Remote")) is None
    assert len(db.scalars(select(JobSourceRecord)).all()) == 1
    # An owner-approved actual board later resolves the lead, keeping its ID.
    db.add(JobSourceRecord(source_type="ashby", source_account="fictional-birch", company_name="Fictional Birch",
        enabled=True, poll_interval_seconds=900, discovery_source="talent_network"))
    db.flush()
    sync_leads(db, now=NOW, network_file=network)
    rows = db.scalars(select(EmployerLead).where(EmployerLead.company_name == "Fictional Birch")).all()
    assert len(rows) == 1 and rows[0].id == original_id and rows[0].state == "polling"
    # Stored jobs and source settings are not changed by gathering leads.
    assert len(db.scalars(select(JobRecord)).all()) == 4
    assert all(row.is_active for row in db.scalars(select(JobRecord)))


def report(db, name, *, verified=True):
    db.add(CompanyPetitionReportRecord(ace_company=name, legal_entity=name + " Inc",
        source_name="Fictional USCIS fixture", source_uri="https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub",
        metric_definition="USCIS I-129 petition decisions", period="FY 2025", report_version=name,
        petition_approvals=12, petition_denials=1, entity_verified=verified, first_seen_at=NOW, last_checked_at=NOW))
    db.flush()


def test_petitions_never_flow_through_parent_acquisition_initials_or_shared_board(db, reviewed):
    report(db, "Fictional Parent")
    report(db, "Fictional Acquirer")
    report(db, "Fictional VC")
    report(db, "Fictional Unreviewed", verified=False)
    db.add(JobSourceRecord(source_type="ashby", source_account="fictional-vc", company_name="Fictional VC",
        enabled=False, poll_interval_seconds=900))
    db.flush()
    for name in ("Fictional Child", "Old Fictional", "FP", "Fictional VC", "Fictional Unreviewed"):
        assert petition_reports_for(db, [name]) == []
        assert company_intelligence(name=name, session=db)["status"] == "unavailable"
        assert company_intelligence_batch(name=[name], session=db) == {"items": {}}
    assert company_intelligence(name="Fictional Parent", session=db)["status"] == "verified"
    assert set(company_intelligence_batch(name=["Fictional Parent", "Fictional Child", "Fictional VC"], session=db)["items"]) == {"Fictional Parent"}
