# Full-history Inbox and Analytics, 2026-10-27

Status: owner-approved commit `5ab6b1a` is live in API/web as of
2026-10-27T14:24Z. Full-history import and parser rechecks are in progress;
mailbox completeness is not yet certified. Earlier read-only measurements below
are the pre-release baseline. This scope supersedes the initial 30/90/365-day
reliable-Inbox candidate.

## Owner requirement and verdict

The owner explicitly requested all history, everything, rather than concentrating
on 30 days. Analytics and Inbox now default to All time. Date selections remain
available for comparison; a completed recent window never earns an all-history
"All caught up" claim.

The live system uses real stored records, but its mailbox coverage is incomplete.
An exhaustive Gmail-ID inventory is different from proving that every outcome
was recognized, linked to the right application and confirmed. Do not call this
perfect tracking or certify full historical response rates.

## Read-only production measurements

`backend/scripts/inbox_coverage_report.py` ran at
`2026-10-27T13:19:13.315320Z`. All listing pages completed:

| Scope | Gmail IDs listed | Stored from those IDs | Missing |
| --- | ---: | ---: | ---: |
| 7-day query | 283 | 282 | 1 |
| 30-day query | 958 | 524 | 434 |
| 90-day query | 1,634 | 524 | 1,110 |
| 365-day query | 2,278 | 524 | 1,754 |
| All retained history, including Spam/Trash | **7,927** | **524** | **7,403** |

Windowed queries include one cutoff-buffer day and default Spam/Trash exclusions.
All time has no date or label filter and explicitly includes Spam/Trash. No stored
ID was absent from that retained-mailbox listing. Permanently deleted emails
cannot be recovered through this connection. These are mailbox messages, not
7,403 proven missing job outcomes. The report lists IDs only, with no detail-body
reads or imports. Gmail listings are changing observations, not atomic mailbox
snapshots; timestamps and listing completion are reported explicitly.

At this snapshot production still ran parser 5: 250 ignored, 197 receipts,
51 automatic and 26 manual records; 319 were read under older parsers. Of the
ignored messages, 113 came from recruiting systems and 180 had application words
(overlapping populations). The ready connection still had no history cursor and
an incomplete preview. Source changes did not run production sync or rechecks.

The independent aggregate PostgreSQL audit at
`2026-10-27T13:10:24.850297Z` reconciled 945 stored application identities to
897 applied marks plus 48 external records. All range, status, cohort and
outcome-record invariants passed:

| Submission selection | Identities | Rejection evidence |
| --- | ---: | ---: |
| 30 days | 564 | 68 |
| 90 days | 944 | 88 |
| All time | **945** | **89** |

All-time current statuses: 853 Applied, 89 Rejected, 3 Screening. One historical
application/rejection lies outside even the 90-day selection. Two potential
job/external duplicate groups and two older email/application date conflicts
still require owner review. Six outcome-worded messages were explicitly filed
as acknowledgements by the owner and remain protected. There are zero orphan
active outcome events. Counts changed since the earlier audit through ordinary
owner activity; the snapshots above were obtained read-only.

## Implementation

- Sync, legacy backfill and Analytics default to all time. Internal API value
  `days: 0` means an unbounded retained-mailbox scan, not a zero-day query.
- All-time listing omits date/label filters and sets `includeSpamTrash=true`.
  It follows every page without the earlier 60-page or 365-day ceiling.
- Each authenticated request lists at most five pages and imports at most
  sixty new messages, committing each separately. A process-local manifest
  retains page/queue progress. On restart, a fresh full listing proves coverage
  again while committed SQL rows prevent duplicate detail reads/events. No new
  database table, migration, scheduler, Gmail permission or background job.
- The history baseline is captured before listing. After initial import, all
  history pages are reconciled for arrivals/deletions before completion. Later
  incremental checks use the full manifest's own cursor, independently of a
  narrower check. The snapshot time reflects completion of the history read.
- Expired/repeated cursors, quota failures, pause/reconnection and incomplete
  detail responses cannot earn a complete claim. A missing detail must have a
  confirmed history deletion or force a new full listing; a 404 alone never
  makes an unimported listed ID count as present. Retained SQL evidence is never
  deleted when Gmail removes a message.
