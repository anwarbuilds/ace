# Resume matching and application tracking

> Part of the ace knowledge set (index: `README.md`). Dated entries, each a problem found, its cause, the fix and the lesson. An entry describes the system on its date: where it disagrees with the code, trust the code and fix the entry. Superseded entries carry a Status line.
>
> Read this when: you touch match scores, skills, marks, application status or the CSV export.

> **Status of the sheet entries:** The spreadsheet upload and import UI was removed on 2026-10-10 at the user's request, because applications are made through ace. Export CSV remains, and the API endpoints `/api/applications/preview` and `/api/applications/import` still exist, unused. The entries about the sheet are history; their lessons (never guess identity, wait for the write, show the user what was skipped) still apply.

## Matching is lexical, not semantic

Keyword overlap over a 96-skill vocabulary with an alias table. Chosen
over embeddings because it is explainable (matched/missing lists are
actionable), deterministic (ranks cannot drift), and free.

## Matching v2: partial credit for related skills (2026-09-06)

v1 recognised exact names only, so a posting asking for "scalability"
and a resume evidencing "distributed systems" scored as a total miss.

Two things were wrong, not one:

1. **Vocabulary.** Postings describe *qualities* more than technologies.
   "Scalable" appeared in 158 of 250 sampled descriptions and was not
   recognised at all. 15 concept skills were added - scalability, high
   availability, low latency, caching, event-driven, stream processing,
   data modeling, API design, infrastructure as code, experimentation,
   information retrieval, recommendation systems, and others.
2. **Relatedness.** `RELATED_SKILL_PAIRS` is a hand-curated graph of 79
   pairs. A requirement met by a related skill earns
   `RELATED_SKILL_CREDIT` (0.5) instead of 0.

Still curated rather than learned, for the reasons above: the user can
be told exactly *why* a skill counted, and nothing here breaks when a
credential expires.

Four properties keep partial credit honest, each pinned by a test:

- Matched and related lists are disjoint, so one requirement cannot be
  credited twice.
- Adjacency never outranks naming the skill outright.
- The graph is read **one hop only**. Transitivity would make pandas
  evidence of FastAPI by way of python.
- The graph is symmetric and validated at import; a pair naming an
  unknown skill raises rather than silently never matching.

**Re-scoring re-extracts resume skills from stored raw text.** Skills
are extracted at upload time, so after the vocabulary grows a stored
resume under-reports what it evidences and every later score inherits
the gap. This was not hypothetical: re-extraction gained the live resume
`distributed systems`, without which the flagship case above could not
have worked.

`algorithm_version` on each score row exists because scores are derived
data with no other staleness signal - a scoring change leaves every
stored row in place, still looking authoritative.

Live effect: scored postings 6,743 → 8,284 (bigger vocabulary clears the
3-skill floor more often), 10,172 rows earn partial credit, 12 of the
top 20 are newly ranked there. Median fell 53 → 50 because recognising
more requirements also enlarges the denominator - scores got more
honest, not worse.

---

## Application import never guesses (2026-09-06)

> **Status:** history. The spreadsheet upload and import UI was removed on 2026-10-10 at the user's request, because applications are made through ace. Export CSV remains, and the API endpoints `/api/applications/preview` and `/api/applications/import` still exist, unused. The entries about the sheet are history; their lessons (never guess identity, wait for the write, show the user what was skipped) still apply.

The asymmetry decides the design: a missed match costs one row the user
re-checks by hand, while a wrong match silently tells them they already
applied somewhere they did not, so they never apply. Three strategies,
strongest first: posting URL (normalized, tracking parameters dropped),
company plus exact normalized title, then company plus a 0.75 title-word
overlap. **When two postings are equally good the row is reported as
ambiguous and left to the user**, never resolved by an arbitrary
tiebreak. On a real file, Amazon's repeated "Software Development
Engineer" correctly came back ambiguous with four candidates.

Import is two steps. Preview reads the file and writes nothing; import
records only the rows the user confirmed. A one-step import would mean
the first sight of a wrong match is after it is stored.

`applied_at` is separate from `updated_at`: an imported application
happened on its own date, while the row was written today. A row with an
unreadable date is still recorded, stamped with the import time, because
losing a real application over one blank cell is worse than an
approximate date.

Applied is a filter and a badge, never a page, per the IA decision.

---

## Application status, not just a date (2026-09-07)

> **Status:** history. The spreadsheet upload and import UI was removed on 2026-10-10 at the user's request, because applications are made through ace. Export CSV remains, and the API endpoints `/api/applications/preview` and `/api/applications/import` still exist, unused. The entries about the sheet are history; their lessons (never guess identity, wait for the write, show the user what was skipped) still apply.

`job_marks.application_status` (migration 0017) with applied, screening,
interviewing, offer, accepted, rejected, withdrawn, ghosted.

Separate from `applied_at`, which records when it was sent and never
moves. Collapsing them would make a rejection overwrite the date it was
applied, losing the history exactly when it becomes interesting.

Setting a status implies an application was sent, so `applied_at` is
backfilled if absent: "rejected" on a posting ACE believes was never
applied to is nonsense. Clearing applied clears the status too.

