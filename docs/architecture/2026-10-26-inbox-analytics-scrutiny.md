# Inbox-to-Analytics scrutiny

Status: audited and corrected locally on `inbox-clarity-20261026`, draft PR #6.
Release approval is pending. Live parser 5 is unchanged. The initial candidate
`e6e6a93` is superseded by this follow-up; approve the final branch commit only.

## Verdict and audit boundary

Analytics reads real stored application records and outcome events. Its
arithmetic reconciles. It is not complete against Gmail, and distinct real-world
submission counts are not fully verified. No claim of perfect tracking is
supported. Imported messages, unique application identities and distinct
application/outcome kinds are different populations.

The audit used read-only PostgreSQL transactions and Gmail ID listing through
the existing coverage script. It imported no mail, ran no sync/recheck/review,
changed no owner decisions, created no auth sessions and performed no release,
migration, scheduler operation or data repair. Production remains on parser 5;
P1 to P5 and these corrections await approval. No real email text, company
identities, application keys, answers or tokens appear in this report or tests.

## Measured production evidence

Measurements are snapshots from 2026-10-26 evening Pacific. The aggregate audit
finished at 19:10:52 (2026-10-27T02:10:52Z); the projection comparison was at
19:01:57. Gmail coverage was measured earlier in this same audit session.

| Gmail window | Listed, complete | Stored from that listing | Missing |
| --- | ---: | ---: | ---: |
| 7 days | 274 | 274 | 0 |
| 30 days | 949 | 516 | 433 |
| 90 days | 1,625 | 516 | 1,109 |

The report uses date cutoffs with a one-day buffer and Gmail default Spam/Trash
exclusions. Its window labels are not exact rolling 24-hour intervals.

There are 516 stored emails: ignored 249, receipt 193, automatic 50, manual 24.
319 rows are under older parsers. The ready connection still lacks a history
cursor and completed preview. Missing mailbox messages are not automatically
missing application outcomes; full import and review are still required.

939 stored identities equal 892 applied job marks plus 47 external records.
All-time current statuses are 850 Applied, 86 Rejected and 3 Screening. There
are two potential job/external duplicate groups with identical company/title/
submission date and matching current status, but each external record lacks a
posting URL. Keep them separate until the owner verifies whether each pair is
one or two submissions. No fuzzy merge or deletion was performed.

| Submission selection | Application identities | Rejections | Dated rejections, live | Candidate |
| --- | ---: | ---: | ---: | ---: |
| 14 days | 262 | 33 | 29 | 31 |
| 30 days | 559 | 66 | 60 | 62 |
| 90 days | 939 | 86 | 64 | 66 |
| All time | 939 | 86 | 64 | 66 |

Every selection passes unique row/record totals, current-status partitions,
disjoint cohort partitions, assessment/rejection record counts and lifetime
totals against independently counted persisted marks/history. Submission-date
filters explain why 30-day and all-time rejection counts differ.

74 manual/automatic email records reconcile as follows:

- 64 represented by counted evidence with an email link.
- 6 deduplicated to another email for the same application and outcome kind.
- 4 represented only by an undated current stage. Two fit Inbox's 24-hour
  marking grace and should retain their email dates/links. Two manual decisions
  have email times more than a day before submission and remain excluded.

Five outcome-worded emails were explicitly owner-filed as acknowledgements:
one classifier-labelled rejection, one possible rejection, one interview and
two offers. Their wording labels do not override the owner's chosen filing.
The four raw ledger rows not joined to current application identities are
Applied/cleared bookkeeping; there are zero orphan active outcome events.

## Reproduced defects and local corrections

1. Analytics discarded confirmed emails just before the ACE Applied mark even
   though Inbox accepts a 24-hour marking grace. The projection now retains
   those linked outcomes, labels them as preceding the mark, and excludes the
   application from response timing when its first outcome predates the mark.
   No negative duration or inferred submission date is created.
2. A single earliest timestamp served both first-response timing and latest
   employer response labels. Separate first/latest projections now retain
   first-response timing but use latest dates and matching links for records,
   company recency and rejection sorting.
3. Any historical rejection dominated the cohort even after a later verified
   interview/offer. Chronology and authoritative current stages now decide the
   disjoint cohort; historical evidence still retains both outcome kinds.
