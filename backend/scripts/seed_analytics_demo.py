"""Rich fictional Analytics fixture, confined to a named disposable /tmp SQLite file.

All submissions, events and petition counts here are invented test data. They
are never imported into a real ACE database. Employer icons may be checked via
an explicitly fictional external application to a known brand.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.scripts.seed_demo import seed
from backend.app.db.models import ApplicationEventRecord, CompanyPetitionReportRecord, ExternalApplicationRecord, GmailConnectionRecord, GmailMessageRecord, JobMarkRecord, JobRecord
from backend.app.inbox.filed_evidence import ACTION_PREFIX
from backend.app.inbox.reconcile import PARSER_VERSION

DATABASE = Path("/tmp/ace-analytics-fictional.db")


def main():
    url = f"sqlite:///{DATABASE}"
    seed(url)
    now = datetime.now(timezone.utc)
    engine = create_engine(url)
    with Session(engine) as session:
        jobs = session.scalars(select(JobRecord).order_by(JobRecord.id).limit(145)).all()
        # Increasing recent submissions, older cohorts and varied real stages.
        for i, job in enumerate(jobs):
            stamp = now - timedelta(days=(i * 7) % 86, hours=i % 8)
            mark = session.get(JobMarkRecord, job.id)
            if mark is None:
                mark = JobMarkRecord(job_id=job.id)
                session.add(mark)
            mark.applied_at = stamp
            kind = "online_assessment" if i % 11 == 0 else "interview" if i % 13 == 0 else "rejection" if i % 7 == 0 else "recruiter_reply" if i % 9 == 0 else None
            mark.application_status = {"online_assessment":"screening", "interview":"interviewing", "rejection":"rejected", "recruiter_reply":"screening"}.get(kind,"ghosted" if i % 19 == 0 else "applied")
            mark.status_changed_at = min(now,stamp+timedelta(days=3))
            if kind and stamp < now-timedelta(days=10):
                session.add(ApplicationEventRecord(application_key=f"job:{job.id}",kind=kind,new_status=mark.application_status,actor="owner",reason="Fictional screenshot fixture, manually confirmed",occurred_at=stamp+timedelta(days=2+i%18),dedupe_key=f"analytics-fixture:{job.id}:{kind}"))
        session.flush()
        companies=list(dict.fromkeys(job.company for job in jobs))[:5]
        for i,name in enumerate(companies):
            for year in range(2021,2026):
                session.add(CompanyPetitionReportRecord(ace_company=name,legal_entity=f"{name} Fictional Legal Entity",source_name="USCIS fixture (fictional counts)",source_uri="https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub",metric_definition="USCIS I-129 petition decisions",period=f"FY {year}",report_version="fictional-test-only",petition_approvals=80+(year-2021)*17+i*11,petition_denials=4+i*3+(year%3)*2,entity_verified=True,first_seen_at=now,last_checked_at=now))
        session.add(ExternalApplicationRecord(company="Google",title="Fictional application for local logo verification",match_key="fictional-google-logo-fixture",applied_at=now-timedelta(days=45),application_status="applied",url="https://www.google.com"))
        # Disconnected grant with retained fictional evidence exercises an honest
        # not-connected banner while still allowing review of historical records.
        conn=GmailConnectionRecord(owner_id=1,email="inbox-fixture@example.test",encrypted_refresh_token=b"",scope="https://www.googleapis.com/auth/gmail.readonly",state="disconnected")
        session.add(conn);session.flush()
        for i,decision in enumerate(["review","review","exact_preview","manual"]):
            session.add(GmailMessageRecord(connection_id=conn.id,gmail_id=f"fictional-{i}",thread_id=f"thread-{i}",received_at=now-timedelta(days=i),sender="recruiter@fictional.example",subject=f"Fictional recruiting evidence {i}",snippet="Fictional evidence used only for local browser validation",classification="interview",decision=decision,candidate_keys=[f"job:{jobs[0].id}",f"job:{jobs[1].id}"] if i==0 else [f"job:{jobs[2].id}"],decision_reason="Fictional candidate review",parser_version="fixture"))
        # Classified meaning remains visible without inventing application
        # attribution, an outstanding task, or a confirmed stage transition.
        for i, kind in enumerate(("online_assessment", "interview", "offer")):
            session.add(GmailMessageRecord(
                connection_id=conn.id, gmail_id=f"fictional-classified-{kind}",
                thread_id=f"fictional-classified-thread-{kind}",
                received_at=datetime(2026,7,1,7,tzinfo=timezone.utc) if i==0 else now-timedelta(days=4+i), sender="talent@fictional.example",
                subject=f"Fictional {kind.replace('_', ' ')} email history",
                snippet="Invented employer evidence for hosted UI validation only.",
                classification=kind, decision="update", candidate_keys=[],
                selected_application_key=None,
                decision_reason=ACTION_PREFIX+"The fictional application identity is not verified.",
                parser_version=PARSER_VERSION))
        session.add(GmailMessageRecord(
            connection_id=conn.id, gmail_id="fictional-classified-before-july",
            thread_id="fictional-classified-before-july-thread",
            received_at=datetime(2026,7,1,6,59,tzinfo=timezone.utc),
            sender="talent@fictional.example", subject="Fictional pre-July offer history",
            snippet="Invented older offer evidence retained for boundary validation.",
            classification="offer", decision="update", candidate_keys=[],
            selected_application_key=None,
            decision_reason=ACTION_PREFIX+"The fictional application identity is not verified.",
            parser_version=PARSER_VERSION))
        session.add(GmailMessageRecord(
            connection_id=conn.id, gmail_id="fictional-owner-receipt",
            thread_id="fictional-owner-receipt-thread",
            received_at=now-timedelta(days=2), sender="talent@fictional.example",
            subject="Fictional owner receipt feedback",
            snippet="Thank you for applying. Your application was received.",
            classification="offer", decision="receipt", candidate_keys=[],
            selected_application_key=None,
            decision_reason="You marked it an application receipt", parser_version="2"))
        session.commit()
    print("Fictional Analytics fixture ready at /tmp/ace-analytics-fictional.db")


if __name__ == "__main__":
    main()