The importer reads a status column through a synonym table, so
"rejected", "declined", "no" and "closed" all land in the same place and
re-uploading an updated sheet moves jobs forward. Anything unrecognised
returns None rather than a guess, because a wrong status would claim a
live application was rejected.

**Watch the two `status` fields.** The import preview row carries both
the match outcome (matched / ambiguous / unmatched) and the parsed
application status. They collided on first write and the second silently
overwrote the first, which would have broken the entire import UI. The
application one is `application_status` in that payload.

---

## The corpus has a start date, and it matters (2026-09-07)

ACE first saw anything on **2026-08-29**. The user's application history
predates it, and only those postings
still open on the 29th could ever be linked, because a posting that
closed before ACE first polled was never stored and never can be.

This is not a matching failure and must not be presented as one.
`/api/stats` exposes `corpus_started_at` so the interface can say it
plainly rather than implying ACE lost something.

Three fixes came out of it.

**Company spacing.** "Open AI" did not match a stored "OpenAI", hiding
782 postings. `tighten_company` compares the spaceless forms as a
fallback. **Partial names** ("Chase" against "JP Morgan Chase") are
pooled on whole-word containment and left to the title checks, which
report ambiguity rather than picking.

**Title abbreviations.** `TITLE_ABBREVIATIONS` expands SDE, SWE, MTS,
FDE and similar on both sides, so a tracker written short still overlaps
the title as posted. The 0.75 overlap threshold stays: Roblox holds only
Senior and Principal roles, so an early-career "SDE" there is an honest
miss, and lowering the bar would offer twenty wrong choices instead.

**Standalone applications** (`external_applications`, migration 0018)
keep history with no posting to attach to. Identity is normalised
company plus title, so re-importing an updated sheet moves a row forward
rather than duplicating it. They are never auto-linked to a job ACE
later discovers: a repost is a different opening.

## Re-uploading the sheet is the daily habit (2026-09-07)

> **Status:** history. The spreadsheet upload and import UI was removed on 2026-10-10 at the user's request, because applications are made through ace. Export CSV remains, and the API endpoints `/api/applications/preview` and `/api/applications/import` still exist, unused. The entries about the sheet are history; their lessons (never guess identity, wait for the write, show the user what was skipped) still apply.

The user applies daily, so import is a repeated action, not a one-off.
Three properties make that safe:

**A status moves forward.** Re-importing a row whose sheet now says
rejected updates the stored status and timestamps the move.
`applied_at` is taken from the sheet, which is the source of truth for
when it was sent.

**A blank status cell never erases.** `set_mark` treats
`application_status=None` as "leave alone", so a sheet without a status
column, or with that cell empty, cannot wipe a rejection recorded
earlier. Verified against live data before shipping.

**An earlier choice sticks.** Ambiguous rows would otherwise have to be
re-resolved by hand on every upload, which for 16 rows a day is a chore
that would kill the habit. `match_row` takes `already_applied`, and a
single candidate already carrying an application settles the row as
"your earlier choice". Two applied candidates stay ambiguous, because
the sheet genuinely cannot tell them apart.

## Marked pages must ignore the gate (2026-09-07)

The Applied page showed only a fraction of the applications. `mark=applied` still had
the default `statuses=PASS` and `active_only` applied, so any posting
ACE had since judged senior, out of family, or closed vanished from the
user's own history.

The gate answers "should you apply to this". Asking it about something
already applied to is meaningless, and it silently deleted most of the
record. Marked pages (saved, applied, archive) now bypass both the
eligibility filter and the active filter. The Queue still respects them,
and a test pins that the exemption did not leak.

---

## An import looked like it did nothing (2026-09-07)

> **Status:** history. The spreadsheet upload and import UI was removed on 2026-10-10 at the user's request, because applications are made through ace. Export CSV remains, and the API endpoints `/api/applications/preview` and `/api/applications/import` still exist, unused. The entries about the sheet are history; their lessons (never guess identity, wait for the write, show the user what was skipped) still apply.

Importing from the Queue appeared to change nothing. It had worked: the
rows were marked applied, and under the default `unapplied_first` sort
they immediately sank past position 700, out of the 60 loaded. From the
user's seat, rows vanished instead of statuses updating.

Import now lands on Applied, where the result of the action is what
fills the screen. API reads are also `no-store` on both sides, since
every route describes rows the scheduler and the user are both
changing.

## The sheet round trip was a missing button (2026-09-07)

> **Status:** history. The spreadsheet upload and import UI was removed on 2026-10-10 at the user's request, because applications are made through ace. Export CSV remains, and the API endpoints `/api/applications/preview` and `/api/applications/import` still exist, unused. The entries about the sheet are history; their lessons (never guess identity, wait for the write, show the user what was skipped) still apply.

The user asked twice why an uploaded spreadsheet did not show up
immediately. Both answers were real and both were fixed: the import
now lands on the Applied page, and every response carries
`Cache-Control: no-store`. But neither addressed why the spreadsheet
existed in the first place.

