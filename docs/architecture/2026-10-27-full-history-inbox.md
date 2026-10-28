# Full-history Inbox and Analytics, 2026-10-27

Status, 2026-10-27T16:30Z: **all developed Inbox/Analytics changes are live**.
The owner separately approved parser 7 by requesting everything be live; PR #7
is merged. API runtime `3294139` is live and healthy, web remains `5ab6b1a` with
all developed dashboard changes. Independent 16:29Z reports again confirm
7,928/7,928 retained Gmail IDs stored, zero missing, and passing Analytics
arithmetic. Additional parser-7 rechecks are running, not complete. Earlier
approval-pending notes below are dated history, superseded by the latest section.

## Owner requirement and verdict

The owner explicitly requested all history, everything, rather than concentrating
on 30 days. Analytics and Inbox now default to All time. Date selections remain
available for comparison; a completed recent window never earns an all-history
"All caught up" claim.

Before release, the live system used real stored records but its mailbox coverage was incomplete.
The completed retained-mailbox scan and independent report now verify zero missing
messages in the checked snapshot.
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


## Additional candidate: parser 7 truncation safety (not released)

Continued scrutiny after the approved parser-6 release reproduced another
false-negative with fictional data: a 9,508-character email began with thanks
for applying and ended with an explicit rejection. The extraction accepted up
to 10,000 characters and claimed completeness, but a second classifier cutoff
at 8,000 characters discarded the rejection and filed a receipt.

The separate candidate uses a shared 10,000-character decision limit and reads
one extra character as a truncation sentinel. Rejections between the former
8,000-character cutoff and the decision limit are recognized. Snippets and
clipped bodies cannot authorize any outcome or file a receipt: recognized
recruiting outcomes wait for review with the existing partial-read reason.
The full-email viewer is unchanged. This remains bounded text recognition;
mailbox completeness never certifies arbitrary wording or attachment outcomes.

Parser version 7 makes existing eligible parser-6 receipts/ignored/pending mail
recheckable under the fix. Owner filings, recorded outcomes and Undo protections
are unchanged. Releasing it would require a further API-only activation and
rechecks, not a schema, scheduler or web change. It has not been deployed under
the approval for `5ab6b1a`.

All 293 focused backend tests pass. Added fictional regressions cover long
plain/HTML rejection tails, truncated receipts/rejections/interviews staying for
review without status/events, exact-size versus one-character overflow, and
parser-6 receipt/ignored rechecks. The authentication test now verifies that a
complete authenticated email can authorize a rejection while a snippet cannot.
No private email text was copied into tests.


## Final independent production verification, 2026-10-27T16:01Z

The one-time process finished successfully. Its final reconciled history snapshot
at 16:01:16.587532Z contains 7,928 retained Gmail IDs, all 7,928 in SQL, zero
missing. All 441 eligible older-parser messages were rechecked; no quota error
lost committed progress. The process stopped after final catch-up, with no new
scheduler or persistent background worker.

The independent `backend/scripts/inbox_coverage_report.py` ran at
16:01:48.093281Z with enforced read-only database connections and Gmail ID lists:

| Scope | Gmail listed | In ACE | Missing |
| --- | ---: | ---: | ---: |
| 7-day query | 284 | 284 | 0 |
| 30-day query | 959 | 959 | 0 |
| 90-day query | 1,635 | 1,635 | 0 |
| 365-day query | 2,279 | 2,279 | 0 |
| All retained history, including Spam/Trash | **7,928** | **7,928** | **0** |

All listings completed. No stored ID was absent from the retained-mailbox listing.
The stored evidence dates span 2018-11-03 to 2026-10-27. These date bounds are
stored email evidence dates, not a claim about permanently deleted mail. The
connection is ready, has a history cursor and completed preview, and has no error.
Final decisions: 5,636 ignored, 1,318 review, 781 receipts, 167 automatic, 26 manual.
The 83 remaining old-parser rows are protected recorded/owner decisions; the
eligible-stale query is zero. All 147 protected rows captured before rechecks
match their private snapshot exactly.

