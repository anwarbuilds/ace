# Inbox to Analytics integration review

Candidate based on canonical `main` at `3bb2a9623c43cdb7c489da8f180aa08b900687d8`.
This work is not deployed. The production API remains parser 15 at `b03d251`,
web `4116aa0`, scheduler source `fca4673`, schema `0050`.

## Consistency contract

Inbox remains the only recruiting-email classifier. Analytics reads its shared
`projected_classification` and `projected_decision`, including compatibility
markers, exact owner receipt overrides, filed actions and company rejection
evidence. No new classifier, storage, worker, scheduler, migration, Gmail scope
or historical replay is introduced.

The Analytics API uses a separate PostgreSQL READ ONLY, REPEATABLE READ session.
Authentication retains its ordinary session/heartbeat outside that snapshot.
All report SELECTs see one committed state; the next request sees an Inbox
transaction that committed before its snapshot began. There are no materialized
counters or Analytics caches to transfer or invalidate.

The existing persistent layout coordinator owns Analytics refreshes: known
`ace-marks` decisions, return navigation, focus, visibility and online recovery,
plus a two-minute visible-page check. It makes no extra hydration/response-mount
request, coalesces bursts, and queues one follow-up when evidence arrives during
an in-flight read. The shell's existing two-minute refresh skips only these two
routes, avoiding a competing timer; discovery announcements retain their path.

`AnalyticsFreshness` retains this mounted selection's last successful rendered
report when a new API read fails, rejects older `as_of` responses, and reports
unavailable/stale/delayed/offline states honestly. Query changes discard another
selection's retained output. There is no browser persistence or duplicate client
application ledger. A new visit fetches authoritative data. Hard reloads and
browser-managed document replacement cannot retain in-memory prior results;
an unavailable page shows no invented totals.

## Evidence and counting

`classified_email_evidence` now covers effective acknowledgements, assessment
invitations, interview invitations/scheduling, offers, recruiter replies, other
action requests, rejection correspondence and separately labeled completion,
cancellation and routine progress updates. It counts distinct messages, with a
partition of verified application-linked, company-only and unlinked evidence.
Owner-held, undone, superseded and unsupported states do not become active
outcomes. An owner receipt projects an acknowledgement while keeping the raw
machine classification and audit history intact.

Confirmed stages count distinct eligible application identities per event type.
Current decision, exact target, active ledger/Undo, actor, effective meaning and
chronology guards apply. An explicit active owner `manual_correction` remains
stage authority under the existing optional-kind API contract; its saved email
meaning remains a separate fact. Invalidated email transitions cannot reappear
as undated status fallback or control the confirmed cohort polarity. A genuinely
later explicit status edit remains authoritative. Valid earlier assessments and
interviews survive later rejections. Positive/rejection categories overlap and
are not summed into distinct applications.

An inherited receipt `selected_application_key` alone is not verified linkage.
Receipts remain recognized without acquiring a role/company attribution from
that key. Company-only rejection requires the existing validated, active company
event and never changes or assigns an individual application. Unlinked invitation
or offer meanings remain visible without a confirmed role-stage transition.

No durable sender-authentication revision or generic inactive flag exists in
schema 0050. Analytics honors current classifications, decisions, links, Undo
and the existing explicit unverified-source marker. `verified_automation` records
the original authorized ingest, not fresh Gmail authentication. Analytics never
rereads Gmail to claim reauthentication. A new external authenticity fact must
first be committed through the existing Inbox evidence contract; unavailable
facts cannot be inferred from legacy storage.

## Reporting clocks and exact records

Application submission cohorts use `applied_at`; stages use valid event history;
recognized correspondence uses message receipt dates. The email floor remains
July 1, 2026 midnight America/Los_Angeles (`2026-07-01T07:00:00Z`). Older records
remain stored. All time includes in-scope email before the first application;
14/30/90/custom selections use actual local receipt dates. Application cohort
dates stay independent, including custom selections before July and undated
all-time application history.

`GET /api/analytics?emails=1` adds paginated `email_records`, `email_total`,
`email_offset`, `email_limit`, optional `email_kind`, and optional
`email_scope=linked|company|unlinked`. It uses the same effective rows and filters
as the summary. Existing application record contracts remain available.
`/app/applications/analytics?emails=1` renders these rows with exact receipt dates,
current meaning/decision and an existing Inbox email link. Search, pagination,
date/timezone, role/company and return navigation preserve their reporting
selection. Application keys and companies are shown only with supported identity.

The four approved tabs, five KPI positions, Wine and Rose Day/Night styles,
Inter, chart geometry, status charts and existing unavailable attribution/rates
are retained. Additions stay within the existing compact recognized-email panel,
existing records-table styling, and a subtle freshness line. Official petition
evidence remains separate from employer correspondence.

## Audit and verification

Private evidence is under ignored `artifacts/analytics-inbox-sync-20261030/`.
The original production arithmetic audit passes its narrower projection. The
expanded independent `scripts/audit_analytics_inbox_sync.py` detects missing
effective message categories in all four ranges before the integration.
Candidate source is evaluated only in the memory of a separate Python process
against enforced read-only production snapshots; no deployed source is replaced.
It reconciles category totals, exact message drilldowns, unique applications,
historical stages, latest statuses, age-qualified partitions and timing. Actual
measurements stay private. No Gmail calls, message bodies, sessions or writes are
needed; arithmetic does not certify semantic classification accuracy or coverage.

Validation results, tested source and screenshot comparison are recorded here
after final checks. The dedicated Analytics workflow includes the full backend
suite, guarded fictional PostgreSQL isolation tests, Node DOM/calculation checks,
TypeScript/lint/build, and hosted Inbox/Analytics browser tests. No local Chrome
is run under the existing laptop cooling restriction. Earlier main CI's 22
extension-browser failures are historical baseline, not a result for this source.

## Release and rollback plan (requires explicit owner approval)

After the exact tested source is approved, verify current running source/images
and protected data, take and validate a fresh private production backup, retain
the actual running API/web images under new rollback tags, and prepare exact-source
images. Activate only API and web with `--no-deps`; no migration is required.
Leave scheduler, PostgreSQL, Caddy, environment, extension and historical rechecks
unchanged. Reconcile Inbox/Analytics after release, compare protected inventories,
and verify source/image hashes, service health, public assets and auth boundaries.

Rollback replaces only the newly activated API/web images with the verified
retained originals. This feature makes no data writes, so no data compensation
or database restore belongs to its rollback. Never restore a database over later
owner activity. No earlier deployment, merge or historical correction approval
authorizes this operation.