A queue row offered Save, Reviewed, Not relevant and Open. It did not
offer Applied. Recording an application meant either the `a` key,
which nothing on screen mentions, or opening the job page. So the
habit that formed was: apply in the browser, type it into a sheet,
upload the sheet, and wait for ACE to reconcile 75 rows against a
corpus that only starts on 2026-08-29.

The fix inverts the flow rather than speeding it up.

**Mark applied from the row.** One click, on the row already in front
of you, at the moment you applied.

**Export instead of import.** `GET /api/applications/export.csv` emits
the user's own columns (Company Name, Role Title, Type, Date Applied,
Status, Link), merges stored postings with the external records that
have no posting behind them, and sorts the whole thing newest first
with undated history last. It drops into their existing tracker
without being reformatted, which is why the dates keep the sheet's own
yearless `7 September` shape.

Import stays. It is how three years of history and any application
made outside ACE get in. It is no longer the daily path.

**A just-applied row is held for one load.** The default sort sinks
applied jobs, and the queue is thousands long, so the next load would
drop the row off the page and the click would read as the job
vanishing. `state.pinned` and `state.heldRow` re-insert it once.

## The import dropped rows on the floor (2026-09-07)

> **Status:** history. The spreadsheet upload and import UI was removed on 2026-10-10 at the user's request, because applications are made through ace. Export CSV remains, and the API endpoints `/api/applications/preview` and `/api/applications/import` still exist, unused. The entries about the sheet are history; their lessons (never guess identity, wait for the write, show the user what was skipped) still apply.

The user reported applications still missing after uploading their
sheet. The cause was a gap between the import's two buckets.

`importChoice` was pre-populated only for `matched` rows, and
`unplaceableRows()` collected only `unmatched` and `unusable` ones. An
**ambiguous** row was in neither. Its dropdown defaulted to "Skip", so
unless the user opened every one of them by hand, the row was not
attached to a posting and not kept as history. It silently disappeared,
and nothing in the dialog said so: the button read "Import 42 and keep
8" while quietly discarding 12.

`unplaceableRows()` also required `r.company && r.title`, so a row with
a company but no title was dropped too, even though "unusable" is
defined as needing a title.

Reproduced against the live corpus with a four-row sheet: two ambiguous,
one unmatched, one untitled. Three of the four were lost. After the fix,
none are.

**The rule the buckets now follow.** Every row that will not become a
job mark is kept as history. Ambiguity is a reason to not guess which
posting it was, never a reason to forget the application happened. The
dropdown now reads "Keep as history" rather than "Skip", and choosing a
posting moves the row between buckets with both tallies redrawn.

**Choosing later removes the placeholder.** `drop_external_duplicates`
deletes standalone records whose `external_match_key` matches a job just
marked, so resolving an ambiguity does not leave the application listed
twice. Keyed on company and title together, so unrelated history at the
same company survives.

## Keeping every row exposed two more bugs (2026-09-07)

> **Status:** history. The spreadsheet upload and import UI was removed on 2026-10-10 at the user's request, because applications are made through ace. Export CSV remains, and the API endpoints `/api/applications/preview` and `/api/applications/import` still exist, unused. The entries about the sheet are history; their lessons (never guess identity, wait for the write, show the user what was skipped) still apply.

Sending ambiguous rows to the history bucket made two latent faults
reachable on the very next import, which failed outright.

**One sheet, two rows, one key.** `record_external_applications`
looked for an existing record with `session.scalar(select(...))`, which
cannot see a record added earlier in the same loop because nothing has
flushed yet. Two rows sharing a `match_key` therefore built two objects
with the same key and died on the unique index. The user's sheet holds
"Software Engineer - Cloud Infrastructure and DevOps" and "Software
Engineer- Cloud Infrastructure and Devops" at PayPal, which normalise
to one key, and that took the whole import down with 46 rows pending.
A `pending` dict now carries records not yet flushed, so a batch merges
rather than collides, and the later row wins.

**Untitled rows were refused server side.** The guard was
`if not company or not title: continue`, so the row the client had just
offered to keep was silently dropped anyway. A missing title is
survivable: the company and the date still say an application happened.
A missing company is not, because it names nothing and cannot be
de-duplicated.

Both are latent bugs older than the change that exposed them. Two rows
that normalised alike would always have collided.

## The sheet round trip asked the same 42 questions every time (2026-09-09)

> **Status:** history. The spreadsheet upload and import UI was removed on 2026-10-10 at the user's request, because applications are made through ace. Export CSV remains, and the API endpoints `/api/applications/preview` and `/api/applications/import` still exist, unused. The entries about the sheet are history; their lessons (never guess identity, wait for the write, show the user what was skipped) still apply.

The user wanted the spreadsheet and ACE to stay in step in both
directions: mark a job applied here and it should reach the sheet;
type a Google job into the sheet, which ACE cannot see at all, and it
should reach ACE. Both halves already existed. What did not work was
doing it twice.

Exporting the real history and immediately re-importing that exact
file produced 129 matched, 21 ambiguous and 21 unmatched. All 42 of
the rows ACE presented as needing attention had already been answered
and stored: they were hand-typed rows ACE could not pin to one posting
and had kept as standalone history. `preview_import` knew about jobs
and about marks, and nothing about the history it had written itself,
so a row kept as history came back as an open question on the next
upload, and every upload after that. Re-uploading is meant to be the
daily habit; re-answering 42 questions daily is not.

