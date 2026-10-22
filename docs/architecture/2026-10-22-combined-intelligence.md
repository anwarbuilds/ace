# Combined Intelligence upgrade, local implementation

## Verified baseline

The work began on clean `wine-rose-platform` at `9ebbdd5`. The deployed
application was `132235c29212feb43f50f59245d540628172c43b`. The backend
already owned job discovery, 15-minute Pull windows, eligibility, scoring,
application marks, external application records, Resume Studio, sessions,
Google sign-in and the Chrome extension. The frontend already had all twelve
Wine and Rose V2 routes, shared application totals and a working Analytics
page. None of those domains was replaced.

The previous schema had no application event history, Gmail grant or verified
employer petition reports. Historic interview and assessment stages cannot be
reconstructed from a current status. Older application dates remain whatever
was actually recorded. Rejected applications remain in lifetime submitted
counts through the existing `job_marks` and `external_applications` sources.

## Additive changes

- `0044_add_combined_intelligence_evidence.py` creates four new tables:
  `application_events`, `gmail_connections`, `gmail_messages` and
  `company_petition_reports`. It does not rewrite or remove a legacy row.
- Pull rows put the wine highlighted company above the secondary role. The
  company dialog preserves scroll position and shows only verified official
  reports. The linked company page exposes the legal entity, source, period,
  report version and check time. Unknown evidence says Not available.
- `/api/intelligence` and `/app/dashboard` add the V3 views. The API reads
  existing application and posting tables, with explicit event coverage and
  source freshness. Role and skill demand use observed qualifying postings;
  the company radar combines submitted applications and open roles. The daily
  brief counts today's actual submissions, observed roles and review emails.
  The action center derives dated follow-ups, ambiguous email reviews and
  recent qualifying Pulls; Complete, Dismiss and Reopen are audited owner
  decisions that do not change application outcomes.
  The event ledger begins with new changes. Older outcomes are not inferred
  from current status.
- Inbox Intelligence has a separate read-only Gmail OAuth grant with state,
  nonce and PKCE, an encrypted refresh token, preview-only backfill, Gmail
  history cursor catch-up, pause, disconnect, snippet purge, review, manual
  correction and Undo. Gmail grants never replace ACE sign-in sessions.
- `backend/scripts/sync_gmail.py` is a one-shot catch-up command. It is not
  installed as a timer in production and does not start the cloud discovery
  scheduler.
- `backend/scripts/import_petition_reports.py` validates a reviewed USCIS
  legal-entity mapping CSV in dry-run mode by default. It does not download
  reports, guess employer aliases or equate DOL LCAs with USCIS petitions.

## Metric contracts

| Metric | Source and meaning |
| --- | --- |
| Lifetime submitted | Count of applied job marks plus all external application rows. Current rejection never removes a submission. |
| Current pending | Submitted rows without current accepted, rejected or withdrawn status. No reply remains pending. |
| Confirmed rejections | Current rejected rows. Historic rejection timestamps are available only when an event was recorded. |
| Recorded response, OA, interview, offer | Distinct application keys with event evidence. Categories can overlap. Pre-ledger history is partial. |
| Response rate | Distinct matured submissions with a recorded meaningful response divided by dated submissions at least 30 days old. The rate is unavailable while event coverage is partial. |
| Median first response | Only reliably dated submissions and response events; sample size is returned. |
| Observed qualified postings | ACE jobs first seen in the selected period that passed the eligibility gate. This is not a national hiring rate. |
| H-1B petition approval rate | Verified USCIS I-129 approvals divided by approvals plus denials for the same legal entity and period. Workforce sponsorship rate remains unavailable. |

The API provides `as_of`, source, period, coverage, sample sizes and metric
definitions. The UI keeps its existing instant lifetime application counter;
the Dashboard labels selected-period trend data separately. Existing Analytics
stays available.

## Reconciliation safety

Automatic status changes require all of: explicit outcome language in the
newest unquoted email text, one exact application-specific requisition, a
single application with that ID, Gmail's DMARC-pass result aligned to the
visible sender and the sender host matching the employer posting host,
a submission before the email, no newer status change
and no protected terminal state. Shared ATS hosts and personal mail domains
do not independently verify an employer. Missing evidence enters review.
Backfill never writes an application status. Repeated Gmail IDs are unique per
connection and create no repeat event. The status and evidence event are
committed together. The row is locked and checked again at write time, so an
older message arriving after a newer interview cannot overwrite it. An OA
event stays in history after a later rejection.

