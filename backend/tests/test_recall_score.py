"""The daily score against the test lists (REC-01).

Every company, board, job and list row here is fictional; the two table
shapes copy the real lists' columns.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from importlib import import_module

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.coverage import recall
from backend.app.coverage.held_out import HELD_OUT_LISTS
from backend.app.coverage.recall import (
    BOARD,
    FEED,
    MISSED,
    ListedRole,
    build_index,
    match_role,
    parse_list,
    recall_report,
    run_daily_check,
    title_forms,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    EmployerLead,
    JobEvaluationRecord,
    JobRecord,
    JobSourceRecord,
    RecallRunRecord,
)


# 2026-11-16 08:00 Pacific.
NOW = datetime(2026, 11, 16, 16, 0, tzinfo=timezone.utc)
TODAY = date(2026, 11, 16)

SPEEDY = next(item for item in HELD_OUT_LISTS if item.key == "speedyapply")
VANSH = next(item for item in HELD_OUT_LISTS if item.key == "vanshb03")

APPLY = '<img src="https://example.invalid/apply.png" alt="Apply" width="70"/>'

SPEEDY_TEXT = "\n".join(
    [
        "### FAANG+",
        "",
        "| Company | Position | Location | Salary | Posting | Age |",
        "|---|---|---|---|---|---|",
        f'| <a href="https://northwind.example"><strong>Northwind Robotics</strong></a> | Software Engineer I | Denver, CO | $150k/yr | <a href="https://job-boards.greenhouse.io/northwind/jobs/4100000001">{APPLY}</a> | 2d |',
        "",
        "### Other",
        "",
        "| Company | Position | Location | Posting | Age |",
        "|---|---|---|---|---|",
        f'| <a href="https://lumora.example"><strong>Lumora Pay</strong></a> | Backend Engineer, New Grad | Austin, TX | <a href="https://lumora.example/careers/jobs/5200000002?gh_jid=5200000002">{APPLY}</a> | 13d |',
        f'| <a href="https://kestrel.example"><strong>Kestrel Grid</strong></a> | Associate Software Engineer | Remote - USA | <a href="https://careers-kestrel.icims.com/jobs/7844/associate-software-engineer/job">{APPLY}</a> | 1d |',
    ]
)

VANSH_TEXT = "\n".join(
    [
        "## The List",
        "",
        "| Company | Role | Location | Application/Link | Date Posted |",
        "| --- | --- | --- | :---: | :---: |",
        '| **Driftmark** | Software Engineer, 2027 🛂 | Seattle, WA | <a href="https://go.vansh.example/1Ab"><img src="x" alt="Apply"></a> | Nov 15 |',
        "| **Halcyon Bio** | Machine Learning Engineer I | Boston, MA | 🔒 | Nov 10 |",
        '| **Fabrikam** | C++ Developer (New Grad) | Remote | <a href="https://go.vansh.example/1Cd"><img src="x" alt="Apply"></a> | Dec 30 |',
    ]
)


@pytest.fixture(autouse=True)
def small_lists(monkeypatch):
    """The fictional lists are short; a real read must hold at least MIN_ROLES."""

    monkeypatch.setattr(recall, "MIN_ROLES", 1)


@pytest.fixture(name="factory")
def fixture_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def job(id_, source, account, external_id, company, title, *, seen, url="", status="PASS", reasons=()):
    return [
        JobRecord(
            id=id_,
            source=source,
            source_account=account,
            external_id=external_id,
            company=company,
            title=title,
            location="Denver, CO",
            description="",
            official_url=url,
            content_hash=f"h{id_}",
            first_seen_at=seen,
            last_seen_at=NOW,
        ),
        JobEvaluationRecord(
            job_id=id_,
            eligibility_status=status,
            role_family="SOFTWARE_ENGINEERING",
            role_priority="HIGH",
            rule_version="test",
            reason_codes=[],
            reasons=list(reasons),
            content_hash=f"h{id_}",
            is_early_career=True,
            is_new_grad=True,
            requirements_verified=True,
            evaluated_at=NOW,
        ),
    ]


def seed(session: Session) -> None:
    rows = []
    # Northwind: from its own Greenhouse board, posting number in the link.
    rows += job(1, "greenhouse", "northwind", "4100000001", "Northwind Robotics", "Software Engineer I",
                seen=datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc),
                url="https://job-boards.greenhouse.io/northwind/jobs/4100000001")
    # Lumora: only a Simplify copy, and the gate rejects it.
    rows += job(2, "simplify", "new-grad", "sim-77", "Lumora Pay", "Backend Engineer, New Grad",
                seen=datetime(2026, 11, 5, 18, 0, tzinfo=timezone.utc), status="REJECT",
                reasons=["Requires 3+ years of experience"])
    # Driftmark: by company and title, its own Lever board.
    rows += job(3, "lever", "driftmark", "aa-11", "Driftmark Inc.", "Software Engineer, 2027",
                seen=datetime(2026, 11, 17, 2, 0, tzinfo=timezone.utc))
    # A different Fabrikam role: same company, different title, so not a match.
    rows += job(4, "ashby", "fabrikam", "bb-22", "Fabrikam", "Senior C++ Developer",
                seen=datetime(2026, 11, 1, tzinfo=timezone.utc))
    session.add_all(rows)
    session.add(
        JobSourceRecord(source_type="ashby", source_account="fabrikam", company_name="Fabrikam", enabled=True, poll_interval_seconds=900)
    )
    session.add(
        EmployerLead(company_key="kestrel grid", company_name="Kestrel Grid", origin="feed", origin_details=[],
                     state="noreader", reason="", boards=[], first_seen_at=NOW, next_check_at=NOW)
    )
    session.commit()


def fetcher(url: str) -> str:
    return {SPEEDY.url: SPEEDY_TEXT, VANSH.url: VANSH_TEXT}[url]


def test_both_table_shapes_are_read_and_closed_rows_left_out() -> None:
    speedy = parse_list(SPEEDY, SPEEDY_TEXT, today=TODAY)
    assert [(role.company, role.title, role.listed_on) for role in speedy] == [
        ("Northwind Robotics", "Software Engineer I", date(2026, 11, 14)),
        ("Lumora Pay", "Backend Engineer, New Grad", date(2026, 11, 3)),
        ("Kestrel Grid", "Associate Software Engineer", date(2026, 11, 15)),
    ]
    assert speedy[0].link == "https://job-boards.greenhouse.io/northwind/jobs/4100000001"

    vansh = parse_list(VANSH, VANSH_TEXT, today=TODAY)
    assert [(role.company, role.title) for role in vansh] == [
        ("Driftmark", "Software Engineer, 2027"),
        ("Fabrikam", "C++ Developer (New Grad)"),
    ]
    # Short links are never kept, so nothing can follow them.
    assert all(role.link is None for role in vansh)
    # A date later than tomorrow belongs to last year.
    assert vansh[0].listed_on == date(2026, 11, 15)
    assert vansh[1].listed_on == date(2025, 12, 30)


def test_a_short_title_suffix_is_the_same_role_and_seniority_is_not() -> None:
    assert title_forms("Software Dev Engineer II - AMZ003914") & title_forms("Software Dev Engineer II")
    assert not title_forms("Senior Software Engineer") & title_forms("Software Engineer")


def test_a_posting_number_matches_even_under_another_company_name() -> None:
    role = ListedRole("speedyapply", "Abnormal Security", "Software Engineer I", "", "https://abnormal.example/careers/jobs/8196352003?gh_jid=8196352003", TODAY)
    candidate = recall.Candidate(9, "greenhouse", "8196352003", "Abnormal AI", "Software Engineer I, Data", "", NOW)
    assert match_role(role, build_index([candidate])) == [candidate]

    # A short number must also agree on the company.
    short = ListedRole("speedyapply", "Valiant", "Engineer", "", "https://x.example/jobs/78441/engineer", TODAY)
    other = recall.Candidate(10, "greenhouse", "78441", "Someone Else", "Engineer", "", NOW)
    assert match_role(short, build_index([other])) == []


def test_the_daily_score_says_where_each_role_came_from(factory) -> None:
    with factory() as session:
        seed(session)

    result = run_daily_check(factory, now=NOW, fetch=fetcher)

    total = result["total"]
    assert (total["listed"], total["board"], total["feed"], total["missed"]) == (5, 2, 1, 2)
    assert total["found"] == 3
    assert total["hidden"] == 1
    assert total["hidden_reasons"] == [{"reason": "Requires 3+ years of experience", "count": 1}]
    # Northwind listed Nov 14, seen Nov 14; Driftmark listed Nov 15, seen Nov 16
    # Pacific: both within a day. Lumora listed Nov 3, seen Nov 5: late.
    assert (total["timed"], total["within_day"], total["seen_first"]) == (3, 2, 0)
    assert result["leaks"] == {"boards": 0, "jobs": 0, "leads": 0}

    reasons = {row["company"]: row["reason"] for row in result["missed"]}
    assert reasons == {
        "Kestrel Grid": "Posted on iCIMS, which ace can't read yet",
        "Fabrikam": "Board read, role not there",
    }

    by_list = {item["key"]: item for item in result["lists"]}
    assert (by_list["speedyapply"]["listed"], by_list["speedyapply"]["found"]) == (3, 2)
    assert (by_list["vanshb03"]["listed"], by_list["vanshb03"]["found"]) == (2, 1)


def test_it_runs_once_a_day_and_not_before_morning(factory) -> None:
    calls: list[str] = []

    def counting(url: str) -> str:
        calls.append(url)
        return fetcher(url)

    early = datetime(2026, 11, 16, 11, 0, tzinfo=timezone.utc)  # 03:00 Pacific
    assert run_daily_check(factory, now=early, fetch=counting) is None
    assert calls == []

    assert run_daily_check(factory, now=NOW, fetch=counting) is not None
    assert run_daily_check(factory, now=NOW + timedelta(hours=3), fetch=counting) is None
    assert len(calls) == 2

    with factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(RecallRunRecord)) == 1


def test_an_unreadable_list_is_reported_not_scored_as_misses(factory) -> None:
    def broken(url: str) -> str:
        if url == VANSH.url:
            raise recall.httpx.ConnectError("down")
        return SPEEDY_TEXT

    result = run_daily_check(factory, now=NOW, fetch=broken)

    by_list = {item["key"]: item for item in result["lists"]}
    assert by_list["vanshb03"] == {"key": "vanshb03", "label": VANSH.label, "links": "short", "error": "could not be read today"}
    assert result["total"]["listed"] == 3


def test_a_thin_read_is_not_a_list(factory, monkeypatch) -> None:
    monkeypatch.setattr(recall, "MIN_ROLES", 20)
    result = run_daily_check(factory, now=NOW, fetch=fetcher)
    assert all(item.get("error") for item in result["lists"])
    assert result["total"]["listed"] == 0


def test_the_report_carries_two_weeks_of_scores(factory) -> None:
    with factory() as session:
        seed(session)
    for days in range(3, -1, -1):
        run_daily_check(factory, now=NOW - timedelta(days=days), fetch=fetcher)

    with factory() as session:
        report = recall_report(session)
    assert report["checked"] is True
    assert report["day"] == "2026-11-16"
    assert report["checked_at"] == NOW.isoformat()
    assert [point["day"] for point in report["trend"]] == ["2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16"]
    assert report["missed"] and report["total"]["listed"] == 5


def test_no_run_yet_says_so(factory) -> None:
    with factory() as session:
        assert recall_report(session) == {"checked": False}


def test_the_check_reads_only_test_lists() -> None:
    with pytest.raises(ValueError, match="only test lists"):
        recall.fetch_list("https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md")


def test_the_migration_only_adds_its_table(monkeypatch) -> None:
    migration = import_module("backend.migrations.versions.0052_recall_runs")
    assert migration.down_revision == "0051"
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE jobs (id INTEGER PRIMARY KEY, title VARCHAR(255))"))
        connection.execute(sa.text("INSERT INTO jobs VALUES (1, 'Fictional Engineer')"))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        assert "recall_runs" in sa.inspect(connection).get_table_names()
        migration.downgrade()
        assert "recall_runs" not in sa.inspect(connection).get_table_names()
        assert connection.execute(sa.text("SELECT title FROM jobs")).scalar_one() == "Fictional Engineer"


def test_a_list_label_before_a_colon_is_not_the_title() -> None:
    role = ListedRole("vanshb03", "Palm Ridge", "New Grad 2027: Software Engineer", "", None, TODAY)
    exact = recall.Candidate(20, "greenhouse", "x1", "Palm Ridge", "Software Engineer", "", NOW)
    assert match_role(role, build_index([exact])) == [exact]


def test_new_grad_wording_matches_only_an_early_career_employer_title() -> None:
    role = ListedRole("vanshb03", "Palm Ridge", "New Grad: Backend Engineer", "", None, TODAY)
    early = recall.Candidate(21, "lever", "y1", "Palm Ridge", "Backend Engineer, University Graduate 2027", "", NOW)
    senior = recall.Candidate(22, "lever", "y2", "Palm Ridge", "Backend Engineer III", "", NOW)
    assert match_role(role, build_index([early, senior])) == [early]


def test_extra_words_in_an_early_career_title_still_match() -> None:
    role = ListedRole("vanshb03", "Palm Ridge", "New Grad 2027: Testing Engineer, Social and Relation", "", None, TODAY)
    held = recall.Candidate(23, "bytedance", "z1", "Palm Ridge",
                            "Testing Engineer Graduate (Palm Ridge Social and Relation) - 2027 Start", "", NOW)
    other_team = recall.Candidate(24, "bytedance", "z2", "Palm Ridge",
                                  "Testing Engineer Graduate (Payments Risk Ledger Billing Systems) - 2027 Start", "", NOW)
    assert match_role(role, build_index([held, other_team])) == [held]


def test_one_word_titles_never_match_by_words() -> None:
    role = ListedRole("vanshb03", "Palm Ridge", "New Grad: Engineer", "", None, TODAY)
    held = recall.Candidate(25, "lever", "z3", "Palm Ridge", "Engineer Graduate Platform Tools", "", NOW)
    assert match_role(role, build_index([held])) == []


def test_a_readable_board_ace_lacks_says_so() -> None:
    role = ListedRole("speedyapply", "Palm Ridge", "Software Engineer", "", "https://jobs.lever.co/palmridge/0a1b2c3d", TODAY)
    assert recall.miss_reason(role, leads={}, boards=set()) == recall.READABLE_NOT_ADDED


def test_an_internship_is_never_a_listed_full_time_role() -> None:
    role = ListedRole("vanshb03", "Palm Ridge", "Software Engineer", "", None, TODAY)
    intern = recall.Candidate(26, "workday", "w1", "Palm Ridge", "Software Engineer Intern (Summer 2027)", "", NOW)
    college = recall.Candidate(27, "workday", "w2", "Palm Ridge", "College Intern", "", NOW)
    assert match_role(role, build_index([intern, college])) == []
