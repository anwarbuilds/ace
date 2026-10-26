"""Read projection invariants using an isolated fictional SQLite database."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from backend.app.api.routers.analytics import analytics_read
from backend.app.db.base import Base
from backend.app.db.models import ApplicationEventRecord, CompanyPetitionReportRecord, ExternalApplicationRecord, GmailMessageRecord, JobEvaluationRecord, JobMarkRecord, JobRecord

NOW = datetime(2026, 10, 26, 6, tzinfo=timezone.utc)  # Sunday 11 PM Pacific

@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def app(db, index, age=40, status="applied", company="Silverpine Labs", family="SOFTWARE_ENGINEERING"):
    stamp=NOW-timedelta(days=age)
    job=JobRecord(source="fixture", source_account="fictional", external_id=str(index), company=company, title="Fictional software role", location="US", description="Fictional application", official_url="https://silverpine.example/jobs", content_hash="fixture", first_seen_at=stamp, last_seen_at=NOW, is_active=False)
    db.add(job); db.flush()
    db.add(JobMarkRecord(job_id=job.id, applied_at=stamp, application_status=status))
    db.add(JobEvaluationRecord(job_id=job.id, eligibility_status="REJECT", role_family=family, role_priority="NORMAL", content_hash="fixture", rule_version="fixture", reasons=[], is_early_career=True, requirements_verified=True))
    db.flush()
    return f"job:{job.id}"


def outcome(db,key,kind,stamp=None,**kwargs):
    row=ApplicationEventRecord(application_key=key,kind=kind,actor="owner",reason="Fictional owner-confirmed evidence",occurred_at=stamp or NOW-timedelta(days=35),dedupe_key=f"fixture:{key}:{kind}:{db.scalar(select(func.count()).select_from(ApplicationEventRecord))}",**kwargs)
    db.add(row);db.flush();return row


def read(db,**kwargs):
    db.flush()
    return analytics_read(db,now=NOW,days="all",**{"tz":"America/Los_Angeles",**kwargs})


def test_unique_application_counts_closed_jobs_external_and_events(db):
    key=app(db,1)
    app(db,2,company="Silverpine Labs")  # Separate requisition, never fuzzy merge.
    db.add(ExternalApplicationRecord(company="External Fiction",title="Fictional",match_key="external-fiction",applied_at=NOW-timedelta(days=50),application_status="rejected"))
    outcome(db,key,"online_assessment");outcome(db,key,"online_assessment");outcome(db,key,"interview")
    d=read(db)
    assert d["total_submitted"]==d["submitted"]==3
    assert d["positive"]==d["assessments"]==d["interviews"]==1
    assert sum(d["statuses"].values())==3
    assert d["cohort"]["positive"]==1 and d["cohort"]["rejected"]==1
    assert sum(d["cohort"][key] for key in ("positive","rejected","pending","unknown"))==d["cohort"]["eligible"]
    assert d["cohort"]["rate"] is None


def test_silence_and_no_reply_are_never_rejections(db):
    app(db,1,age=300,status="ghosted");app(db,2,age=300)
    d=read(db)
    assert d["cohort"]["pending"]==2
    assert d["cohort"]["rejected"]==0
    assert not d["has_outcome_evidence"]


def test_undo_preview_untrusted_actor_receipt_and_pre_submission_excluded(db):
    key=app(db,1)
    e=outcome(db,key,"interview")
    outcome(db,key,"undo",undo_of_id=e.id)
    outcome(db,key,"application_confirmation")
    row=outcome(db,key,"online_assessment");row.actor="preview"
    outcome(db,key,"rejection",stamp=NOW-timedelta(days=60))
    d=read(db)
    assert d["positive"]==d["assessments"]==d["interviews"]==0
    assert d["cohort"]["rejected"]==0
    assert d["median_days"] is None


def test_30_day_threshold_and_disjoint_rejection_after_interview(db):
    key=app(db,1,age=30);app(db,2,age=29.999)
    outcome(db,key,"interview",stamp=NOW-timedelta(days=28))
    outcome(db,key,"rejection",stamp=NOW-timedelta(days=20))
    d=read(db)
    assert d["cohort"]["eligible"]==1
    assert d["cohort"]["positive"]==0 and d["cohort"]["rejected"]==1
    assert d["positive"]==1 and d["median_days"]==2


def test_week_is_local_monday_to_sunday_and_independent_of_selected_range(db):
    app(db,1,age=0);app(db,2,age=6);app(db,3,age=7)
    d=read(db,start=NOW.date()-timedelta(days=3))
    assert d["week"][0]["date"]=="2026-10-19"
    assert d["week"][-1]["date"]=="2026-10-25"
    assert d["week_total"]==2
    assert sum(r["count"] for r in d["week"])==2


def test_timezone_boundary_not_utc_date(db):
    key=app(db,1,age=0)
    mark=db.get(JobMarkRecord,int(key.split(":")[1]));mark.applied_at=datetime(2026,10,25,1,tzinfo=timezone.utc)
    d=read(db)
    assert {r["date"]:r["count"] for r in d["daily"]}["2026-10-24"]==1
    assert d["week"][-1]["count"]==0


def test_role_and_custom_date_filter_preserve_lifetime(db):
    app(db,1,age=2,family="SOFTWARE_ENGINEERING");app(db,2,age=2,family="ML_ENGINEERING");app(db,3,age=40)
    d=read(db,family="SOFTWARE_ENGINEERING",start=NOW.date()-timedelta(days=4),end=NOW.date()-timedelta(days=1))
    assert d["submitted"]==1 and d["total_submitted"]==3
    assert d["roles"][0]["submitted"]==1
    assert d["attribution"]["resume"]==d["attribution"]["channel"]=="Not recorded"
    assert not d["attribution"]["combinations"]


def test_undated_history_in_all_time_not_chart_or_cohort(db):
    db.add(ExternalApplicationRecord(company="Fictional",title="Unknown date",match_key="unknown",applied_at=None))
    d=read(db)
    assert d["total_submitted"]==d["submitted"]==d["undated"]==1
    assert d["cohort"]["eligible"]==sum(r["count"] for r in d["daily"])==0


def report(db,company="Silverpine Labs",year="2025",approvals=12,denials=3,**kwargs):
    row=CompanyPetitionReportRecord(ace_company=company,legal_entity="Fictional Legal Entity",period=f"FY {year}",report_version=kwargs.pop("version", "fixture"),source_name="Fictional USCIS report fixture",source_uri="https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub",metric_definition="USCIS I-129 petition decisions",petition_approvals=approvals,petition_denials=denials,entity_verified=True,first_seen_at=NOW,last_checked_at=NOW,**kwargs)
    db.add(row);db.flush();return row


def test_petitions_official_only_exact_entity_revisions_and_lca_separate(db):
    app(db,1)
    report(db)
    revision=report(db,approvals=16,denials=4,version="newer");revision.last_checked_at=NOW+timedelta(seconds=1)
    lca=report(db,year="2024",approvals=300,denials=None);lca.metric_definition="DOL certified LCAs";lca.source_uri="https://www.dol.gov/agencies/eta/foreign-labor/performance"
    wrong=report(db,year="2023");wrong.source_uri="https://unverified.example/reports"
    fuzzy=report(db,company="Silverpine Labs Holdings",year="2022")
    d=read(db)
    assert len(d["annual"])==1 and d["annual"][0]["approvals"]==16
    assert d["annual"][0]["rate"]==.8
    assert len(d["reports"])==2
    assert next(r for r in d["reports"] if r["metric"]=="DOL certified LCAs")["rate"] is None
    assert all(r["name"]!="Silverpine Labs Holdings" for r in d["verified_companies"])


def test_no_report_is_not_zero_sponsorship(db):
    app(db,1)
    d=read(db)
    assert not d["annual"] and not d["reports"] and not d["verified_companies"]


def test_manual_stage_is_counted_without_invented_response_time(db):
    app(db,1,status="interviewing")
    d=read(db)
    assert d["interviews"]==d["positive"]==1
    assert d["median_days"] is None and d["timing_sample"]==0


def test_read_is_pure_and_queries_do_not_scan_discovery_evaluations(db):
    app(db,1)
    statements=[]
    def capture(conn,cursor,statement,parameters,context,executemany):statements.append(statement)
    event.listen(db.bind,"before_cursor_execute",capture)
    read(db)
    event.remove(db.bind,"before_cursor_execute",capture)
    assert all(s.lstrip().upper().startswith("SELECT") for s in statements)
    assert all("WHERE job_evaluations.job_id IN" in s for s in statements if "FROM job_evaluations" in s)


@pytest.mark.parametrize("kwargs",[{"tz":"invalid/zone"},{"start":NOW.date()+timedelta(days=1)},{"start":NOW.date(),"end":NOW.date()-timedelta(days=2)}])
def test_bad_date_or_timezone_rejected(db,kwargs):
    with pytest.raises(HTTPException):read(db,**kwargs)


def test_manual_email_assessment_requires_confirmed_single_identity(db):
    from backend.app.db.models import GmailConnectionRecord
    key=app(db,1)
    other=app(db,2,age=150)  # Outside the selected window.
    conn=GmailConnectionRecord(owner_id=1,email="fictional@example.test",encrypted_refresh_token=b"",scope="gmail.readonly",state="disconnected")
    db.add(conn);db.flush()
    message=GmailMessageRecord(connection_id=conn.id,gmail_id="fictional",received_at=NOW-timedelta(days=35),sender="fictional@example.test",subject="Fictional OA",snippet="",classification="online_assessment",decision="manual",selected_application_key=key,decision_reason="Owner confirmed",parser_version="fixture")
    db.add(message);db.flush()
    outcome(db,key,"manual_correction",gmail_message_id=message.id,new_status="screening")
    d=read(db)
    assert d["assessments"]==1
    outcome(db,other,"manual_correction",gmail_message_id=message.id,new_status="screening")
    d=read(db,start=NOW.date()-timedelta(days=90))
    assert d["assessments"]==0  # A single message never counts for two identities.


def test_company_year_is_not_aggregated_across_incomplete_legal_entities(db):
    app(db,1)
    report(db)
    incomplete=report(db,approvals=4,denials=None,version="second-entity")
    incomplete.legal_entity="Fictional Subsidiary"
    d=read(db)
    assert len(d["reports"])==2
    assert not d["annual"]


def test_inbox_deep_link_filters_before_latest_100_and_keeps_connections_private(db):
    from backend.app.api.routers.inbox import _message_rows
    from backend.app.db.models import GmailConnectionRecord
    conn=GmailConnectionRecord(owner_id=1,email="fictional@example.test",encrypted_refresh_token=b"",scope="gmail.readonly",state="disconnected")
    db.add(conn);db.flush()
    for index in range(102):
        db.add(GmailMessageRecord(connection_id=conn.id,gmail_id=f"filtered-{index}",received_at=NOW-timedelta(days=index),sender="fictional@example.test",subject="Fictional message",snippet="",classification="unknown",decision="review" if index==101 else "ignored",candidate_keys=["job:1","job:2"] if index==101 else [],decision_reason="Fictional fixture",parser_version="fixture"))
    db.flush()
    assert all(row.decision=="ignored" for row in _message_rows(db,conn.id))
    assert len(_message_rows(db,conn.id,"review"))==1
    assert len(_message_rows(db,conn.id,"ambiguous"))==1
    assert not _message_rows(db,conn.id+1,"review")
    with pytest.raises(HTTPException):_message_rows(db,conn.id,"unsupported")


def test_application_drilldowns_match_chart_filters_and_remain_unique(db):
    key=app(db,1,age=40,status="screening")
    other=app(db,2,age=5,status="applied",company="Other Fiction")
    outcome(db,key,"online_assessment");outcome(db,key,"online_assessment")
    d=read(db,records=True,evidence="online_assessment",eligible=True)
    assert d["record_total"]==1 and [row["key"] for row in d["records"]]==[key]
    assert d["records"][0]["event_types"]==["online_assessment"]
    assert d["records"][0]["href"].startswith("/app/jobs/")
    assert read(db,records=True,status="applied")["records"][0]["key"]==other
    assert read(db,records=True,company="Other Fiction")["record_total"]==1
    assert read(db,records=True,limit=1,offset=1)["record_total"]==2
    assert len(read(db,records=True,limit=1,offset=1)["records"])==1
    with pytest.raises(HTTPException):read(db,records=True,status="silently_rejected")


def test_rejected_companies_lists_every_employer_once_newest_rejection_first(db):
    first=app(db,1,company="Silverpine Labs");app(db,2,company="Silverpine Labs",status="rejected")
    outcome(db,first,"rejection",stamp=NOW-timedelta(days=5))
    app(db,3,company="Northwind Robotics",status="rejected");app(db,6,company="Northwind Robotics",status="rejected")
    app(db,7,company="Northwind Robotics",status="screening")
    app(db,4,company="Bluefin Analytics")
    app(db,5,company="Aster Fiction",status="rejected")
    d=read(db)
    assert d["rejected_companies"]==[
        {"name":"Silverpine Labs","rejections":2,"applications":2,"dated":1,"roles":["Fictional software role"],"in_progress":0,
         "latest_at":(NOW-timedelta(days=5)).isoformat()},
        # Undated ones follow, most rejections first, then by name.
        {"name":"Northwind Robotics","rejections":2,"applications":3,"dated":0,"roles":["Fictional software role"],"in_progress":1,"latest_at":None},
        {"name":"Aster Fiction","rejections":1,"applications":1,"dated":0,"roles":["Fictional software role"],"in_progress":0,"latest_at":None}]
    assert d["rejection_summary"]=={"applications":5,"companies":3,"dated":1,"latest_at":(NOW-timedelta(days=5)).isoformat()}
    empty=read(db,start=NOW.date()-timedelta(days=10),end=NOW.date()-timedelta(days=1))
    assert empty["rejected_companies"]==[] and empty["rejection_summary"]["applications"]==0


def test_rejected_records_search_dates_and_link_the_email(db):
    from backend.app.db.models import GmailConnectionRecord
    early=app(db,1,company="Silverpine Labs");late=app(db,2,company="Northwind Robotics")
    db.get(JobRecord,int(late.split(":")[1])).title="Platform Engineer"
    app(db,3,company="Bluefin Analytics",status="rejected")
    conn=GmailConnectionRecord(owner_id=1,email="fictional@example.test",encrypted_refresh_token=b"",scope="gmail.readonly",state="disconnected")
    db.add(conn);db.flush()
    mail=GmailMessageRecord(connection_id=conn.id,gmail_id="fictional-rejection",received_at=NOW-timedelta(days=2),sender="fixture@example.test",subject="Fictional update",snippet="",classification="rejection",decision="automatic",selected_application_key=late,decision_reason="Fictional fixture",parser_version="fixture")
    db.add(mail);db.flush()
    outcome(db,early,"rejection",stamp=NOW-timedelta(days=9))
    row=outcome(db,late,"rejection",stamp=NOW-timedelta(days=2),gmail_message_id=mail.id);row.actor="verified_automation"
    d=read(db,records=True,evidence="rejection")
    # Newest rejection first; a status without an email date comes last.
    assert [r["key"] for r in d["records"]][:2]==[late,early] and d["record_total"]==3
    assert d["records"][0]["evidence"]==[{"kind":"rejection","at":(NOW-timedelta(days=2)).isoformat(),"message_id":mail.id}]
    assert d["records"][2]["evidence"]==[{"kind":"rejection","at":None,"message_id":None}]
    found=read(db,records=True,evidence="rejection",q="  northwind   PLATFORM ")
    assert [r["key"] for r in found["records"]]==[late] and found["record_query"]=="northwind platform"
    assert read(db,records=True,evidence="rejection",q="northwind data")["record_total"]==0
    assert read(db,records=True,q=late)["record_total"]==1  # The record key is searchable too.
