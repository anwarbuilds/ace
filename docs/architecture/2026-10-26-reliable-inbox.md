# Reliable Inbox P1 to P5

Status: implemented and tested locally on `inbox-clarity-20261026`, awaiting
owner approval to release. Production parser 5 is unchanged. No migration.

## Problem and behavior

The first catch-up read only one Gmail ID page and never established its
cursor when another page existed. A timestamp and empty review queue could
therefore look complete while older email was missing. Unknown application
mail was ignored permanently, and narrow rejection searches hid the reason.

P1 verifies the full selected Gmail window, deduplicates/chunks stored-ID reads
and saves at most 60 new emails per request. The page repeats until finished.
Each saved email survives a later failed read. Profile comes before listing;
only complete listings/history with zero remaining can advance the cursor.
Deleted mail is relisted before coverage is claimed. A missing profile cursor
is temporary failure. Per-connection process locks return busy for competing
sync/backfill/recheck calls; database uniqueness also protects duplicate writes.
Unrelated integrity failures propagate. A paused or replaced grant stops work.

Connection/sync responses carry ephemeral coverage per grant and window:
`days`, `gmail`, `in_ace`, `missing`, `checked_at`, `complete`. Restart and
reconnection require verification again. The report and implementation include
the calendar boundary day. The UI reports incomplete listings, progress and
errors accurately; 30/90/365-day verification replaces page-by-page import.
The compatibility backfill endpoint remains. This adds no server timer.

P2 parser 6 recognizes explicit eligibility and sponsorship declines with a
recruiting word, retaining sender authentication, single identity, final/newer
status protection and Undo. Conditional eligibility instructions stay manual.
Unknown application-related messages become unclear review candidates, excluding
job-board unknown mail and self-sent messages. No bodies are newly retained.
Positive automation still requires opt-in, an exact ID, employer origin and
an incremental history-added message; wider historical positives stay previews.

P3 rereads ignored recruiting mail under older parsers from the last 120 days,
using the same recruiting word lists in SQL. Owner decisions are preserved.
The page runs recheck automatically even after a recent Gmail check. Failures
refresh already-saved marks and preserve the chosen wider window for retry.

P4 empty records searches return up to 25 matching applications from all dates,
statuses and roles, plus up to 25 related stored emails and exact match totals.
Every query word must match; SQL wildcard characters are escaped. The page
explains dates, status and email disposition, links to existing controls and
Inbox, and offers all-time searches. Direct rejection links without selected
dates default to all time; explicit Analytics date selections are preserved.

P5 shows a company mismatch warning and asks for an explicit override before
an existing or newly added application receives an outcome. Exact squashed
names and initials count as named evidence. The guard does not alias parent
brands or loosen automatic matching. Cancellation makes no write.

## Validation

All tests use fictional mail, tokens and applications in isolated SQLite or
lightweight DOM fixtures. No real email text or personal answers were added.

```bash
nice -n 15 taskset -c 0 .venv/bin/python -m pytest \
  backend/tests/test_gmail_reads.py backend/tests/test_inbox_reconciliation.py \
  backend/tests/test_inbox_persistence.py backend/tests/test_inbox_display.py \
  backend/tests/test_analytics_read.py backend/tests/test_job_marks.py \
  backend/tests/test_external_applications_api.py backend/tests/test_auth.py \
  -q -p no:cacheprovider
cd web
nice -n 15 taskset -c 0 npm run test:inbox
nice -n 15 taskset -c 0 node --max-old-space-size=768 node_modules/typescript/bin/tsc --noEmit
```

Results: 241 backend tests and 32 React render/workflow/DOM tests pass. The
1,107-email regression covers multiple pages and 19 independently saved batches;
others cover quota recovery, cursor races/expiry, partial listings, deletion,
duplicate integrity races, paused connections, historical positive safeguards,
parser wording/false-positive boundaries, owner/Undo preservation, stale ignored
mail, search explanations and authenticated request validation. Actual component
tests verify auto-open behavior, failure states and mismatch cancellation/override.
Focused ESLint, TypeScript, whitespace and the zero-hit dash guard pass.

The retained Inbox Playwright cases were updated and collected only. Chrome,
browser screenshots and live employer verification remain prohibited here by
the cooling restriction. No production application images have been built
for this change; an approved release must pass the VM build before activation.

## Production baseline and release boundary

The approved existing `backend/scripts/inbox_coverage_report.py` was piped into
the running API once, read-only. It listed Gmail IDs and aggregate database
counts only. Parser 5; 516 stored; 7/30/90-day Gmail lists 274/949/1,625;
present 274/516/516; missing 0/433/1,109. All listings finished. Connection
ready without a cursor or completed preview. These are the pre-release
measurements from 2026-10-26 evening, not proof of a fixed production Inbox.

Ask the owner to approve the exact commit for an API/web-only release. Follow
the root knowledge file's Safe production release: fresh verified private
backup, prior image/container/schema/config inventory, exact SHA build and
activation of only API/web with no dependencies. No migration, scheduler,
database restore, Gmail permission change or extension publication is needed.

After an approved release, verify running API/web SHA and source hashes,
unchanged schema/protected services and authenticated read-only responses. The
owner opens Inbox to let it verify and reread automatically, then rerun the
coverage report and compare the selected window and actual Gmail/ACE counts.
Do not trigger production sync/recheck/review during release verification.
Parser 6 can recover old misses but deterministic wording cannot guarantee
all future employer phrasing; unclear application mail remains reviewable.