4. Deferred emails were absent from Analytics review totals. They now have an
   explicit count/link and enter the total waiting count.
5. Inbox refreshed its own data without notifying the existing cross-tab marks
   bus. Changes now notify that bus; Analytics refreshes on opening/return as
   well as focus, visibility and evidence messages. No second count store.
6. Excluded evidence was silent. Owner-authenticated records now expose fixed
   exclusion reasons and separate review links. Analytics discloses measured
   Gmail coverage, snapshot time, pending/re-read counts and exclusions. An
   undated recorded stage is distinguished from explicit event actor provenance.
7. The global audit endpoint's 100-event cap could hide an old email's Undo.
   A message-filtered read now includes its events/undos before the cap, and
   the selected email fetches that history. Ownership checks remain enforced.
8. Opted-in live assessments recorded an event but left the application Applied;
   positive automation could also regress an Offer/Interviewing stage. Live
   assessment/recruiter outcomes now set Screening and stage regressions wait
   for review. Global/owner opt-in, authenticated employer origin, exact IDs,
   timing/final-status guards and historical previews remain in force.

## Read-only candidate comparison

The candidate Analytics source was evaluated only in a separate diagnostic
Python process using one repeatable read-only production snapshot. No running
service, source file or database record changed. Source SHA-256:
`e67da61ff031f447653dc74a17f584a5d475fdebc93ce064eb49f27ca54cfd1f`.

All time: dated rejections 64 to 66, 7 evidence links corrected, 6 latest-company
dates corrected. All 939 identities, current-status counts, 86 rejections and
3 positive-response identities are unchanged. The 65-application timing sample
and median are unchanged. Two older date conflicts remain explicitly excluded.
The diagnostic process still imported live parser-5 Inbox helpers, so its stale
count is not a simulation of the planned parser-6 recheck selector. Full Gmail
import/classification was not replayed or certified by this comparison.

## Repeatable validation and remaining work

`backend/scripts/inbox_analytics_audit.py` adds an aggregate-only repeatable
read-only PostgreSQL audit alongside the existing coverage report:

```bash
ssh -i ~/.ssh/ace_oracle ubuntu@161.153.89.170 'cd /opt/ace && docker compose --env-file .env -f deploy/oracle/compose.yaml exec -T api python -' < backend/scripts/inbox_analytics_audit.py
```

The command never calls Gmail or prints private text/keys. It reports persisted
totals, possible cross-history duplicates, range invariants, recorded-message
reconciliation and items needing review. `projection_checks_pass` validates
arithmetic, while `mailbox_coverage_certified` remains false. Exceptions expose
only their class, never SQL parameters. Use `inbox_coverage_report.py` separately
to compare actual Gmail IDs against stored evidence.

Validation: 255 focused fictional backend tests, 37 React render/workflow/DOM
contracts, TypeScript, focused ESLint, zero-hit dash and whitespace checks pass.
Tests cover the real ingest-to-Analytics, Undo and reassignment path, timing
grace and exclusions, latest/first distinctions, cohort order, deferred review,
audit purity/privacy, old email Undo, refresh propagation and positive-stage
protection. No Chrome or production browser rendering. Image builds remain a
gate for an approved release, not a completed check.

Next: approve the exact final commit for an API/web-only release under the safe
release procedure; then complete Gmail verification/rechecks through Inbox and
rerun both audits. Separately review the two old date conflicts and two possible
duplicate groups. Do not repair or delete them automatically. Complete fetched
ID coverage does not prove perfect wording recognition or establish full
historical response rates, resume attribution or channel attribution.

## Hosted CI follow-up

On source commit `c54a352`, GitHub backend and web jobs passed, including the
full hermetic backend suite, TypeScript, lint and a Next.js build. The hosted
browser job failed before any new-app tests: 20 extension tests passed and 27
failed fixture setup because the fixture opened `/`, expecting the removed
legacy Queue's global `render`. That unchanged API route redirects to Next.js,
which the job had not started. The same failure occurred on the initial
`e6e6a93` candidate. These failures are not passing Inbox browser verification.

The follow-up changes only that extension fixture to load a unique blank page
before each fictional form, and updates stale workflow descriptions. It does
not alter extension runtime behavior, remove assertions or skip tests. Chrome
remains prohibited locally; hosted CI must validate the fixture and then run
the new app suite. Check the final branch's CI result before release.