`GMAIL_AUTO_OUTCOMES_ALLOWED=false` is the server default, and each connection
also starts with `auto_outcomes_enabled=false`. Both must be enabled after an
owner-reviewed pilot before verified automatic outcomes can write. No setting
was changed in production.

## Isolated migration and rollback

Before any approved deployment, take a PostgreSQL custom-format backup and
verify it can be read or restored into an isolated database. Run migration
0044 on a staging copy, verify existing aggregate counts and the replica
cursor, then prepare the exact release SHA. The local SQLite operation smoke
test confirmed that 0044 creates only its four tables. Older migrations are
PostgreSQL-specific, so a full SQLite upgrade from revision 0001 is not a
valid rehearsal.

If a release needs rollback, deploy the prior application image while leaving
the additive tables in place. Keep the cloud scheduler stopped and the legacy
replica active. A downgrade would delete new evidence and should only be
considered after a separate backup and explicit data-loss approval. Do not
restore a production dump, reset a database or touch the legacy stack as part
of a normal code rollback.

## Owner-only Gmail setup after release approval

1. In Google Cloud, enable the Gmail API and configure a Web OAuth client
   for the private ACE origin. Register exactly
   `https://ace.opik.net/api/inbox/google/callback` as a redirect URI.
2. Configure the Gmail read-only restricted scope, separately from the
   existing Google sign-in grant. Keep the app limited to approved test users
   while reviewing Google's restricted-scope verification and server-storage
   security-assessment requirements.
3. Add `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REDIRECT_URI` and a
   newly generated Fernet `GMAIL_TOKEN_KEY` to the VM's mode 600 `.env`.
   Do not put these values in Git, chat, screenshots or logs.
4. After the owner authorizes deployment, sign in, connect Gmail, run a bounded
   historical preview and inspect ambiguous cases. Backfill is read-only for
   application statuses. Resume sync only after the preview is complete.
5. Install a separate daily timer for `python -m backend.scripts.sync_gmail`
   only after reviewing its local catch-up result. Keep the cloud discovery
   scheduler stopped throughout monitoring.
6. Verified-only automatic outcomes remain disabled. A later explicit owner
   decision can set `GMAIL_AUTO_OUTCOMES_ALLOWED=true` and enable the Inbox
   control after negative-case review. That decision is separate from Gmail
   connection and deployment approval.

Google documents the scope as restricted and says server storage may require
a security assessment: [Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes).
Its [sync guide](https://developers.google.com/workspace/gmail/api/guides/sync)
describes history cursors and the 404 full-reconciliation case.

## External prerequisites and current limits

- No live Gmail account, credentials or official petition release was supplied
  to development. OAuth and sync are implemented but cannot be validated with
  the owner's actual mailbox until the owner completes the private setup.
- The importer needs a reviewed legal-entity mapping to an official USCIS
  release. Unknown companies intentionally show no petition statistics.
- The current application tables represent one mark per stored job. A truly
  separate repeat submission to the same posting needs an additional identity
  model before it can be auto reconciled. Such cases should remain manual.
- A Gmail Pub/Sub watch and webhook were not installed. The implemented
  incremental history cursor and separate daily catch-up avoid changing the
  discovery scheduler. Provider push can be added after private setup if the
  daily cadence proves insufficient.
- The new views were compared with the supplied Day and Night previews, but
  a live Gmail state cannot yet be compared visually. Local screenshots use
  only fictional, isolated fixture data.

No push, production migration, deployment, DNS change or scheduler operation
was performed by this implementation.

## Local validation

- Backend regression: 1,211 passed and 45 skipped after the Gmail sender
  authentication change; focused safety/auth tests passed again after the
  action-center and ordered-message fixes.
- Frontend typecheck, ESLint and optimized production build passed.
- Chromium full baseline: 133 passed on isolated fictional fixture data;
  subsequent focused Day and Night combined-intelligence tests: 20 passed,
  including action state changes. The existing mark/count browser suite also
  passed after the Dashboard metric changes.
- Extension rules: 185 passed. Static user-facing dash scan: zero hits.
- Migration 0044 isolated operation test created all four tables and checked
  the preview and automation safety columns. No production migration ran.
- Screenshots are in ignored `artifacts/combined-intelligence/dark/` and
  `artifacts/combined-intelligence/light/`, including Pulls, all seven
  Dashboard views, Inbox disconnected state and the company dialog.