A row ACE already holds is now reported as `RECORDED` rather than as a
question, and is sent back on every sync without being confirmed so its
date and status move forward from the sheet. The candidates are kept on
it, so attaching one to a real posting stays available, it is just no
longer demanded. Settled is not the same as closed. Measured on the
real corpus afterwards: the whole sheet, zero questions, and repeated syncs
converge rather than drift, with sheet rows exactly equal to marks plus
history.

The user chose "sheet always wins" for a status disagreement. That was
already the behaviour, and a blank cell still never erases what ACE
knows, which matters much more now that these rows are re-sent
automatically rather than ticked by hand.

## The exported sheet was a day ahead, and upside down (2026-09-09)

> **Status:** history. The spreadsheet upload and import UI was removed on 2026-10-10 at the user's request, because applications are made through ace. Export CSV remains, and the API endpoints `/api/applications/preview` and `/api/applications/import` still exist, unused. The entries about the sheet are history; their lessons (never guess identity, wait for the write, show the user what was skipped) still apply.

Two complaints about the same file. The first 23 rows were dated 10
September when it was still the 9th where the user was, and the whole
sheet ran newest-first while theirs runs oldest-first, so it arrived
reversed relative to the file it was meant to slot into. The order was
one line; the dates were not.

Instants are stored in UTC, which is correct and unchanged. The CSV
export formatted them in UTC too, which is a different question:
"which day was this" is asked from where the person was standing. An
application marked at 19:43 on the US west coast is 02:43 the next day in UTC, so
the sheet said the 10th. The web client never had this bug, because it
formats from an ISO string in the browser and picks up the reader's own
zone -- which is exactly why the user noticed: ACE's own screen and the
sheet ACE exported disagreed about the same application.

Rendering now goes through a `display_timezone` setting, defaulting to
America/Los_Angeles and validated at startup so a bad zone name is
refused rather than silently falling back to UTC.

The display bug had already become a data one. Re-importing the
exported sheet read the wrong date back as a real date and stored it,
replacing the click's own instant with noon UTC on the following day.
`backend/scripts/repair_applied_date_drift.py` undoes that, and its
restraint is the interesting part: 73 marks have an applied date
differing from when ACE recorded them, and only 10 are damage. A job
applied to in August and typed into the sheet in September also has two
different dates, and there the sheet's date is the truth. The repair
fires only on the exact signature -- stored at noon UTC, marked at or
after 17:00 local, stored date exactly one day later -- and restores
the instant from `status_changed_at` rather than inventing a new noon.
Most of its tests pin rows it must not touch.

Worth remembering that noon UTC, chosen for imported dates long before
any of this, is what made the repair possible: it is the only stored
time that survives a ±12h shift without changing date, so it doubles as
a reliable marker of "this date came from a sheet, not a click".

## A URL match, the most confident method there is, matched the wrong job (2026-09-09)

Found while checking whether the round trip above ever listed one
application twice. `normalize_url` dropped the whole query string, on
the reasoning that it carries tracking parameters and "the path is what
identifies the posting". That is false on every Greenhouse-hosted
board, where the path is a constant like `/jobs/search` and the posting
id lives in `?gh_jid=`. Five Stripe postings, three IXL ones and more
collapsed to a single identity; `by_url` is a dict, so whichever landed
last won and the rest were unreachable.

The failure was not a missed match, it was a confident wrong one. A
sheet row carrying the exact URL of Stripe's "Abuse Investigator"
matched an unrelated posting and reported `MATCHED` by `"url"` -- the
strongest signal in the matcher, which nothing downstream questions.
That is precisely the property `test_two_equally_good_candidates_are_ambiguous_not_guessed`
calls the central safety property of the whole import: a wrong match
tells the user they already applied somewhere they did not, so they
never apply.

Fixed by keeping the query and dropping only parameters known by name
to be tracking. That alone would have broken the older, real case of a
saved copy carrying a parameter ACE's copy does not, so a second step
falls back to the path -- but only where the path names exactly one
posting. Where it names several, falling back is the original collapse,
so the row is left to company and title instead. Measured over 300
random real postings matched by their own URL: 300 correct, none wrong.
Before the fix the same check matched the wrong posting outright.

## Two copies of one job, and the mark went to the wrong one (2026-09-10)

The user clicked Applied on a job's detail page, got the toast, and
watched the page carry on saying "Not applied yet" with the Applied
button unlit. Reloading showed it correctly, so the write had worked.

The same posting can be held in memory four ways at once: in
`state.items`, in a pull session's own job list, in `state.detailJob`,
and in `state.heldRow`. `jobById` returns whichever it finds first and
checks the session lists **before** `state.detailJob`, so a job reached
from the Pulls feed had its session copy updated while the copy the
page was rendering from was left alone.

`applyMark` now writes to every copy. Reproduced first, which mattered:
the initial attempt to verify used a job that happened to have only one
copy in memory, so it passed without touching the bug. Forcing the real
condition (job 44464, present in both the pulls feed and as the detail
job) showed "Not applied yet" before and "Applied, applied Sep 10"
after.

