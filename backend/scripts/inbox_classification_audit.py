"""Read-only classification dry-run. No sync, recheck, status or event writes.

Default: preview retained excerpts as incomplete evidence. --read-bodies uses
only the existing read-only grant, a completed all-date job-mail ID selection,
label preflight, <=50 paced reads per invocation and a private resume report.
The report is an audit artifact, never an application queue or second database.
Production execution requires the owner's authorization for that operation.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db.models import GmailConnectionRecord, GmailMessageRecord, ApplicationEventRecord
from backend.app.api.routers.inbox import _identities, _access, _scoped_detail, _message_evidence, _thread_keys, _stale_query
from backend.app.inbox import gmail
from backend.app.inbox.queue import projected_decision, PENDING
from backend.app.inbox.reconcile import EmailEvidence, PARSER_VERSION, read_intent, reassess
from backend.app.inbox.evaluation import evaluate


def preview(row, evidence, applications, account=None, *, protected=True, thread_keys=()):
    reading = read_intent(evidence)
    decision = reassess(evidence, applications, row.classification, account, thread_keys=thread_keys, previous_reason=row.decision_reason)
    # Historical positives always remain confirmation-only. This is a proposal,
    # never a call to _apply. Protected rows cannot change, including owner Undo.
    disposition = 'review' if decision.disposition=='verified' else decision.disposition
    record_outcome = not protected and decision.disposition=='verified' and decision.classification=='rejection'
    status_change = record_outcome and any(app.key==decision.target and app.current_status!='rejected' for app in applications)
    if record_outcome and get_settings().gmail_auto_rejections:
        disposition = 'automatic'
    else:
        status_change = False
        record_outcome = False
    return {'message_id':row.id, 'current_classification':row.classification,
            'current_decision':projected_decision(row), 'classification':decision.classification, 'current_body_classification':reading.classification,
            'proposed_decision':projected_decision(row) if protected else disposition,
            'reason':decision.reason, 'classification_reason':reading.explanation, 'excerpt':reading.excerpt,
            'complete':evidence.complete, 'variant':reading.variant, 'protected':protected,
            'target':decision.matched_target, 'would_change_status':status_change, 'would_record_outcome':record_outcome,
            'review_required':(projected_decision(row) if protected else disposition) in PENDING}


def summary(rows):
    pending = [r for r in rows if r['current_decision'] in PENDING]
    return {'audited':len(rows), 'pending_audited':len(pending),
            'pending_after_proposal':sum(r['review_required'] for r in pending),
            'proposed_categories':dict(Counter(r['classification'] for r in rows)),
            'remaining_reasons':dict(Counter(r['reason'] for r in pending if r['review_required'])),
            'would_change_status':sum(r['would_change_status'] for r in rows),
            'would_record_outcome':sum(r['would_record_outcome'] for r in rows),
            'protected':sum(r['protected'] for r in rows), 'partial':sum(not r['complete'] for r in rows),
            'changes':dict(Counter(r['current_classification']+' -> '+r['classification'] for r in rows)),
            'reference_evaluation':evaluate(rows),
            'mailbox_recall_certified':False,'independent_multicategory_accuracy_certified':False}


def private_write(path: Path, value):
    if path.is_symlink():
        raise ValueError('Refusing a symlink report')
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if path.parent.stat().st_mode & 0o077:
        raise ValueError('Private report directory must have mode 700')
    temporary=path.with_suffix('.partial')
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2,sort_keys=True)
    temporary.replace(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read-bodies',action='store_true')
    parser.add_argument('--limit',type=int,default=25,choices=range(1,51))
    parser.add_argument('--private-report',type=Path,required=True)
    args=parser.parse_args()
    settings=get_settings()
    if not settings.database_url.startswith('postgresql'):
        parser.error('CLI requires enforced read-only PostgreSQL; unit tests use fictional SQLite')
    if Path(__file__).resolve().parents[2] in args.private_report.resolve().parents:
        parser.error('Private reports must stay outside the source checkout')
    engine=create_engine(settings.database_url,connect_args={'options':'-c default_transaction_read_only=on -c jit=off'},isolation_level='REPEATABLE READ')
    try:
        report=json.loads(args.private_report.read_text()) if args.private_report.exists() else {'parser':PARSER_VERSION,'rows':[]}
        if report['parser']!=PARSER_VERSION:raise ValueError('Resume report has another parser')
        with Session(engine) as db:
            conn=db.scalar(select(GmailConnectionRecord))
            if not conn or conn.state!='ready' or not conn.encrypted_refresh_token:
                raise ValueError('No ready connection')
            grant=hashlib.sha256(bytes(conn.encrypted_refresh_token)).hexdigest()
            if report.get('grant',grant)!=grant:raise ValueError('Grant changed; start a new report')
            report['grant']=grant
            applications=_identities(db)
            messages=list(db.scalars(select(GmailMessageRecord).where(GmailMessageRecord.connection_id==conn.id)))
            stale_ids=set(db.scalars(_stale_query(conn.id).with_only_columns(GmailMessageRecord.id)))
            if args.read_bodies:
                token=_access(conn)
                if 'scope_ids' not in report:
                    ids,complete=gmail.list_message_ids(token,gmail.job_query(),max_pages=5)
                    if not complete:raise ValueError('Scope exceeds bounded listing; no body reads authorized from a partial list')
                    report['scope_ids']=ids
            scope=set(report.get('scope_ids',[]))
            done={r['message_id'] for r in report['rows']}
            # Owner-recorded outcomes provide a narrow independent reference.
            # Filing as an acknowledgement is a policy choice, not a gold label.
            owner_events=list(db.scalars(select(ApplicationEventRecord).where(ApplicationEventRecord.actor=='owner')))
            undone={e.undo_of_id for e in db.scalars(select(ApplicationEventRecord).where(ApplicationEventRecord.undo_of_id.is_not(None)))}
            references={}
            for event in owner_events:
                if event.id not in undone and event.gmail_message_id and event.new_status in {'rejected','interviewing','offer'}:
                    references[event.gmail_message_id]={'rejected':'rejection','interviewing':'interview','offer':'offer'}[event.new_status]
            selected=[m for m in messages if m.id not in done and (projected_decision(m) in PENDING or m.id in references)
                      and (not args.read_bodies or m.gmail_id in scope)]
            selected.sort(key=lambda m:hashlib.sha256(m.gmail_id.encode()).digest())
            for row in selected[:args.limit]:
                data={}
                if args.read_bodies:
                    # Refresh pause/grant with a separate read transaction; the
                    # report snapshot remains stable while network access runs.
                    def active():
                        with Session(engine) as control:
                            current=control.get(GmailConnectionRecord,conn.id)
                            return bool(current and current.state=='ready' and hashlib.sha256(bytes(current.encrypted_refresh_token)).hexdigest()==grant)
                    if not active():break
                    data=_scoped_detail(row.gmail_id,token,active)
                    if not active():break
                    if {'SPAM','TRASH'}.intersection(data.get('labelIds',[])):
                        report.setdefault('excluded',[]).append(row.id)
                        continue
                    ev=_message_evidence(data)
                else:
                    ev=EmailEvidence(row.sender,row.subject,row.snippet,row.received_at,complete=False)
                result=preview(row,ev,applications,conn.email,protected=row.id not in stale_ids,
                               thread_keys=_thread_keys(db,conn,data,ev,applications))
                if row.id in references:result['expected_classification']=references[row.id]
                report['rows'].append(result)
                report['observed_at']=datetime.now(timezone.utc).isoformat()
                private_write(args.private_report,report)
                if args.read_bodies:time.sleep(.8)
            db.rollback()
        output=summary(report['rows'])
        report['summary']=output
        private_write(args.private_report,report)
        print(json.dumps(output,indent=2,sort_keys=True))
        return 0
    except Exception as exc:
        # Tracebacks can contain SQL parameters or Gmail contents.
        print(json.dumps({'error':type(exc).__name__,'complete':False,'writes':0}))
        return 2
    finally:engine.dispose()

if __name__=='__main__':raise SystemExit(main())