The independent Analytics audit at 16:01:47.394755Z uses a repeatable enforced
read-only PostgreSQL snapshot. All 14/30/90/all-time uniqueness, lifetime totals,
status/cohort partitions and assessment/rejection evidence checks pass. All time:

- 945 identities = 897 applied marks + 48 external records, unchanged.
- Statuses: 751 Applied, 192 Rejected, 2 Screening. Rejected increased from 89 to
  192 through real imports/rechecks, not fabricated application records.
- 177 rejections have dates. Recorded status fallback is distinguished from
  verified email evidence; do not describe all 192 as independently email-dated.
- 193 recorded messages reconcile as 178 chosen email links, 14 deduplicated
  emails about the same application/kind and one undated status-only fallback.
- Inbox and Analytics pending totals both equal 1,318; zero orphan active outcome
  events. Pending messages are not silently counted as confirmed responses.
- Two potential cross-history duplicate groups, two older date conflicts and the
  one status-only message remain review limits. Six outcome-worded emails the
  owner filed as acknowledgements remain protected. No merge, destructive repair
  or override was performed.
- The ignored-mail indicators are 11 recruiting-system senders and 114 messages
  with application words, with overlap possible. Those are risk indicators rather
  than proof of missed outcomes. Complete ID coverage does not certify semantic
  recognition of every phrase, attachment or untracked historical application.

The API/web still run the approved release. Public HTTPS health at 16:01:44Z
returns exact frontend `5ab6b1a90decfcddf8b3866fe99a9627f0f2e574`, protected routes
return 401 when signed out, and representative public assets return readable
images. Running Analytics SHA-256 remains
`80db50ddcf0cb87a129680d8729ac1390fdb9947680ee79940f1cde6abd17074`;
Inbox SHA-256 is `e8847188e44163b375de8367971a437e9fc1f4b512259bd417c7099148bf99c2`,
matching approved commit `5ab6b1a`. API/web/scheduler/Postgres are healthy. Schema
`0050`, all nine protected inventory aggregates and all recorded service/image
IDs remain unchanged. This is public HTTP and read-only live-data verification,
not signed-in production browser or restore-drill evidence.

Coverage caches are process-local. The owner's next authenticated Inbox check
independently fills the API worker's snapshot by listing and reconciling history;
already imported IDs are not re-downloaded. Ongoing checks run while Inbox is
open. This release does not add an always-running Gmail worker. No additional
production action is authorized by a documentation commit.

The separately proposed parser-7 API fix remains unreleased, awaiting the
approval question sent during the import. Its exact runtime candidate is
`3294139f27eaae8985b58ce6294aae0242bd747a` in PR #7. All 293 focused backend tests,
hosted backend/web jobs, 47 extension browser cases and 30 focused Inbox/Analytics
cases pass. The full app browser result is 196 passed / 20 failed. Exact failure
sets match the approved parser-6 baseline, with zero new failing cases; the
overall e2e job remains failed. Exact candidate proof: run 40526589769, job
122268531501, focused step 13 completed 15:03:21Z. Do not deploy this candidate
under the earlier approval for `5ab6b1a`.


## Approved parser-7 API activation and ongoing rechecks, 16:30Z

The owner's reply to the specific parser-7 approval question was: “What about
the developments you did? I need everything to be live.” That authorizes the
remaining API activation and historical rechecks described in that question.
Canonical `wine-rose-platform` includes review merge `ab8d6f1`; its runtime/test
files are byte-identical to exact tested candidate
`3294139f27eaae8985b58ce6294aae0242bd747a`. The API image was built from that
exact candidate. PR #7 is merged. No web runtime changes remain beyond deployed
`5ab6b1a90decfcddf8b3866fe99a9627f0f2e574`.

