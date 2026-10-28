"""Focused job-mail triage regressions. Entirely fictional, no external reads."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from backend.app.api.routers import inbox
from backend.app.api.routers.analytics import analytics_read
from backend.app.db.models import GmailMessageRecord
from backend.app.inbox import gmail
from backend.app.inbox.queue import decision_expression, projected_decision
from backend.app.inbox.reconcile import EmailEvidence, reconcile, UNCLEAR_REASON, PARTIAL_REASON, PARSER_VERSION
from backend.app.inbox.company_outcomes import KIND, event_company
from backend.tests.test_inbox_persistence import (database, gmail_reads, message, stored, row_for,
    statuses, job_events, company_events, owner_request, verified_scope, NOW)


def finish(session, conn):
    for _ in range(20):
        result = inbox.sync_once(session, conn)
        if not result["more"]:return result
    raise AssertionError("Scoped scan failed to finish")


@pytest.mark.parametrize("label", ["SPAM", "TRASH"])
def test_label_preflight_avoids_excluded_body_and_retains_existing_evidence(database, gmail_reads, monkeypatch, label):
    session,conn=database
    old=stored(session,conn,"moved-job","review","Application update",version="7")
    old.classification="rejection";session.commit()
    verified_scope(session,conn)
    calls=[]
    def get(path,token,params):
        calls.append(params["format"])
        assert params["format"]=="minimal", "Excluded body must not be fetched"
        return {"id":"moved-job","labelIds":[label]}
    monkeypatch.setattr(gmail,"get_json",get)
    result=inbox.recheck(inbox.RecheckRequest(),owner_request(),session)
    assert result["scope_pending"] and calls==["minimal"]
    session.refresh(old)
    assert old.parser_version=="7" and old.decision=="review" and old.classification=="rejection"
    assert statuses(session)==["applied"]*3 and not job_events(session)


def test_history_personal_additions_and_spam_moves_use_scoped_listing_without_body_reads(database,gmail_reads,monkeypatch):
    session,conn=database
    selection=["old-archived-job"]
    calls=[];phase=0
    def get(path,token,params=None):
        calls.append((path,params))
        if path=="/profile":return {"historyId":"baseline"}
        if path=="/messages":
            assert params["q"]==gmail.job_query() and params["includeSpamTrash"]=="false"
            assert "after:" not in params["q"]
            return {"messages":[{"id":key} for key in selection]}
        if path=="/history":
            return {"historyId":"new-snapshot" if phase else "initial-snapshot", "history": [] if not phase else [{
                "messagesAdded":[{"message":{"id":"ordinary-personal"}},{"message":{"id":"new-job"}}],
                "labelsAdded":[{"message":{"id":"old-archived-job"},"labelIds":["TRASH"]}]}]}
        key=path.rsplit("/",1)[-1]
        assert key in selection and key!="ordinary-personal"
        return message(key,"Thank you for applying.", NOW-timedelta(days=2500) if key=="old-archived-job" else NOW)
    monkeypatch.setattr(gmail,"get_json",get)
    first=finish(session,conn)
    assert first["coverage"]["complete"] and row_for(session,"old-archived-job").received_at.year<2021
    selection[:]=["new-job"];phase=1
    second=finish(session,conn)
    assert second["coverage"]["gmail"]==1 and second["coverage"]["includes_spam_trash"] is False
    assert row_for(session,"old-archived-job") is not None  # Source evidence is never deleted.
    assert row_for(session,"ordinary-personal") is None
    assert len([path for path,params in calls if path=="/messages"])==2
    assert len([path for path,params in calls if path=="/history"])==2  # Continuous arrivals cannot starve progress.


def test_no_recheck_before_full_scope_and_narrow_window_is_insufficient(database,gmail_reads,monkeypatch):
    from backend.app.inbox.full_history import FullMailboxScan
    session,conn=database
    stored(session,conn,"old-job","ignored","Your application",version="7")
    inbox._FULL_SCANS[inbox._coverage_key(conn,30)]=FullMailboxScan("narrow",phase="complete",ids={"old-job"})
    monkeypatch.setattr(gmail,"get_json",lambda *a:pytest.fail("Unverified scope must not read bodies"))
    assert inbox.recheck(inbox.RecheckRequest(),owner_request(),session)["scope_pending"]
    assert inbox.messages(owner_request(),session,None,0,50)["counts"]["stale"]==0


@pytest.mark.parametrize("reason",["You undid ACE's change for this email","You undid the change this email made"])
def test_both_historical_undo_reasons_are_protected(database,gmail_reads,monkeypatch,reason):
    session,conn=database
    row=stored(session,conn,"undo-history","review","Your application",version="1",reason=reason)
    row.classification="unclear";session.commit();verified_scope(session,conn)
    monkeypatch.setattr(gmail,"get_json",lambda *a:pytest.fail("Owner Undo must not be re-read"))
    assert inbox.recheck(inbox.RecheckRequest(),owner_request(),session)["checked"]==0
    assert projected_decision(row)=="review"


def test_sql_python_api_and_analytics_queue_agree_without_hiding_old_outcomes(database):
    session,conn=database
    cases=[("unclear","review",UNCLEAR_REASON,"update"),("rejection","review","Email predates application","review"),
        ("online_assessment","review","No application could be matched with confidence","review"),
        ("unclear","review",PARTIAL_REASON,"review"),("unclear","deferred",UNCLEAR_REASON,"deferred"),
        ("unclear","manual",UNCLEAR_REASON,"manual"),("unknown","review","Fictional ambiguity","review"),
        ("unclear","review","","review"),("unclear","update","You marked it an application update","update")]
    expected={}
    for i,(kind,decision,reason,projected) in enumerate(cases):
        row=stored(session,conn,f"projection-{i}",decision,"Your application",version="7")
        row.classification=kind;row.decision_reason=reason;row.received_at=NOW-timedelta(days=2500)
        expected[row.id]=projected
    session.commit()
    sql=dict(session.execute(select(GmailMessageRecord.id,decision_expression())).all())
    assert sql==expected=={row.id:projected_decision(row) for row in session.scalars(select(GmailMessageRecord))}
    # This exact expression also compiles for PostgreSQL; live read-only preview executes it there.
    assert "CASE WHEN" in str(decision_expression().compile(dialect=postgresql.dialect()))
    pending=sum(value in inbox.PENDING for value in expected.values())
    api=inbox.messages(owner_request(),session,"pending",0,2)
    second=inbox.messages(owner_request(),session,"pending",2,100)
    assert api["review_count"]==api["total"]==pending
    assert len({m["id"] for m in api["items"]+second["items"]})==pending
    analytics=analytics_read(session,days="all")
    assert sum(analytics["review"][key] for key in ("needs_review","exact_preview","deferred"))==pending
    updates=inbox.messages(owner_request(),session,"update",0,100)
    assert updates["total"]==2 and api["counts"]["reviewed"]==1  # Saved correspondence never claims owner review.
    assert all(m["received_at"].startswith(str((NOW-timedelta(days=2500)).year)) for m in second["items"])


@pytest.mark.parametrize("subject",["Verify your account","Your job recommendations","Password reset"])
@pytest.mark.parametrize("body,kind",[("Req ID: SE-101. We have decided not to proceed with your application.","rejection"),
    ("Req ID: SE-101. We invite you to interview.","interview"),
    ("Req ID: SE-101. Please complete the online assessment.","online_assessment")])
def test_routine_subject_cannot_hide_an_explicit_body_outcome(database,subject,body,kind):
    session,conn=database
    data=message("outcome-under-generic-subject",body)
    data["payload"]["headers"][2]["value"]=subject
    result=inbox._ingest(session,conn,data,inbox._identities(session),preview=True)
    assert result in {"automatic","exact_preview"}
    assert row_for(session,data["id"]).classification==kind


@pytest.mark.parametrize("subject,body",[("HackerRank account verification","Verify your email to use HackerRank."),
    ("Your CodeSignal report","Your practice score is ready."),
    ("Weekly career digest","New jobs for you from HireVue and CodeSignal.")])
def test_bare_assessment_brands_do_not_create_outcomes_or_review_tasks(subject,body):
    result=reconcile(EmailEvidence("news@codesignal.com",subject,body,NOW),[])
    assert result.classification=="unknown" and result.disposition=="ignored"


def test_legacy_unclear_in_scope_is_actually_reread_and_can_record_a_missed_outcome(database,gmail_reads,monkeypatch):
    session,conn=database
    row=stored(session,conn,"legacy-unclear","review","Your application",version="7",reason=UNCLEAR_REASON)
    row.classification="unclear";session.commit();verified_scope(session,conn)
    assert projected_decision(row)=="update"
    monkeypatch.setattr(gmail,"get_json",lambda path,*a:message("legacy-unclear","Req ID: SE-101. You have not been selected."))
    result=inbox.recheck(inbox.RecheckRequest(),owner_request(),session)
    assert result["counts"]=={"automatic":1} and row.parser_version==PARSER_VERSION
    assert statuses(session)==["applied","rejected","applied"] and len(job_events(session))==1


def test_exact_thread_receipt_resolves_only_matching_rejection_and_preserves_undo(database):
    session,conn=database
    receipt=message("thread-receipt","Req ID: SE-101. Thank you for applying.",NOW-timedelta(hours=2))
    assert inbox._ingest(session,conn,receipt,inbox._identities(session),preview=True)=="receipt"
    outcome=message("thread-rejection","We have decided to move forward with other candidates.")
    assert inbox._ingest(session,conn,outcome,inbox._identities(session),preview=True)=="automatic"
    assert statuses(session)==["applied","rejected","applied"]
    inbox.undo(job_events(session)[0].id,owner_request(),session)
    assert statuses(session)==["applied"]*3


@pytest.mark.parametrize("variant",["conflicting_receipt","different_sender","different_id","positive","historical"])
def test_thread_hint_never_overrides_conflicts_or_positive_and_date_guards(database,variant):
    session,conn=database
    inbox._ingest(session,conn,message("anchor","Req ID: SE-101. Thank you for applying.",NOW-timedelta(hours=2)),inbox._identities(session),preview=True)
    if variant=="conflicting_receipt":
        inbox._ingest(session,conn,message("anchor-2","Req ID: SE-102. Thank you for applying.",NOW-timedelta(hours=1)),inbox._identities(session),preview=True)
    body="We have decided to move forward with other candidates."
    if variant=="different_id":body="Req ID: SE-999. "+body
    if variant=="positive":body="We invite you to interview."
    data=message("guarded-thread",body,NOW-timedelta(days=2500) if variant=="historical" else NOW)
    if variant=="different_sender":data["payload"]["headers"][1]["value"]="other@careers.silverpine.example"
    assert inbox._ingest(session,conn,data,inbox._identities(session),preview=True)==("review" if variant=="positive" else KIND)
    assert statuses(session)==["applied"]*3 and not job_events(session)
    if variant!='positive':
        assert row_for(session,'guarded-thread').selected_application_key is None
        assert [event_company(event) for event in company_events(session)]==['Silverpine Labs']
    else:
        assert not company_events(session)


@pytest.mark.parametrize("exact",[True,False])
def test_only_new_scoped_history_additions_can_automate_opted_in_exact_positives(database,gmail_reads,monkeypatch,exact):
    session,conn=database
    live=False
    def get(path,token,params=None):
        if path=="/profile":return {"historyId":"before-initial"}
        if path=="/messages":return {"messages":[{"id":"live-positive"}] if live else []}
        if path=="/history":return {"historyId":"after-live" if live else "after-initial", "history":
            [{"messagesAdded":[{"message":{"id":"live-positive"}}]}] if live else []}
        return message("live-positive",("Req ID: SE-101. " if exact else "")+"We invite you to interview.")
    monkeypatch.setattr(gmail,"get_json",get)
    assert finish(session,conn)["coverage"]["complete"]
    live=True
    assert finish(session,conn)["coverage"]["complete"]
    assert row_for(session,"live-positive").decision==("automatic" if exact else "review")
    assert statuses(session)==["applied","interviewing" if exact else "applied","applied"]


@pytest.mark.parametrize("body,kind",[
    ("We will not proceed with your application.","rejection"),
    ("We cannot continue with your candidacy.","rejection"),
    ("We regret the outcome of your application review.","possible_rejection"),
    ("There has been a decision on your application involving other candidates.","possible_rejection"),
])
def test_outcome_like_wording_without_a_receipt_opening_cannot_become_passive(body,kind):
    from backend.tests.test_inbox_reconciliation import app
    evidence=EmailEvidence("talent@careers.silverpine.example","Application update",body,NOW,True)
    decision=reconcile(evidence,[app("job:1","SE-101")])
    assert decision.classification==kind and decision.disposition in {"review","verified"}


def test_ordinary_application_progress_without_an_outcome_is_still_saved_automatically():
    evidence=EmailEvidence("talent@careers.silverpine.example","Application update",
        "Your application for the Software Engineer role is still being compared with other candidates.",NOW,True)
    assert reconcile(evidence,[]).disposition=="update"


def test_receipt_from_before_the_recorded_application_cannot_supply_thread_identity(database):
    session,conn=database
    receipt=message("old-thread-anchor","Req ID: SE-101. Thank you for applying.",NOW-timedelta(days=2500))
    assert inbox._ingest(session,conn,receipt,inbox._identities(session),preview=True)=="receipt"
    outcome=message("new-thread-rejection","We have decided to move forward with other candidates.")
    assert inbox._ingest(session,conn,outcome,inbox._identities(session),preview=True)==KIND
    assert statuses(session)==["applied"]*3 and not job_events(session)
    assert row_for(session,'new-thread-rejection').selected_application_key is None
    assert [event_company(event) for event in company_events(session)]==['Silverpine Labs']