- Rechecks include all stale ignored mail, without the former 120-day or
  sender/keyword exclusion. Waiting mail and ACE-filed receipts remain eligible;
  owner filings, confirmed outcomes and Undo remain protected.
- Full historical imports preserve positive-outcome preview restrictions.
  Spam/Trash outcomes are retained for owner review and never change an
  application status automatically. Other existing exact-ID, sender, timestamp,
  final-stage and opt-in safeguards remain in force.
- All-time Analytics includes undated external records without inventing dates.
  Explicit date selections remain bounded, exclude undated records and are
  labeled as date selections rather than All time.

Gmail contract references: [message listing](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)
and [history reconciliation](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list).
Message totals come from actual deduplicated listed IDs, not `resultSizeEstimate`.

## Real-data projection comparison without writes

At `2026-10-27T13:16:58.424390Z`, candidate Analytics source was compiled only
inside a separate diagnostic Python process and compared with live code against
one repeatable, enforced read-only PostgreSQL snapshot. No service/source file
was replaced and no mailbox import/recheck ran. Candidate SHA-256:
`80db50ddcf0cb87a129680d8729ac1390fdb9947680ee79940f1cde6abd17074`.

The candidate retained all 945 identities, statuses, 89 rejections and three
positive-response identities. Dated rejections increased 67 to 69, seven email
links and six latest-company dates were corrected, and the 67-application timing
sample and median were unchanged. Two before-application date conflicts remain
excluded with review links. The diagnostic imported live parser-5 Inbox helpers;
it does not simulate the new all-ignored recheck selector or classify unread mail.

## Validation and release gate

286 focused fictional backend tests and 42 React render/workflow/DOM tests pass.
TypeScript, focused ESLint, whitespace and the forbidden-dash guard pass. Tests
cover 2010 mail, 1,107 messages, more than 60 pages, per-request work limits,
restart/quota recovery, independent cursors, arrivals/deletions during scanning,
unconfirmed missing details, pause/grant changes, Spam/Trash review, old ignored
mail, full-history defaults and explicit date filtering. Browser cases are
collected locally only; Chrome remains prohibited on this laptop.

Hosted CI uncovered a stale extension fixture that opened the removed legacy
Queue. It now uses a unique blank document with fresh script state; 46 of 47
cases then passed. The remaining assertion expected an unscoped legacy answer
bank entry to fill a protected employer relationship. The approved contextual
Memory behavior requires a reviewed scope and distinguishes previous/ever; that
test now asserts the field remains empty, preserving its school positive control
and all other protected-field assertions. No extension runtime changed or tests
were skipped. Check the final hosted CI result before release.

Next: owner approval for the exact final commit, then the safe API/web-only
image build/activation and post-release verification. Only after approval and
release should the owner open Inbox for the full import/recheck and rerun both
read-only audits. Review ambiguous/unlinked outcomes, the two date conflicts and
two potential duplicate groups separately. No automatic merge, deletion or
repair is authorized. Complete ID coverage alone cannot certify semantic
recognition, unique real-world submissions or every historical outcome.

Final scrutiny also reproduced a recheck/owner-action race: all four fictional
cases (owner acknowledgement, owner-confirmed outcome, pause, reconnection)
incorrectly wrote an automatic rejection after the Gmail read returned. The fix
rechecks connection/grant state and reselects current stale eligibility with a
short PostgreSQL row lock after network access, refreshing the identity map.
An owner filing/confirmation is skipped rather than overwritten. Pause/grant
changes stop the batch and the client reports saved progress. No row lock spans
a Gmail request. These are local reproductions/fixes, not production repairs.

Hosted run `40511676317` on `4b79e50` passed backend/web and all 47 extension
browser cases, then reported 190 app-browser passes/26 failures. Four Analytics
cases expected the richer `seed_analytics_demo` fixture, while CI only seeded the
basic demo (no Gmail evidence, assessment events, verified series or Google
external record). The acknowledgement browser case also failed, while its
actual full-component handler and fixture routing pass offline. The focused
browser step now runs those two files against the existing isolated rich SQLite
fixture, waits for the email frame before filing, then restores the basic demo
and runs every remaining browser file. No assertions are skipped. Failure
accessibility trees/screenshots contain fictional CI data only. The whole suite
is not green; unrelated old extension/navigation expectations remain outside
this Inbox implementation. Check focused and broad results separately.