Worth noting the backend was already right. `set_mark` has recorded
`applied_at` whenever a status is set for a while now, on the reasoning
that a status implies an application was sent. The whole failure was
client-side state.

## A closed posting listed again looked unapplied (2026-10-12)

The user saw jobs they had already applied to arriving again in the pulls and asked to be told they were applied.
The data explained it: Microsoft closed "Software Engineer" in Redmond (the postings applied to on Oct 2, 4 and 8) and listed
the same title and place again under new ids on Oct 12. Each listing is its own job, so the mark stayed on the closed rows
and the new ones had none. An Amgen role held twice in one run did the same. The queue also folds similar openings into one
header ("Software Engineer, 3 similar openings"), which hid even the marks that did exist, so a whole group of re-listings
read as new.

The mark is not copied across. Whether a second listing is the same opening is something only the user knows (an employer can
hold six open requisitions with one title), and this file already records what guessing an identity cost. Instead the notice
is derived when a page is read and never stored: `applications/prior.py` finds, for a job with no applied mark of its own,
earlier applied jobs with the same company and title (ignoring case and spacing) and a compatible place (the same first place,
or one side naming only a country; "Remote" never matches a city). `/api/jobs` returns `applied_before` with the latest such
posting, its date, whether it is still open, and how many match. It shows as an amber "Applied before, Oct 4" on the row and
in the job page header and status card (with a link to the earlier posting), as "k already applied" on a group header, in the
desktop notification, and in the alert email (plain text and HTML, date in the user's zone).

The notice also carries the employer's requisition number for both postings. The first complaint after release was an
Expedia role whose notice read "You applied to this" while the two postings were both open with different requisitions
(R-108814 applied on Oct 8, R-110488 new): a second opening that looks the same, not a re-listing. The text now says
"This posting is requisition R-110488, so it may be a separate opening" when the numbers differ, and "Same requisition"
when they match.

Verified on live data first: the Redmond re-listings pointed at the Oct 4 application with six matches, the Amgen twin at the
role marked that morning, and a 200 row page still answered in 0.2 s. Lesson: a mark belongs to a posting, but the user's
question is about the opening, so show the resemblance and let them decide; and any summary row that hides its members
(a collapsed group) has to carry the warnings its members would have shown.

## Scores now follow the corpus, and say why they are missing (2026-10-14)

Reported on 2026-10-10: almost every job in the queue showed "n/a", and the job page said ACE "could not read this
posting". Cause: `rescore_corpus` was the only writer of `job_resume_scores` and ran only on resume upload, so every job
found after 2026-09-06 had no row at all, and the page treated "no row" and "row with no score" as the same thing.

Fix: `score_unscored_jobs` (in `matching/service.py`) runs from the scheduler's cycle recorder before the pull is
recorded and alerted. It scores active PASS jobs that have no row for the active resume, whose evaluation was rewritten
after they were scored (the posting changed, or the gate did), or whose row came from an older
`MATCHING_ALGORITHM_VERSION`; at most 2,000 per cycle so a backlog drains over a few cycles. A refreshed row keeps the
old number in `previous_score`. A job that throws is logged as `job_score_failed` and skipped, so it is retried and
never carries an invented score. Bounded to the queue on purpose: an upload still rescores the corpus.

The API now returns `match_state`: `scored`, `pending` (not scored yet), `no_description` (requirements never read),
`insufficient` (read, too few recognised skills to rank), `no_resume`. Both UIs word each one differently.

Lesson: a derived table with one writer goes stale silently. Ask which events should refresh it (new row, changed input,
changed rules, changed algorithm), and test each one. Tests: `backend/tests/test_score_sweep.py`.

## The Inbox looked synced when it was not (2026-10-26)

The owner opened Inbox Intelligence to "Waiting for you: 0" and "Last sync" a few minutes old, while Gmail held a fresh
rejection from a shared Ashby sender that the dashboard never showed. Three things made the page look settled when it
was not. Nothing read Gmail in the background: email arrived only when a button was pressed. "Last sync" also moved
when an older import page ran, so it could show a recent time while new email had never been fetched. And a rejection
that opens with "thank you for applying" was filed as a receipt whenever its decisive sentence went unread (body
extraction failed, so only Gmail's short snippet was classified), and receipts never reach Waiting for you.

Fix (parser version 3, branch `inbox-clarity-20261026`): the page checks Gmail when opened and while open, one Sync now
button also re-reads email kept under older rules, and a status card states when Gmail was last checked and whether
anything waits. `last_synced_at` means only the last check for new email. A receipt that also sounds like a decision,
or that was read only from its snippet, waits for the owner; receipts ACE filed itself are read again by recheck, the
owner's never. A Recruiting email view lists everything about applications with what ACE did, and search reaches every
imported email. The review shows the email itself, rebuilt from an allowlist into a sandboxed frame with no scripts
and no pictures fetched from the sender (`backend/app/inbox/display.py`, `components/inbox/EmailFrame.tsx`).

Lesson: a status line must describe the exact thing it names. "Last sync" written by two different operations, and a
"nothing to review" that excludes the bucket a misread email lands in, both read as "all done". Show what the system
did with each recent item and let the owner search, so a miss is visible instead of silent. Tests:
`backend/tests/test_inbox_display.py`, the parser 3 cases in `test_inbox_reconciliation.py`, the view, search and
recheck cases in `test_inbox_persistence.py`, and `web/tests/inbox-review-render.test.mjs`.

Follow-up the same day, found by a read-only production check after release: Analytics showed only 1 dated rejection
although 29 emails had changed an application. Its "one email substantiates one application" rule counted Inbox's own
`email:<id>` audit entry, which every imported email has, as a second application, so every email outcome was dropped
and showed only as an undated status. Only job and external keys count now (27 of 47 dated afterwards). Lesson: a
fixture that omits the audit rows production always writes cannot catch this; build test data in the production shape.
Test: `test_email_outcomes_count_despite_the_inbox_audit_entry_every_email_has` in `test_analytics_read.py`.

Later the same day: the owner asked how to choose the application for two Workday emails that waited with none
picked. Workday sends from `<tenant>@myworkday.com` (for example `generalmotors`), and ACE ignored every platform
address, so the employer was never named. Parser 4 reads the Workday tenant (other shared platforms still never name an
employer), and the review panel suggests applications the sender or subject names, including initials such as GM,
before the owner types. The owner also rejected a richer Rejected companies table in favour of the original card grid:
summary panels stay compact, and search and paging live on the drill-down page. Tests:
`test_a_workday_tenant_names_the_employer` and the suggestion case in `web/tests/inbox-review-render.test.mjs`.

## Inbox looked reliable and was not: coverage, ignored mail and wording (2026-10-26)

Status: diagnosis retained; P1 to P5 implementation below is local and awaiting release approval.

The owner showed an employer update email from a week earlier that never reached Rejected applications. Measured
against production (read-only): Gmail listed 946 emails for 30 days and ACE held 512, because a sync with no history
cursor lists one page of 500 and never pages on, so the cursor is never set and everything older than the newest 500 is
only reachable through the manual 100 per page import (1,110 of 1,622 missing for 90 days). Of the stored emails, 248
were decided `ignored` ("No outcome found") and the recheck never reads ignored mail again, so 319 emails sat under an
older parser; 112 ignored emails came from recruiting systems and 179 had application words. The reported email said the
employer's immigration policy does not include sponsorship: no rejection phrase matched, so it was ignored although the
application existed and its acknowledgement had been linked by the Workday tenant.

Lessons: a "caught up" status must be proven against the source (Gmail's own listing), not inferred from a timestamp; a
classifier needs a safety net so that anything about an application that it cannot read reaches the owner instead of an
ignored pile; and a re-read must cover every decision the new rules could change, ignored included. Plan and acceptance
tests are in `ACE_NEXT_KNOWLEDGE.md`, "OPEN WORK for the next chat: a reliable Inbox". Tool:
`backend/scripts/inbox_coverage_report.py` (read-only, counts only).


## Reliable Inbox P1 to P5 implemented locally (2026-10-26)

Complete ID listing plus independently saved 60-email batches replaces the
one-page catch-up. Coverage is measured against Gmail IDs, stored only in memory
per connection/grant/window and reverified after restart. Listing/profile order,
history expiry, partial listings, concurrent requests, quota failures, deletion
and pause/disconnect have fictional regressions. Historical positive outcomes
never become live automation just because the connection already has a cursor.

Parser 6 recognizes explicit sponsorship/eligibility declines while conditional
instructions stay manual. Unknown application mail reaches Needs you; recent
ignored recruiting email is reread after the bump, including on page open.
Empty search results explain matching applications across filters and related
imported mail. A manual company mismatch warns and requires an explicit override.
No historical owner decision is silently repaired. Events and Undo remain.

The fresh approved read-only baseline still found 433 of 949 listed 30-day
emails absent from ACE (516 stored); it imported or changed nothing. Tests are
fictional, not production verification. Release and subsequent source-versus-ACE
comparison remain pending owner approval. Details and commands:
`../architecture/2026-10-26-reliable-inbox.md` and the root OPEN WORK checkpoint.


## Stored counts can reconcile while Inbox evidence is still incomplete (2026-10-26)

Status: local audit corrections awaiting release approval; live parser 5 is unchanged.

The owner's request for a deeper scrutiny confirmed 433 missing 30-day Gmail
messages and independently reconciled all 939 stored application identities.
Matching sums proved the projection's arithmetic, not exhaustive source recall
or distinct submissions: two company/title/date pairs across job and external
history lack enough posting evidence to deduplicate safely.

Four recorded emails lost Analytics dates/links; two fit Inbox's existing
24-hour marking grace and are recovered locally without a negative or invented
response time. Two older conflicts remain explicitly excluded and reviewable.
Repeated outcomes exposed the use of earliest timestamps for "latest" labels.
Separate first/latest projections now preserve response timing while correcting
recency, evidence links and chronological cohort precedence. Deferred messages
are accounted for and the existing marks bus refreshes Analytics after Inbox
changes. A selected email's filtered event history makes Undo reachable beyond
the global 100-event audit page. Undated stages no longer acquire an invented
owner actor. Opted-in live assessments set Screening and cannot regress a later
Interviewing/Offer stage.

Read-only production replay of the candidate projection corrected 7 links and
6 company dates, kept 939 records and all status/outcome totals, and preserved
the timing sample/median. Five owner acknowledgement choices stayed intact.
The repeatable aggregate audit is `backend/scripts/inbox_analytics_audit.py`;
mailbox coverage still comes from `inbox_coverage_report.py`. A green count check
cannot certify that every email was fetched or understood. Full evidence:
`../architecture/2026-10-26-inbox-analytics-scrutiny.md`.


## 2026-10-27: owner requires all Inbox history

All time is now the default for Inbox sync/backfill and Analytics. This supersedes
the initial 365-day ceiling. Full listing includes retained Spam/Trash, uses a
bounded resumable manifest and reconciles changes from the pre-list cursor before
claiming a snapshot complete. Stale ignored mail has no age/keyword exclusion.
Owner decisions and Undo stay protected; Spam/Trash outcomes require review and
historical positives retain previews. No schema, scheduler or Gmail permission
changes. Explicit date selections remain correctly bounded/labeled.

Latest read-only evidence: 7,927 retained Gmail IDs, 524 stored, 7,403 missing;
945 persisted application identities reconcile (897 job marks + 48 external),
all-time rejections 89. Missing messages are not all missing outcomes, and
permanently deleted mail cannot be recovered. Two possible duplicate pairs and
two old date conflicts remain for review. 286 focused backend/42 DOM contracts
pass; final hosted CI, owner release approval and actual full import verification
remain gates. No production write or release occurred. Evidence and exact UTC
snapshots: `../architecture/2026-10-27-full-history-inbox.md`.


## 2026-10-27: approved full-history Inbox release is live

Owner-approved API/web commit `5ab6b1a` is live, parser 6, schema unchanged at
`0050`. Health/version/auth checks and protected aggregate preservation passed
after a fresh verified private backup. All-history imports and old-parser
rechecks are now authorized and running through the deployed service, with
manual decisions/Undo and existing automation safeguards retained. Coverage
remains incomplete until the final independent Gmail-ID inventory verifies it.
The live read-only projection audit passes all selection/count/cohort/evidence
checks; at its 14:27Z snapshot, previously missing emails raised recorded
rejection-evidence applications from 89 to 106 without creating applications
(945 identities). Historical baseline/pending-release notes above are superseded
by the root Current release checkpoint and
`../architecture/2026-10-27-full-history-inbox.md`. Broader browser CI still fails;
focused Inbox/Analytics 30, extension 47, backend and web checks pass.


## 2026-10-27T16:01Z: full-history live import and verification complete

The owner-approved parser-6 API/web release `5ab6b1a` completed the full retained
Gmail import and 441 eligible old-parser rechecks. The independent coverage
report verifies 7,928 Gmail IDs, all 7,928 stored, zero missing, including
Spam/Trash; all comparison windows also have zero missing. The history cursor
and completed preview are set, with no eligible stale mail remaining. Eighty-three
older-parser records remain intentionally protected. All 147 snapshotted
recorded/owner decisions were preserved.

The enforced read-only projection audit passes for 14/30/90/all-time selections:
945 identities = 897 applied marks + 48 external records; current statuses are
751 Applied, 192 Rejected, 2 Screening. Rejected rose from 89 to 192; dated
rejections are 177. Inbox and Analytics both expose 1,318 pending messages.
Counts reconcile, but outcome wording/matching and pending owner decisions are
not certified perfect. Two potential duplicate groups, two old timestamp
conflicts, one undated-only recorded message and six protected owner-filed
acknowledgements remain explicit. Nothing was merged or repaired destructively.

Separate candidate `3294139` (draft PR #7) fixes an additional fictional
long-email truncation failure and requires review for partial outcomes. Its
293 focused backend, hosted backend/web, 47 extension browser and 30 focused
Inbox/Analytics browser checks pass. The broader app suite has the exact same
20 failures as the approved baseline, with zero new failing cases (196 app
browser passes total). It has not been deployed; another API activation awaits
owner approval. See the root Final live verification and the full-history report.


## 2026-10-27T16:30Z: remaining parser-7 development approved and live

The owner answered the specific API-only parser-7 release question by requesting
all developments be live. PR #7 is merged; exact tested API runtime `3294139`
(parser 7) is live and healthy. Web already contains all developed changes and
remains `5ab6b1a`. Fresh private backup/rollback image retained, schema `0050`,
web/scheduler/PostgreSQL/Caddy identities unchanged. All 199 protected Inbox
rows match their snapshot. A one-row job-mark increase is a new unapplied
dismissal; private comparison proves zero existing rows changed or disappeared.

Independent 16:29Z coverage still verifies all 7,928 retained Gmail IDs stored,
zero missing. Analytics invariants pass with 945 identities, 192 Rejected,
177 dated rejections and 1,318 pending. Semantic and owner-review limits remain.
The additional 7,729 eligible parser-7 rechecks run in a one-time paced operator
process with per-message commits and automatic final read-only reports. They
are **not yet complete**. Check private VM directory
`/opt/ace/private-backups/inbox-parser7-20261027/`, `parser7-recheck.log` and
`recheck-exit-status` before resuming. Details are in the root Current live
release and `../architecture/2026-10-27-full-history-inbox.md`.


## 2026-10-27: owner narrows Inbox scope; triage draft saved unfinished

The owner objected that 1,318 manual tasks defeats Inbox Intelligence. A live
aggregate audit at 16:34Z found 1,093 generic unclear messages, 225 recognized
outcomes with unresolved matching/policy, and 855 messages older than the first
recorded application (overlap). A later handoff snapshot is 7,931 stored and
1,320 review; the reported “13018” UI number has not been verified as 13,018.

The owner wants job-related mail across all dates, excluding Spam/Trash and
personal mail, with routine correspondence handled automatically and genuine
ambiguities only for review. The exhaustive parser-7 operator was stopped at
16:36:09Z, expected exit 143, no operator left; never restart it under the new
scope. Live API is still parser 7, web `5ab6b1a`, schema `0050`.

The local parser-8 backend draft adds Gmail job candidate selection, scoped
history re-listing, shared SQL/Python queue projection for searchable passive
correspondence, and initial routine-subject handling. It is unfinished and
untested beyond compilation/whitespace. Its age cutoff and routine guard are
provisional and require careful review to preserve real historical outcomes.
Frontend, independent scoped coverage report, tests and actual context/thread
matching remain unfinished. No new deployment or production queue cleanup ran.
The full standalone continuation is the root START HERE section; resume in
`/home/ubuntu/Documents/ace-inbox`, preserve the seven draft runtime files, test
with fictional data, measure production read-only and ask for a specific release.


## 2026-10-27: job-mail triage candidate completed, not released

Resumed checkpoint `053ae41`. Removed provisional historical suppression,
protected partial/owner/deferred/Undo evidence, made old unclear mail eligible
for actual scoped reclassification, added metadata label preflights and bounded
history re-selection, and shared the queue policy across Inbox and Analytics.
Routine notices and bare assessment brands no longer create outcome tasks;
explicit body outcomes win over generic account subjects. Consistent same-sender
thread evidence can disambiguate rejections without relaxing status/auth/timing
or positive-automation guards. All retained evidence remains searchable.

319 focused fictional backend and 44 DOM tests pass, with TypeScript/lint/dash/
whitespace checks. No local Chrome. Read-only production preview at 18:29Z:
1,869 job-mail search IDs, 1,860 stored, 9 missing; pending 1,320 to 227 projected,
1,093 passive correspondence and all 226 recognized pending outcomes retained.
SQL/Python/Analytics agree; 952 application identities and four date selections
reconcile. This is not full-body replay, perfect search recall or live parser 8.
No production write, import, exhaustive operator restart, migration or release.
See the root candidate continuation for complete behavior, limits and approval.


Final candidate `2554569` adds a receipt/thread timestamp compatibility guard
using the shared marking grace; older receipts cannot select newer applications.
138 focused parser/persistence/triage cases pass, hosted backend passes 1,586,
and web checks/build pass. Focused browser validation is 30 passes on identical
UI source. Last broader browser run: 165 pass / 21 fail; 19 failures overlap the
old list, two additional unchanged-code shortcut-focus assertions fail, and the
old scrolling failure passes. No fresh baseline reproduction proves those two
differences pre-existing. Python extension browser runner: 1 pass / 46 skipped.
The final e2e rerun is still running; overall CI is not claimed green. Draft
PR #8 is ready for a specific API/web release decision, with production parser 7
untouched and the stopped exhaustive operator absent (saved exit status 143).


## 2026-10-27 12:27 Pacific: approved job-mail scope release live

Owner-approved `3cd87a5` runs on API/web at ace.opik.net, parser 8; PR #8 is
merged. Live read-only SQL/Python/Inbox/Analytics agree on 227 pending, with
1,093 legacy correspondence messages searchable and 952 identities reconciled.
Every row in 10 protected tables, all 259 protected Inbox decisions and existing
audit events match pre/post hashes. Schema 0050, environment and scheduler/
PostgreSQL/Caddy remain unchanged. Fresh 471,244,094-byte private backup passes
gzip/catalog checks; rollback tags and all verification artifacts are under
`private-backups/inbox-job-mail-20261027T1918Z/` on the VM. No restore/migration,
scheduler operation, body replay or exhaustive-operator restart ran.

HTTPS health/auth, the new Inbox bundle and 85 logo hashes pass. Final hosted
backend 1,586, matcher 258, extension browser 47, focused Inbox/Analytics browser
30 and web checks/build pass. Broader browser 167 pass / 19 fail; every failure
name is in the earlier 20-failure baseline. Overall CI stays non-green. The
operator is absent with saved exit 143. Refresh Inbox for the new UI and normal
scoped checking; deployment alone does not prove all candidate bodies have been
reclassified or that the search has perfect semantic recall. Root live record
contains exact SHA, image IDs, timestamps, preservation counts and limits.
