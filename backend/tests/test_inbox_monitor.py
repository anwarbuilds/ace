"""Background Gmail checks use fictional sessions and provider calls only."""
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

import pytest

from backend.app.api.routers import inbox
from backend.app.config import get_settings
from backend.app.db.models import GmailConnectionRecord, GmailMessageRecord
from backend.app.inbox import gmail
from backend.app.inbox.monitor import check_connections, single_monitor
from backend.tests.test_inbox_persistence import database, message, row_for, statuses, job_events


@pytest.fixture
def monitor(database, monkeypatch):
    db, conn = database
    monkeypatch.setenv('GMAIL_BACKGROUND_SYNC_ENABLED','true')
    get_settings.cache_clear()
    monkeypatch.setattr(inbox, '_settings_ready', lambda: True)
    sessions = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    return db, conn, sessions


def test_checks_ready_connections_while_page_closed_and_records_exact_outcome(monitor, monkeypatch):
    db, conn, sessions = monitor
    calls=[]
    def sync(session, connected, days, **kwargs):
        calls.append((connected.id, days))
        inbox._ingest(session, connected, message('background-new', 'Job ID: SE-101. Your application was rejected.'), inbox._identities(session), preview=False)
        session.commit()
    monkeypatch.setattr(inbox, 'sync_once', sync)
    assert check_connections(sessions) is False
    db.expire_all()
    assert calls==[(conn.id,0)]
    assert statuses(db)==['applied','rejected','applied']
    assert row_for(db,'background-new').decision=='automatic'
    assert job_events(db)[0].actor=='verified_automation'


@pytest.mark.parametrize('state', ['paused','disconnected','error'])
def test_paused_disconnected_or_failed_grants_are_not_polled(monitor,monkeypatch,state):
    db,conn,sessions=monitor
    conn.state=state;db.commit()
    monkeypatch.setattr(inbox,'sync_once',lambda *a:pytest.fail('inactive grant was read'))
    assert check_connections(sessions) is False


def test_disabled_or_stopping_worker_has_no_database_or_network_calls(monkeypatch):
    monkeypatch.setenv('GMAIL_BACKGROUND_SYNC_ENABLED','false');get_settings.cache_clear()
    assert check_connections(lambda:pytest.fail('disabled worker queried DB')) is False
    monkeypatch.setenv('GMAIL_BACKGROUND_SYNC_ENABLED','true');get_settings.cache_clear()
    assert check_connections(lambda:pytest.fail('stopping worker queried DB'),stopping=lambda:True) is False
    get_settings.cache_clear()


@pytest.mark.parametrize('error,state,limited', [
    (gmail.GmailRateLimited('fictional quota limit'),'ready',1800),
    (gmail.GmailRateLimited('fictional quota limit',retry_after=3600),'ready',3600),
    (gmail.GmailTemporaryError('fictional outage'),'ready',False),
    (gmail.GmailError('fictional expired authorization'),'error',False),
])
def test_quota_and_transient_errors_do_not_revoke_grant(monitor,monkeypatch,error,state,limited):
    db,conn,sessions=monitor
    def fail(*args, **kwargs):raise error
    monkeypatch.setattr(inbox,'sync_once',fail)
    assert check_connections(sessions) == limited
    db.expire_all()
    assert conn.state==state and conn.encrypted_refresh_token==b'fixture'
    assert conn.last_error==str(error)
    assert not list(db.scalars(select(GmailMessageRecord)))


def test_monitor_never_reclassifies_saved_evidence_or_rechecks_history(monitor,monkeypatch):
    db,conn,sessions=monitor
    inbox._ingest(db,conn,message('saved','Thank you for applying.'),inbox._identities(db),preview=True);db.commit()
    before={c.name:getattr(row_for(db,'saved'),c.name) for c in GmailMessageRecord.__table__.columns}
    monkeypatch.setattr(inbox,'_recheck_locked',lambda *a,**k:pytest.fail('history recheck invoked'))
    def duplicate(session,connected,days,**kwargs):
        assert inbox._ingest(session,connected,message('saved','Your application was rejected.'),inbox._identities(session),preview=False)=='duplicate'
        session.commit()
    monkeypatch.setattr(inbox,'sync_once',duplicate)
    check_connections(sessions);db.expire_all()
    assert {c.name:getattr(row_for(db,'saved'),c.name) for c in GmailMessageRecord.__table__.columns}==before
    assert not job_events(db)


def test_concurrent_pause_is_preserved_when_provider_fails(monitor,monkeypatch):
    db,conn,sessions=monitor
    def sync(session,connected,days,**kwargs):
        with sessions() as owner:
            owner.get(GmailConnectionRecord,connected.id).state='paused';owner.commit()
        raise gmail.GmailError('fictional expired authorization')
    monkeypatch.setattr(inbox,'sync_once',sync)
    check_connections(sessions);db.expire_all()
    assert conn.state=='paused' and conn.last_error is None