Hosted focused run `40515983693` on `4c79daa` passed 28/30 browser cases with
rich fictional data. The remaining two failures were strict selector ambiguity:
Acknowledgement matched both the overview KPI and the filing choice; Google
logo matched the company table and outcome history. Final selectors target the
email-decision group and company table respectively. Filing actions, no-status-
change checks, image loading and image-error fallback assertions remain intact.


## Approved live release, 2026-10-27

The owner approved the exact reviewed commit `5ab6b1a90decfcddf8b3866fe99a9627f0f2e574`
and requested accurate live dashboard data. It was fast-forwarded without force
to `wine-rose-platform`, built on the VM and activated in API/web only.

- Live public HTTPS health at 14:24:08Z: API healthy and frontend header/body
  match the exact approved SHA. Running API parser 6 and Analytics source hash
  match the reviewed candidate. Signed-out Inbox and Analytics return 401;
  representative logo and auth-background assets return readable images.
- API image: `sha256:5450e7ccf18399d6e5eff97548f194d026981b72a5b22e74a88ec64a18fccb77`.
  Web image: `sha256:0bd5af244cbca295a8fe765d046bc8d490143d8101cd0dfc0722c6d972be7c61`.
- Fresh private 474,638,141-byte consistent PostgreSQL backup verified with
  gzip integrity and `pg_restore --list`, not a restore drill. VM location and
  rollback image tags are in the root Current release checkpoint.
- Schema `0050` and scheduler/PostgreSQL/Caddy container and image IDs were
  unchanged. Protected counts matched before/after activation: 1,237 job marks,
  897 Applied, 48 external applications, 104 answers, 111 career facts,
  5 resumes, 6 resume documents, 6 resume versions, 1 user. No migration,
  scheduler operation, extension publication or destructive repair ran.
- Hosted exact-commit checks: backend/web jobs pass, 47 extension browser cases
  and 30 focused Inbox/Analytics browser cases pass. Remaining app browser
  tests fail; the overall e2e job is not green. This limitation was disclosed
  before owner approval. Run 40517153741, focused step 13.

The deployed service's `sync_once(..., 0)` and parser recheck functions are used
by a monitored one-time operator process, with no added scheduler or new auth
sessions. Only count/coverage output is retained. The existing ready grant and
automation opt-ins, conservative historical/Spam/Trash handling, owner decisions
and Undo are preserved. API-worker coverage caches are process-local: the
owner's next Check Gmail independently verifies the retained listing and history;
SQL imports remain durable. No complete claim is made merely from this process
starting. Google rate-limited the first pass after 104 committed new emails;
progress was preserved and the import resumed with paced reads and bounded
cooldowns honoring Google's retry timing. No quota or permission refusal was
bypassed. A private 147-row snapshot of previously protected Inbox decisions
was captured before rechecks for a subsequent preservation comparison.
Google documents per-project/per-user quotas and explicit retry/backoff behavior:
[usage limits](https://developers.google.com/workspace/gmail/api/reference/quota),
[error handling](https://developers.google.com/workspace/gmail/api/guides/handle-errors).
The observed live limit is not inferred from documented defaults.

An enforced read-only live audit at 14:27:21Z passed all projection checks for
14/30/90/all-time selections: 945 identities, 106 rejection-evidence applications
(previously 89), 3 positive-response applications, 37 pending review and no orphan
active outcome events. This was an interim snapshot while imports continued,
not the final mailbox-coverage result or signed-in browser verification.


### Gmail pacing observed during the import

The first unpaced run stopped safely on `GmailRateLimited`; short backoffs alone
can exhaust before a minute-based quota resets. Google subsequently documents
`messages.get(format=full)` as 60 units and the current per-user/project rate as
6,000 units/minute, with different retained limits for some older projects.
Repeated live 403 quota responses were observed; no exact configured project
quota was claimed from documentation alone. The operator process now spaces
reads by at least 0.7 seconds (under 86/minute), keeps server retry timing and
bounded cooldowns, and retains its manifest between attempts. This adjusts only
the one-time operator process, not the approved runtime source or scheduler.
The live UI's bounded temporary-failure path still keeps committed progress and
requires a later check if Google's short retries cannot recover.
