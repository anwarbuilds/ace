"""Owner-approved bounded classification/filing, with no application updates.

Default preview enforces read-only PostgreSQL. Supply an explicit private cohort,
then separately review the full plan and supply its seal for apply or rollback.
No mailbox discovery, global historical enablement or stored full mail bodies.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import traceback

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.app.api.routers import inbox
from backend.app.config import get_settings
from backend.app.db.models import GmailConnectionRecord as Connection, GmailMessageRecord as Mail, ApplicationEventRecord as Event
from backend.app.inbox import reconcile as reader
from backend.app.inbox import historical_cleanup as cleanup
from backend.app.inbox import postings, queue, company_outcomes, filed_evidence
from backend.scripts.inbox_classification_audit import private_write


def source_hash():
    files = {name: module.__file__ for name, module in [('reader', reader), ('inbox', inbox), ('cleanup', cleanup), ('postings', postings), ('queue', queue), ('company_outcomes', company_outcomes), ('filed_evidence', filed_evidence)]}
    files['operator'] = __file__
    return cleanup.digest({name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for name, path in files.items()})


def seal(plan):
    return cleanup.digest({key: plan[key] for key in ('source', 'manifest', 'grant', 'entries')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('preview', 'apply', 'rollback'), default='preview')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--limit', type=int, choices=range(1, 51), default=25)
    parser.add_argument('--approved-plan-sha256')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest.get('scope') != 'historical_classification_only':
        parser.error('Only an explicitly approved classification-only cohort is supported')
    ids = manifest['message_ids']
    operation = manifest['operation']
    if (not ids or len(ids) != len(set(ids)) or not all(isinstance(i, int) and i > 0 for i in ids)
            or not operation.isalnum() or len(operation) > 40):
        parser.error('Invalid explicit cohort or operation identifier')
    settings = get_settings()
    if not settings.database_url.startswith('postgresql'):
        parser.error('Operator requires PostgreSQL')
    if Path(__file__).resolve().parents[2] in args.plan.resolve().parents:
        parser.error('Private plans must be outside the source checkout')
    writing = args.mode != 'preview'
    if writing and not args.approved_plan_sha256:
        parser.error('Writing requires the separately reviewed plan seal')
    plan = json.loads(args.plan.read_text()) if args.plan.exists() else {
        'source': source_hash(), 'manifest': cleanup.digest(manifest), 'entries': {}, 'applied': {}, 'reverted': {}}
    if plan['source'] != source_hash() or plan['manifest'] != cleanup.digest(manifest):
        parser.error('Source or authorized cohort changed; prepare a new plan')
    if writing and (set(map(int, plan['entries'])) != set(ids) or seal(plan) != args.approved_plan_sha256):
        parser.error('A complete reviewed plan with matching seal is required')
    options = '-c jit=off' + ('' if writing else ' -c default_transaction_read_only=on')
    engine = create_engine(settings.database_url, connect_args={'options': options})
    try:
        with Session(engine) as db:
            if not writing:
                assert db.scalar(text('SHOW transaction_read_only')) == 'on'
            conn = db.get(Connection, manifest['connection_id'])
            if not conn or conn.state != 'ready' or not conn.encrypted_refresh_token:
                raise ValueError('Gmail is not ready')
            grant = hashlib.sha256(bytes(conn.encrypted_refresh_token)).hexdigest()
            if plan.get('grant', grant) != grant:
                raise ValueError('Gmail grant changed')
            plan['grant'] = grant
            def active():
                with Session(engine) as control:
                    current = control.get(Connection, conn.id)
                    return bool(current and current.state == 'ready' and hashlib.sha256(bytes(current.encrypted_refresh_token)).hexdigest() == grant)
            completed = plan['entries'] if not writing else plan['applied' if args.mode == 'apply' else 'reverted']
            token = inbox._access(conn) if args.mode != 'rollback' else None
            for mid in [mid for mid in ids if str(mid) not in completed][:args.limit]:
                key = str(mid)
                assert active(), 'Gmail pause or disconnect stops the operator'
                row = db.get(Mail, mid)
                if not row or row.connection_id != conn.id:
                    raise ValueError('Cohort ownership mismatch')
                if args.mode == 'rollback':
                    event = cleanup.revert_prepared(db, conn, plan['entries'][key], operation)
                    assert active()
                    db.commit()
                    plan['reverted'][key] = event.id
                elif args.mode == 'apply' and db.scalar(select(Event.id).where(Event.dedupe_key == cleanup.event_key(conn, row, operation))):
                    # Recover a commit that preceded the local journal write.
                    event = cleanup.apply_prepared(db, conn, plan['entries'][key], plan['entries'][key], operation)
                    db.rollback()
                    plan['applied'][key] = event.id
                else:
                    if not cleanup.eligible(db, row):
                        raise ValueError('Owner decision or recorded evidence is protected')
                    data = inbox._scoped_detail(row.gmail_id, token, active)
                    assert active(), 'Gmail pause or disconnect stops the operator'
                    if {'SPAM', 'TRASH'}.intersection(data.get('labelIds', [])):
                        raise ValueError('Evidence moved outside eligible Gmail scope')
                    # Release the pre-network transaction; reconcile against fresh
                    # owner/application rows before the short write transaction.
                    db.rollback()
                    conn = db.get(Connection, manifest['connection_id'])
                    row = db.get(Mail, mid)
                    fresh = cleanup.projection(db, conn, row, data)
                    del data
                    if writing:
                        event = cleanup.apply_prepared(db, conn, plan['entries'][key], fresh, operation)
                        db.refresh(conn, with_for_update=True)
                        if conn.state != 'ready' or hashlib.sha256(bytes(conn.encrypted_refresh_token)).hexdigest() != grant:
                            raise ValueError('Gmail was paused or disconnected')
                        db.commit()
                        plan['applied'][key] = event.id
                    else:
                        plan['entries'][key] = fresh
                        db.rollback()
                    time.sleep(.8)
                plan['observed_at'] = datetime.now(timezone.utc).isoformat()
                private_write(args.plan, plan)
            db.rollback()
        entries = list(plan['entries'].values())
        result = {'prepared': len(entries), 'cohort': len(ids), 'applied': len(plan['applied']),
                  'reverted': len(plan['reverted']), 'pending_after': sum(e['patch']['decision'] in inbox.PENDING for e in entries),
                  'categories': dict(Counter(e['reading'] for e in entries)),
                  'remaining_reasons': dict(Counter(e['patch']['decision_reason'] for e in entries if e['patch']['decision'] in inbox.PENDING)),
                  'status_changes': 0, 'outcome_records': 0, 'seal': seal(plan)}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        # Never print SQL parameters, credentials or real mail contents.
        frame = traceback.extract_tb(exc.__traceback__)[-1]
        print(json.dumps({'error': type(exc).__name__, 'mode': args.mode, 'complete': False,
                          'location': f'{Path(frame.filename).name}:{frame.lineno}:{frame.name}'}))
        return 2
    finally:
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