def test_pause_at_the_error_update_boundary_is_preserved_atomically(monitor,monkeypatch):
    from sqlalchemy import event
    db,conn,sessions=monitor
    engine=db.get_bind()
    def fail(*args,**kwargs):raise gmail.GmailError('fictional authorization failure')
    monkeypatch.setattr(inbox,'sync_once',fail)
    paused=[]
    def before_sql(connection,cursor,statement,parameters,context,many):
        if statement.startswith('UPDATE gmail_connections') and 'gmail_connections.state =' in statement and not paused:
            paused.append(True)
            # The owner's Pause wins immediately before the monitor's guarded
            # UPDATE executes. The remaining WHERE condition must reject it.
            cursor.execute("UPDATE gmail_connections SET state='paused' WHERE id=?",(conn.id,))
    event.listen(engine,'before_cursor_execute',before_sql)
    try:check_connections(sessions)
    finally:event.remove(engine,'before_cursor_execute',before_sql)
    db.expire_all()
    assert paused and conn.state=='paused' and conn.last_error is None


@pytest.mark.parametrize('boundary',['metadata','body'])
def test_shutdown_during_network_read_retains_pending_message_without_ingesting(monitor,monkeypatch,boundary):
    from backend.app.inbox.full_history import FullMailboxScan
    db,conn,sessions=monitor
    stopped=[]
    inbox._FULL_SCANS[inbox._coverage_key(conn,0)]=FullMailboxScan('fixture-baseline',phase='importing_changes',ids={'shutdown-new'},snapshot='fixture-snapshot')
    inbox._FULL_SCANS[inbox._coverage_key(conn,0)].pending.append('shutdown-new')
    monkeypatch.setattr(inbox,'_access',lambda *a:'fixture-token')
    calls=[]
    def get(path,token,params):
        calls.append(params['format'])
        if params['format']=='minimal':
            if boundary=='metadata':stopped.append(True)
            return {'id':'shutdown-new','labelIds':[]}
        stopped.append(True)
        return message('shutdown-new','Job ID: SE-101. Your application was rejected.')
    monkeypatch.setattr(gmail,'get_json',get)
    result=inbox.sync_once(db,conn,0,should_stop=lambda:bool(stopped))
    assert result['state']=='stopping'
    assert calls==(['minimal'] if boundary=='metadata' else ['minimal','full'])
    assert inbox._FULL_SCANS[inbox._coverage_key(conn,0)].pending[0]=='shutdown-new'
    assert not list(db.scalars(select(GmailMessageRecord)))
    assert statuses(db)==['applied']*3 and not job_events(db)


def test_advisory_lock_uses_dedicated_connection_and_always_releases():
    from types import SimpleNamespace
    calls=[]
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):calls.append('closed')
        def scalar(self,sql,params):calls.append(str(sql));return True
        def execute(self,sql,params):calls.append(str(sql))
        def commit(self):calls.append('committed')
    engine=SimpleNamespace(dialect=SimpleNamespace(name='postgresql'),connect=Connection)
    with pytest.raises(ValueError),single_monitor(engine) as acquired:
        assert acquired
        raise ValueError('fictional tick failure')
    assert 'pg_try_advisory_lock' in calls[0] and calls[1]=='committed'
    assert 'pg_advisory_unlock' in calls[2]
    assert calls[-2:]==['committed','closed']


def test_api_lifespan_starts_and_stops_only_the_configured_gmail_monitor(monkeypatch):
    import asyncio
    from backend.app.api.main import create_app
    from backend.app.inbox import monitor as module
    monkeypatch.setenv('GMAIL_BACKGROUND_SYNC_ENABLED','true');get_settings.cache_clear()
    monkeypatch.setattr(inbox,'_settings_ready',lambda:True)
    calls=[]
    class Worker:
        def __init__(self,*args):pass
        def start(self):calls.append('started')
        def stop(self):calls.append('stopped')
    monkeypatch.setattr(module,'GmailMonitor',Worker)
    app=create_app()
    async def use():
        async with app.router.lifespan_context(app):
            assert calls==['started'] and app.state.gmail_monitor is not None
    asyncio.run(use())
    assert calls==['started','stopped']
    get_settings.cache_clear()


def test_one_background_lease_covers_multiple_ticks_and_quota_cooldown(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from backend.app.inbox import monitor as module
    calls=[];delays=[]
    @contextmanager
    def lease(engine):
        calls.append('acquired')
        try:yield True
        finally:calls.append('released')
    class Stop:
        stopped=False
        def wait(self,delay):
            delays.append(delay)
            self.stopped=len(delays)>=3
            return self.stopped
        def is_set(self):return self.stopped
    monkeypatch.setattr(module,'single_monitor',lease)
    def check(*args,**kwargs):calls.append('checked');return module.QUOTA_COOLDOWN_SECONDS
    monkeypatch.setattr(module,'check_connections',check)
    worker=module.GmailMonitor(None,SimpleNamespace(dialect=SimpleNamespace(name='sqlite')))
    worker.stop_requested=Stop();worker.run()
    assert calls==['acquired','checked','checked','released']
    assert delays==[15,module.QUOTA_COOLDOWN_SECONDS,module.QUOTA_COOLDOWN_SECONDS]
