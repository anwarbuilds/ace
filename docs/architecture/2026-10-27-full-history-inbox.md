# Full-history Inbox and Analytics, 2026-10-27

Status: locally implemented on `inbox-clarity-20261026`, draft PR #6. Nothing
from this work is deployed. Owner approval is required for the final commit.
This scope supersedes the initial 30/90/365-day reliable-Inbox candidate.

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

280 focused fictional backend tests and 40 React render/workflow/DOM tests pass.
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
