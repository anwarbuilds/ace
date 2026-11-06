"""Fictional board additions exercise the real feed, batch and paste paths."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.coverage import identity
from backend.app.coverage.identity import BoardEvidence, read_board_evidence, registration_identity
from backend.app.coverage.service import add_source, undo_added
from backend.app.db.base import Base
from backend.app.db.models import CompanyPetitionReportRecord, JobSourceRecord, SourceState
from backend.app.discovery.detector import detect_source_from_url
from backend.app.discovery.feed_links import BoardOutcome, NamedBoard, boards_named_in, read_boards, register_confirmed_boards
from backend.app.discovery.detector import DetectedSourceIdentity
from backend.app.scheduling.types import SourceType
from backend.app.coverage.probing import BoardCandidate
from backend.app.models.job import CanonicalJob
from backend.scripts.register_network_boards import Candidate, Outcome, assess, register

NOW = datetime(2026, 11, 6, 16, tzinfo=timezone.utc)
BOARDS = {
    'greenhouse': 'https://job-boards.greenhouse.io/birchlabs/jobs/1',
    'ashby': 'https://jobs.ashbyhq.com/birchlabs/job-1',
    'lever': 'https://jobs.lever.co/birchlabs/job-1',
    'smartrecruiters': 'https://jobs.smartrecruiters.com/birchlabs/1-software-engineer',
    'workday': 'https://birchlabs.wd5.myworkdayjobs.com/External/job/US/Engineer_R1',
    'oracle_recruiting': 'https://birchlabs.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX/job/1',
    'workable': 'https://apply.workable.com/birchlabs/j/ONE/',
    'gem': 'https://jobs.gem.com/birchlabs/job-1',
}


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def raw_job(reader):
    row = {'id': '1', 'title': 'Software Engineer, New Grad', 'name': 'Software Engineer, New Grad'}
    if reader == 'smartrecruiters':
        row['company'] = {'name': 'Birch Labs'}
    return row


def fetchers(reader, employers=()):
    rows = [dict(raw_job(reader), hiringOrganization={'name': name}) for name in employers] or [raw_job(reader)]
    def fetch(url, **kwargs):
        if '/v1/boards/' in url and not url.endswith('/jobs'):
            return {'name': 'Birch Labs'}
        if 'oraclecloud.com' in url:
            return {'items': [{'requisitionList': rows}]}
        if reader == 'lever':
            return rows
        if reader == 'smartrecruiters':
            return {'content': rows}
        return {'jobs': rows}

    def post(url, payload, **kwargs):
        return {'results': rows, 'jobPostings': rows}

    def page(url, **kwargs):
        if reader == 'workable':
            return '<title>Birch Labs - Current Openings</title><h1>Open roles</h1>'
        if reader in ('ashby', 'lever', 'gem', 'workable'):
            return '<title>Birch Labs Jobs</title><h1>Open roles</h1>'
        # A readable board can omit a separate owner name.
        return '<html><h1>Open roles</h1></html>'
    return fetch, post, page


def normalized(reader):
    return [CanonicalJob(source=reader, company='Birch Labs', external_id='1',
        title='Software Engineer, New Grad', location='Seattle, WA',
        description='Build software with our team. ' * 20, official_url=BOARDS[reader],
        hiring_organizations=('Birch Labs',) if reader == 'smartrecruiters' else ())]


@pytest.mark.parametrize('reader,owner_stated', [(reader, True) for reader in BOARDS]
    + [(reader, False) for reader in ('oracle_recruiting', 'workable', 'gem')])
@pytest.mark.parametrize('path', ['feed', 'batch', 'paste'])
def test_normal_board_can_be_added_through_each_path(db, reader, path, owner_stated):
    url = BOARDS[reader]
    ref = detect_source_from_url(url)
    assert ref and ref.source_type.value == reader
    fetch, post, page = fetchers(reader)
    if not owner_stated:
        page = lambda url, **kwargs: '<html><h1>Open roles</h1></html>'
    jobs = normalized(reader)

    def evidence(candidate, jobs):
        return read_board_evidence(reader, ref.source_account,
            source_host=ref.source_host, fetch=fetch, fetch_text=page, jobs=jobs)

    if path == 'feed':
        [board] = boards_named_in([(url, 'Birch Labs')])
        [outcome] = read_boards([board], lambda definition: jobs, evidence)
        assert outcome.registered, outcome.error
        assert register_confirmed_boards(db, [outcome], now=NOW)
        db.commit()
    elif path == 'batch':
        candidate = Candidate(reader, ref.source_account, 'Birch Labs', ref.source_host)
        outcome = assess(candidate, lambda definition: jobs, evidence)
        assert outcome.added, outcome.reason
        assert register(db, outcome, now=NOW)
        db.commit()
    else:
        result = add_source(db, text=url, fetch=fetch, post=post, fetch_text=page,
            robots=lambda host: '', fetch_robots=lambda host: (404, ''),
            refuses=lambda url: False, now=NOW)
        assert result.status == 'added', result
    source = db.scalar(select(JobSourceRecord))
    assert source.enabled
    assert source.source_type == reader and source.source_account == ref.source_account
    assert source.company_name.casefold().replace(' ', '') == 'birchlabs' or reader == 'oracle_recruiting'
    unverified = reader == 'oracle_recruiting' or not owner_stated
    assert ('identity_unverified' in source.discovery_source.split()) == unverified
    # A reviewed legal report alone cannot establish that this board belongs
    # to that employer. The uncertainty must survive registration and reload.
    db.add(CompanyPetitionReportRecord(ace_company=source.company_name, legal_entity='Birch Labs Inc',
        source_name='Fictional official report', source_uri='https://reports.example/birch-labs',
        metric_definition='Fictional petition decisions', period='FY 2030', report_version='fictional',
        entity_verified=True, petition_approvals=3, petition_denials=1, first_seen_at=NOW, last_checked_at=NOW))
    db.commit()
    db.expire_all()
    from backend.app.coverage.petition_identity import petition_reports_for
    assert bool(petition_reports_for(db, [source.company_name])) == (not unverified)


def test_matrix_covers_all_current_board_detectors():
    # Fixed employer readers and the two multi-employer feeds have no
    # arbitrary board URL to add. Their polling contracts are tested separately.
    import inspect
    from backend.app.discovery import detector
    providers = set()
    for name, function in vars(detector).items():
        if name.startswith('_detect_') and callable(function):
            import re
            providers.update(x.lower() for x in re.findall(r'SourceType\.([A-Z_]+)', inspect.getsource(function)))
    assert providers == set(BOARDS)


@pytest.mark.parametrize('reader', BOARDS)
@pytest.mark.parametrize('evidence', [
    BoardEvidence(owner='Birch Labs', employers=('Cedar Works',)),
    BoardEvidence(employers=('Birch Labs', 'Cedar Works')),
    BoardEvidence(shared=True),
    BoardEvidence(unavailable=True),
])
def test_conflicts_shared_boards_and_failed_evidence_never_fall_back(reader, evidence):
    ref = detect_source_from_url(BOARDS[reader])
    found = registration_identity('Birch Labs', evidence, source_type=reader,
        account=ref.source_account, source_host=ref.source_host, direct=True)
    assert found.company is None and found.state in ('unknown', 'shared')


@pytest.mark.parametrize('reader', BOARDS)
@pytest.mark.parametrize('path', ['feed', 'batch', 'paste'])
def test_reviewed_shared_board_stays_blocked_through_every_path(db, monkeypatch, reader, path):
    url = BOARDS[reader]
    ref = detect_source_from_url(url)
    monkeypatch.setattr(identity, 'REVIEWED_SHARED_BOARDS', {
        (reader, ref.source_account.casefold()): 'Reviewed fictional shared board.',
    })
    def fail(*args, **kwargs):
        pytest.fail('A reviewed shared board must be rejected before a network request.')
    if path == 'feed':
        [board] = boards_named_in([(url, 'Birch Labs')])
        [outcome] = read_boards([board], fail, fail)
        assert not outcome.registered and outcome.error.startswith('shared:')
        assert not register_confirmed_boards(db, [outcome], now=NOW)
    elif path == 'batch':
        outcome = assess(Candidate(reader, ref.source_account, 'Birch Labs', ref.source_host), fail, fail)
        assert not outcome.added and outcome.reason.startswith('shared:')
        assert not register(db, outcome, now=NOW)
    else:
        result = add_source(db, text=url, fetch=fail, post=fail, fetch_text=fail,
            robots=lambda host: '', fetch_robots=lambda host: (404, ''), now=NOW)
        assert result.status == 'saved_looking' and 'shared' in result.detail.lower()
    assert not any(row.enabled for row in db.scalars(select(JobSourceRecord)))


@pytest.mark.parametrize('source_type', list(SourceType))
def test_existing_polling_settings_and_state_survive_all_addition_paths(db, monkeypatch, source_type):
    # Covers all current readers, including fixed employer sites and feeds
    # that intentionally have no arbitrary employer board to add by URL.
    source = JobSourceRecord(source_type=source_type.value, source_account='birchlabs',
        company_name='Birch Labs', source_host='birchlabs.example', enabled=True,
        poll_interval_seconds=723, discovery_source='fictional owner decision')
    state = SourceState(source=source_type.value, source_account='birchlabs',
        last_success_at=NOW, last_unchanged_at=NOW, http_etag='fictional-etag', last_job_count=7)
    db.add_all([source, state])
    db.commit()
    before = (source.enabled, source.poll_interval_seconds, source.discovery_source,
              source.updated_at, state.last_success_at, state.last_unchanged_at, state.http_etag)
    board = NamedBoard(DetectedSourceIdentity(source_type, 'birchlabs', 'birchlabs.example'), 'Birch Labs')
    assert not register_confirmed_boards(db, [BoardOutcome(board, False, error='fictional conflict')], now=NOW)
    assert not register(db, Outcome(Candidate(source_type.value, 'birchlabs', 'Birch Labs'), True, 'fictional'), now=NOW)
    monkeypatch.setattr('backend.app.coverage.service.resolve', lambda *args, **kwargs:
        BoardCandidate('Birch Labs', source_type.value, 'birchlabs', 7, 'fictional readable board'))
    assert add_source(db, text='https://birchlabs.example/job/1', now=NOW).status == 'already_known'
    db.expire_all()
    assert (source.enabled, source.poll_interval_seconds, source.discovery_source,
            source.updated_at, state.last_success_at, state.last_unchanged_at, state.http_etag) == before


def test_structured_employer_does_not_change_job_identity_or_content_hash():
    from backend.app.persistence.hashing import compute_job_content_hash
    original = normalized('smartrecruiters')[0]
    without_evidence = original.model_copy(update={'hiring_organizations': ()})
    assert compute_job_content_hash(original) == compute_job_content_hash(without_evidence)


def test_failed_metadata_does_not_store_another_permanently_disabled_board(db):
    [board] = boards_named_in([(BOARDS['workable'], 'Birch Labs')])
    def fail(*args):
        raise TimeoutError('fictional transport failure')
    [outcome] = read_boards([board], lambda definition: normalized('workable'), fail)
    assert not outcome.registered and outcome.transient
    assert not register_confirmed_boards(db, [outcome], now=NOW)
    assert db.scalar(select(JobSourceRecord)) is None


def test_two_feed_names_cannot_rescue_silent_owner_evidence():
    [board] = boards_named_in([(BOARDS['oracle_recruiting'], 'Birch Labs'),
                             (BOARDS['oracle_recruiting'], 'Cedar Works')])
    [outcome] = read_boards([board], lambda definition: normalized('oracle_recruiting'))
    assert not outcome.registered and 'different employers' in outcome.error


@pytest.mark.parametrize('reader', BOARDS)
@pytest.mark.parametrize('path', ['feed', 'batch', 'paste'])
@pytest.mark.parametrize('employers', [('Cedar Works',), ('Birch Labs', 'Cedar Works')])
def test_unreviewed_structured_conflict_or_shared_board_never_gets_added(db, reader, path, employers):
    url = BOARDS[reader]
    ref = detect_source_from_url(url)
    fetch, post, page = fetchers(reader, employers)
    jobs = [normalized(reader)[0].model_copy(update={'hiring_organizations': (name,)}) for name in employers]
    def evidence(candidate, read_jobs):
        # For providers without board owner metadata, the listed company
        # remains a competing claim. Workday's tenant must not override it.
        return BoardEvidence(owner='Birch Labs', employers=tuple(employers))
    if path == 'feed':
        [board] = boards_named_in([(url, 'Birch Labs')])
        [outcome] = read_boards([board], lambda definition: jobs, evidence)
        assert not outcome.registered
        assert not register_confirmed_boards(db, [outcome], now=NOW)
    elif path == 'batch':
        outcome = assess(Candidate(reader, ref.source_account, 'Birch Labs', ref.source_host),
            lambda definition: jobs, evidence)
        assert not outcome.added
        assert not register(db, outcome, now=NOW)
    else:
        # A single owner without contradictory evidence is a legitimate
        # direct paste. Add an independent board-owner claim to expose the
        # conflict even on platforms that otherwise omit that field.
        from backend.app.coverage import service
        original = service.read_board_evidence
        def with_owner(*args, **kwargs):
            found = original(*args, **kwargs)
            from dataclasses import replace
            return replace(found, owner=found.owner or 'Birch Labs')
        from unittest.mock import patch
        with patch.object(service, 'read_board_evidence', with_owner):
            result = add_source(db, text=url, fetch=fetch, post=post, fetch_text=page,
                robots=lambda host: '', fetch_robots=lambda host: (404, ''), now=NOW)
        assert result.status == 'saved_looking'
    assert not any(row.enabled for row in db.scalars(select(JobSourceRecord)))


def test_smartrecruiters_preserves_disagreeing_summary_and_detail_without_breaking_polling():
    from backend.app.adapters.smartrecruiters import _canonical_job_from_posting
    row = _canonical_job_from_posting(
        summary={'id': '1', 'name': 'Software Engineer', 'company': {'name': 'Cedar Works'}},
        detail={'company': {'name': 'Birch Labs'}}, company_identifier='birchlabs', company_name='Birch Labs')
    assert row.company == 'Birch Labs'
    assert row.hiring_organizations == ('Birch Labs', 'Cedar Works')
    found = registration_identity('Birch Labs', BoardEvidence(), source_type='smartrecruiters',
        account='birchlabs', jobs=[row])
    assert found.company is None and found.state == 'shared'


@pytest.mark.parametrize('reader', ['simplify', 'ripplematch'])
def test_multi_employer_feed_never_becomes_a_single_employer(reader):
    found = registration_identity('Birch Labs', BoardEvidence(), source_type=reader, account='fictional')
    assert found.company is None and found.state == 'shared'


@pytest.mark.parametrize('url,reader,account,host', [
    ('https://wd5.myworkdaysite.com/recruiting/birchlabs/External/job/US/Engineer_R1',
     'workday', 'birchlabs/External', 'birchlabs.wd5.myworkdayjobs.com'),
    ('https://jobs.eu.lever.co/birchlabs/job-1', 'lever', 'birchlabs', 'jobs.eu.lever.co'),
])
def test_other_existing_url_forms_keep_the_board_and_region(db, url, reader, account, host):
    fetch, post, page = fetchers(reader)
    requested = []
    def record(url, **kwargs):
        requested.append(url)
        return fetch(url, **kwargs)
    result = add_source(db, text=url, fetch=record, post=post, fetch_text=page,
        robots=lambda host: '', fetch_robots=lambda host: (404, ''), now=NOW)
    assert result.status == 'added'
    source = db.scalar(select(JobSourceRecord))
    assert (source.source_account, source.source_host) == (account, host)
    if reader == 'lever':
        assert requested and all('api.eu.lever.co' in url for url in requested)


def test_unverified_manual_board_keeps_owner_origin_and_undo(db):
    from backend.app.coverage.leads import added_report
    from backend.app.coverage.sources_view import sources_report
    reader = 'oracle_recruiting'
    fetch, post, page = fetchers(reader)
    result = add_source(db, text=BOARDS[reader], fetch=fetch, post=post, fetch_text=page,
        robots=lambda host: '', fetch_robots=lambda host: (404, ''), now=NOW)
    assert result.status == 'added'
    source = db.scalar(select(JobSourceRecord))
    assert source.discovery_source == 'added_by_hand identity_unverified'
    assert added_report(db)[0]['state'] == 'polling'
    assert sources_report(db, now=NOW, show='mine')['rows'][0]['added_by_you']
    assert undo_added(db, source_type=reader, source_account=source.source_account, now=NOW)
    assert not source.enabled and source.discovery_source == 'added_by_hand undone'


def test_unverified_network_origin_keeps_the_existing_nonproductive_cadence(db):
    from backend.app.coverage.cadence import promote_productive_sources
    outcome = Outcome(Candidate('gem', 'birchlabs', 'Birch Labs'), True,
        'Readable board', jobs=1, us_engineering=1, passing=0, identity_state='unverified')
    assert register(db, outcome, now=NOW)
    db.commit()
    source = db.scalar(select(JobSourceRecord))
    assert source.discovery_source == 'talent_network identity_unverified'
    assert source.poll_interval_seconds == 3600
    assert promote_productive_sources(db) == []
    assert source.poll_interval_seconds == 3600