API-only `up --no-build --no-deps --wait` was verified at 16:27Z. Parser 7 is
running and API/web are healthy. Web/scheduler/PostgreSQL/Caddy container and
image identities are unchanged. Schema remains `0050`. Running API image:
`sha256:c95437dd07cc9e90c766b28f07cbf5e9edc8aa388ce358ea1cdf1e16a5c13333`.
Source SHA-256:

- Inbox: `e3149312a7d2b15a95ad2ff0e79d2827a9453090921d7390a1a69b11e1e280fc`.
- Reconciler: `5eac2e8ef37408100f448f545940b3fb772d968bee82ed8fea0d6da7f225885f`.
- Analytics unchanged: `80db50ddcf0cb87a129680d8729ac1390fdb9947680ee79940f1cde6abd17074`.

A new private consistent backup is in
`/opt/ace/private-backups/inbox-parser7-20261027/`: mode-700 directory,
mode-600 `database.dump.gz`, 477,571,512 bytes, gzip and PostgreSQL archive
listing verified. No restore drill. Previous API image retained as
`oracle-api:before-inbox-parser7-20261027`. Eight inventory counts match exactly;
job marks rose 1,237→1,238. A private comparison against the fresh backup proves
zero existing job-mark rows changed or disappeared and exactly one added
dismissed, unapplied, unsaved job. Existing owner activity was preserved.
All 199 protected recorded/owner Inbox decisions match their fresh snapshot;
the prior 147-row snapshot was copied out before container replacement.

Public HTTPS health at 16:26:51Z returns the exact unchanged frontend commit
and healthy API; Inbox/Analytics require authentication, public images load.
Independent enforced-read-only reports at 16:29:29Z and 16:29:31Z verify:

- 7,928 retained Gmail IDs, all stored, zero missing, including Spam/Trash;
  every shorter comparison query also has zero missing.
- 945 identities = 897 applied marks + 48 external applications.
- 751 Applied, 192 Rejected, 2 Screening; 177 dated rejections.
- Inbox pending = Analytics pending = 1,318; all projection invariants pass.
- No orphan active outcome events. The two possible duplicate groups, two old
  date conflicts, one status-only record and six owner-filed outcome-worded
  acknowledgements retain their previously documented review limits.

A one-time paced operator runner started at approximately 16:30Z and re-listed
7,928/7,928 retained mail IDs with zero missing at 16:30:12Z. It is rechecking
**7,729 eligible historical messages** using deployed business rules; the other
199 decisions are protected. **These rechecks have not yet completed.** Reads
are spaced at least 0.7 seconds with quota cooldown handling and per-message
commits. The runner survives SSH disconnects, adds no scheduler/service, and
runs independent coverage, Analytics and both preservation comparisons after
completion. It requires zero eligible stale mail, zero missing IDs in every
query and passing Analytics checks. Private outputs use `parser7-final-*`.
A startup-only Python import-path failure was corrected with explicit
`PYTHONPATH=/app`; the failed attempt made no mail changes and is logged apart.

For continuation, inspect `parser7-recheck.log`, `recheck-runner-pid`,
`recheck-exit-status`, and the runner process in that backup directory before
starting another operation. `0` exit status plus final reports certifies the
checks ran; absent status does not certify completion. VM runner:
`/tmp/ace-inbox-parser7-runner.sh`. Container/VM restarts interrupt it but retain
committed SQL progress. Any later owner actions that change protected snapshots
must be investigated, never automatically undone.

All 293 focused backend tests and exact-candidate hosted backend/web, 47
extension browser and 30 focused Inbox/Analytics cases passed before activation.
The broader browser job remains failed on the same 20 cases as the prior live
baseline; no new failing cases were introduced. No migration, scheduler change,
extension publication, destructive repair or signed-in production browser test
was performed. Code activation and full ID coverage do not certify perfect
semantic recognition or completion of the ongoing parser-7 recheck.
