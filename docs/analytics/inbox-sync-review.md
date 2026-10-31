# Inbox to Analytics integration review

Based on canonical `main` at `3bb2a9623c43cdb7c489da8f180aa08b900687d8`.
Owner-approved exact tested source **`a48d71be3a33a6188e8fa96f748b4b78ecd19ef0`**
is **LIVE for API/web** at https://ace.opik.net, activated
2026-10-31T04:31:22Z–04:31:35Z (October 30, 21:31 Pacific).
[PR #20](https://github.com/anwarbuilds/ace/pull/20) merged into canonical main
as `1a91c7021c5186412bbb64cc2c54a7ab23b741e2`. Parser 15, scheduler source
`fca4673`, schema 0050 and the approved design are preserved.

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
The owner explicitly approved final candidate execution in the memory of a
separate Python process against enforced read-only production snapshots; no
deployed source was replaced. Primary, independent and expanded checks pass all
four ranges, reconciling category totals, exact message drilldowns, unique
applications, historical stages, latest statuses, age-qualified partitions and
timing. Candidate source hash matches the reviewed file. A further comparison of
deployed and candidate calculations in the same snapshot preserves every
submission/status/timeline/attribution/official-series source and the existing
confirmed outcome values; the recognized email omissions are corrected.
Report reads measured 180 to 208 ms and 17 SELECTs. Actual counts and the requested
source/date/verification metric table stay in private `RECONCILIATION.md` beside
the JSON reports. Zero Gmail calls, message bodies, sessions or writes were
needed; arithmetic does not certify semantic classification accuracy or coverage.

Final tested source `a48d71be3a33a6188e8fa96f748b4b78ecd19ef0` is in
[merged PR #20](https://github.com/anwarbuilds/ace/pull/20). Local final checks pass:
2,497 backend tests (two PostgreSQL-only checks use the hosted service), 115
DOM/calculation cases, 267 extension matcher cases,
Memory safety, JavaScript syntax, route generation, TypeScript, full lint,
production web build, zero forbidden UI dashes and clean whitespace. One initial
test fixture lacked a React display name; it was named and full lint then passed.
An initial restricted-sandbox backend run stalled in TestClient and was stopped;
the completed full runs used the normal isolated fictional fixtures outside that
restriction. Earlier intermediate source passed 2,495 cases; it is not substituted
for the final result.

The passing [dedicated Analytics review](https://github.com/anwarbuilds/ace/actions/runs/41167247224)
verifies that exact source: **2,499 backend tests including the real PostgreSQL
snapshot/read-only tests, 53 hosted Inbox/Analytics browser cases, DOM/calculation
checks, TypeScript, full lint and production build pass**. The runtime files are
identical to `5c399bb`; its follow-up changed only the two browser fixtures.
The browser checks prove a committed Inbox acknowledgement correction updates
open Analytics, both report routes retain the exact selection/results across a
failed refresh and recover on Retry, delayed requests avoid overlapping refreshes,
and offline pages recover automatically online. Date filters, aggregation,
historical weeks, role filters, July boundaries, exact email drilldowns and
application preservation also pass.

Wider [final-source CI](https://github.com/anwarbuilds/ace/actions/runs/41167251270)
passes backend/web; extension browsers have **25 pass / 22 fail**. Exact
traceback-name comparison with main's consolidation run finds zero new or resolved
failed names. Extension runtime and its browser fixtures are unchanged. Later
broad app-browser steps are skipped, so overall CI is not green.
The first dedicated run passed all 2,499 backend cases including PostgreSQL,
web checks/build, and 51 browser cases. Its two new fixture failures were an
overbroad records-page selector that also matched page-number controls, and an
unsupported `decision=all` API query (the actual Inbox omits that parameter).
Both tests were corrected without runtime changes in `a48d71b`; no assertion was
removed. The earlier [full run](https://github.com/anwarbuilds/ace/actions/runs/41166658152)
passed backend/web and retained 25 passing / 22 failing extension-browser cases;
exact traceback-name comparison with main's consolidation run found no new or
resolved failed names. Later broad app-browser steps were skipped. Overall CI is
not green; dedicated Inbox/Analytics verification is separate.

All eight final desktop captures are 1672 x 941. Four Day reference comparisons
and four Night views were inspected, along with the compact recognized-evidence
captures and responsive checks. Original shell dimensions, Inter and four-tab
composition remain; counts/chart shapes and unavailable states follow the
fictional persisted fixture. The compact evidence wording and freshness line
are intentional accuracy changes. No pixel-perfect claim or signed-in production
browser verification is made. Captures, comparisons, mobile views and traces are
private in `hosted-final/` under the owner evidence directory. The passing run's
`analytics-review` artifact contains the source captures, retained for 14 days.
The dedicated Analytics workflow includes the full backend
suite, guarded fictional PostgreSQL isolation tests, Node DOM/calculation checks,
TypeScript/lint/build, and hosted Inbox/Analytics browser tests. No local Chrome
is run under the existing laptop cooling restriction. Current failures were
checked explicitly against the historical baseline; earlier counts do not
substitute for a fresh result.

## Completed owner-approved release and retained rollback

The owner separately approved deployment after reviewing the final candidate.
Production main was fast-forwarded to exact tested `a48d71b`, after verifying its
ancestry in canonical main and unchanged mounted configuration. Only API/web were
built and activated with `--no-build --no-deps --wait`; no migration ran.

Fresh private backup:
`/opt/ace/private-backups/analytics-inbox-sync-20261031T0421Z/database.dump.gz`
(565,200,680 bytes). Gzip, archive catalog and full expansion pass; no restore
drill or retention pruning ran. A first catalog pipe ended with SIGPIPE when the
catalog reader closed early; its original log/exit are preserved. Regular-file
input then passed catalog and full expansion before activation.

All 371 backend/four script hashes match installed source. Healthy API/web,
exact public frontend SHA/header, 15 bundle/font and 85 logo hashes, plus ten
anonymous API/page auth probes pass. Installed primary, independent Inbox and
expanded read-only audits reconcile 14/30/90/all and exact email drilldowns.
They make zero Gmail calls/body reads/writes. Nineteen protected tables have
zero added/removed/changed rows across preparation-to-cutover and
cutover-to-post-startup; Gmail grants and owner controls match. Scheduler,
PostgreSQL, Caddy and exited migrate retain IDs/images/start times/mounts.
`.env`, Compose and Caddyfile retain hashes/modes/inodes.

The first post-health snapshot saw zero monitor leases during its documented
15-second startup delay. Preserve that failed readiness result; the subsequent
snapshot passes with exactly one lease, successful normal sync advancement and
no connection errors. No service was restarted to obtain that result. Global
historical rechecks remain false and parser 7 remains stopped. Startup logs have
no traceback, error line or HTTP 5xx. No signed-in production browser ran.

The private folder retains actual preceding image tags
`oracle-api:before-analytics-sync-20261031T0421Z` (`b03d251`) and
`oracle-web:before-analytics-sync-20261031T0421Z` (`4116aa0`). Its guarded
`rollback.sh` replaces only API/web and rejects unexpected current/tagged images.
No database restoration or data compensation is part of this image rollback.
Ignored local `artifacts/analytics-inbox-sync-20261030/release/` also holds
aggregate audit, source, public asset, service and private HMAC preservation proofs.

### Procedure for a future separately approved release

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

## Changed-file inventory

Relative to canonical `3bb2a96`, including the final continuity record:

```text
ACE_NEXT_KNOWLEDGE.md
.github/workflows/analytics-review.yml
backend/app/api/routers/analytics.py
backend/scripts/inbox_analytics_audit.py
backend/tests/test_analytics_filed_evidence.py
backend/tests/test_analytics_inbox_sync.py
backend/tests/test_analytics_snapshot_postgres.py
backend/tests/test_analytics_sync_audit.py
backend/tests/test_inbox_evidence_scope.py
docs/analytics/inbox-sync-review.md
docs/analytics/metric-sources.md
docs/analytics/review.md
scripts/audit_analytics_inbox_sync.py
web/package.json
web/src/app/app/analytics/analytics.css
web/src/app/app/analytics/page.tsx
web/src/app/app/applications/analytics/page.tsx
web/src/components/analytics/AnalyticsFreshness.tsx
web/src/components/analytics/AnalyticsRefresh.tsx
web/src/components/analytics/AnalyticsView.tsx
web/src/components/analytics/CorrespondenceRecords.tsx
web/src/components/shell/AppProvider.tsx
web/src/lib/analytics.ts
web/tests/analytics-freshness-dom.test.mjs
web/tests/analytics-rejections-render.test.mjs
web/tests/e2e/analytics-redesign.spec.ts
web/tests/inbox-reliability-dom.test.mjs
```
