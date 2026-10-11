# Sources, adapters, polling and persistence

> Part of the ace knowledge set (index: `README.md`). Dated entries, each a problem found, its cause, the fix and the lesson. An entry describes the system on its date: where it disagrees with the code, trust the code and fix the entry. Superseded entries carry a Status line.
>
> Read this when: you touch an adapter, the scheduler, conditional HTTP, retries, identity and diffing, or see a source misbehave.

## Detail fetches are predicated, not exhaustive

Workday and SmartRecruiters return a cheap list and require a separate
request per posting for the description. Fetching all of them made one
SmartRecruiters source take 949 seconds for 1,631 postings.

Details are now fetched only for titles the gate would keep, using the
*real* gate rather than a copy that could drift. That source now takes
18 seconds -- 91 detail requests instead of 1,631.

Every listed posting is still emitted, including skipped ones, because
the snapshot is authoritative for lifecycle: omitting them would mark
live jobs closed. Skipped postings carry an empty description, which is
safe because the predicate only skips what the gate already rejects on
title, and self-healing because a later rule change makes the next poll
fetch the detail.

## Conditional HTTP everywhere it works

115 of 128 sources replay the HTTP validator from their previous poll,
so an unchanged board answers 304 with no body and the entire download
and diff are skipped. Measured before wiring: 75 MB per full cycle,
roughly 21 GB a day at a five-minute cadence, almost all of it
unchanged.

Workday is excluded because it lists via POST, and Amazon because its
search response is generated per request.

A 304 means the list is byte-identical, so nothing was added, edited or
closed. Only the success markers move.

**Safety valve.** A provider returning a stale validator could keep
answering 304 forever and ACE would go quietly out of date -- the
failure this system is least able to notice, because silence produces
no error. Every source is therefore fetched unconditionally at least
once every six hours, bounding how long a bad validator can hide
changes.

## A discovery run is not a scheduler cycle

Measured live, 38 of roughly 65 cycles polled a single source, so
cycle-level grouping would produce dozens of runs holding one job each.

A session is instead a *discovery run*: opened when a cycle finds new
jobs, extended while further discoveries arrive within 20 minutes. That
reproduces what a person means by "this morning's pull" without
inventing a schedule the scheduler does not have. Cycles that find
nothing create no run.

Jobs are attached by *claiming* those first seen inside the run's
window, rather than threading a session id down through the scheduler,
poll service, workflow, snapshot service and repository -- five layers
of domain code that do not care about presentation. Safe because the
scheduler is the only writer of new jobs and cycles do not overlap.

`last_poll_at` is read from source state, not from runs: a poll that
found nothing is still a poll, and answering "when did you last look"
with the last time something turned up would imply ACE had stopped.

## Transient provider failures are retried, never partially returned

Amazon returned a 504 on page ten of a twenty-page walk, discarding nine
pages of work and failing the whole poll.

Returning the partial result is **not** an option: a snapshot is
authoritative for lifecycle, so anything absent from it is treated as
closed. Nine pages of twenty would mark hundreds of live jobs closed --
far worse than failing the poll.

Paginating adapters therefore retry transient failures (429, 500, 502,
503, 504 and connection errors) a bounded number of times with jittered
backoff, honouring Retry-After up to a cap. A 404 is never retried: it
is a real answer about a board that no longer exists, and retrying would
hide a catalog problem behind a slow poll.

## One fetch path per provider

There were two ways to fetch Greenhouse: the dispatcher, and an older
runner used only by a diagnostic script. When adapters changed to return
three values, the unused path still did `tuple(jobs)` and produced a
three-element tuple whose first element was a list instead of a job --
silently wrong, no exception, no log line. Its tests missed it because
they used fake fetchers.

The duplicate path is deleted. `test_adapter_contract.py` now checks the
*real* adapter functions, so adapter shape and dispatcher expectation
cannot drift apart again.

## The scheduler polls concurrently

Sources are independent -- different hosts, different rows, one
transaction each -- so they are polled six at a time. Sequential polling
let one slow employer block every source behind it. Concurrency is
bounded well below the database pool, and is a limit on politeness
rather than a throughput target.

## Source lanes


| Lane | Mechanism | Description available |
| --- | --- | --- |
| A | Greenhouse, Ashby, Lever, SmartRecruiters, Workday, Amazon | Full |
| B | Curated new-grad feed (TikTok, Apple, Tesla, Oracle) | None - browse-only |
| C | RippleMatch | Full - but the apply link is RippleMatch's own (invariant 6's one exception) |

An aggregator lane was tried and removed: see the 2026-09-10 entry. The test any future one has to pass is whether it returns the employer's own link, because a posting ACE cannot link to is a posting the user has to find again by hand.

## Derived vs authoritative data

`job_evaluations` and `job_resume_scores` are **derived** - rebuildable
from `jobs` plus the rules. They store `content_hash` and `rule_version`
so staleness is detectable. This is what makes rule changes safe:

```bash
python -m backend.scripts.backfill_job_evaluations --apply
```

**Run this after every gate change.** Bump `ELIGIBILITY_RULE_VERSION`
first so staleness is detected.

---

## Amazon polls once a day, not every 15 minutes (2026-09-07)

Amazon's search-index source is a single account rather than a whole
ATS, and it does not need the same cadence as the 113 sources on a
5-minute interval. `job_sources.poll_interval_seconds` for the amazon
row was set to 86400 directly; the scheduler reads intervals from the
database each cycle, so this took effect without a restart. No code
default existed to change; nothing seeds this row on startup.

## One title, many cities (2026-09-07)

Palantir has four active openings whose titles are character-identical
and differ only by location. A sheet row naming that title is genuinely
ambiguous, so the import asked which one, and the row was skipped
because no choice was made. The user reported it as a status bug; it
was the ambiguity path working, but unhelpfully.

Two things were wrong.

**The choice was unmakeable.** `Candidate` carried no location, so all
four options rendered as the same string. Asking a question whose
answers are indistinguishable is worse than not asking. Candidates now
carry location and the dropdown leads with it.

**The sheet could not help.** A `Location` column is now read (city,
office, based in) and used to break exactly this kind of tie via
`location_matches`, which is deliberately loose: a tracker writes
"Chicago" where an ATS writes "Chicago, IL, United States", and the
only job is telling four otherwise identical postings apart. A location
matching none of them leaves the question open rather than forcing a
wrong answer.

**The file format is never the problem.** The user offered to upload a
PDF instead. Import reads CSV and Excel because it needs columns; a PDF
of the same table would parse worse, not better. When a row does not
match it is about the content, not the container.

## Eightfold has two API generations, and ACE only knew one (2026-09-09)

The user found an Amdocs new-grad posting ACE had missed. Amdocs runs
Eightfold, which ACE already reads, so the existing adapter's own
docstring called another tenant "a configuration line rather than a
new module". That held for Netflix and did not hold here: Amdocs's
classic `/api/apply/v2/jobs` route answers with a 403 whose body is
`{"message": "Not authorized for PCSX"}`. The tenant runs Eightfold's
newer PCS-X product line, a different route with a different response
shape.

Three wrong guesses at the URL before the real one was found by
driving a headless browser against the live search widget and reading
what it actually requested. Typing into the widget's React combobox
and dispatching Enter (a `<button type=submit>` guess found nothing,
because Eightfold's own submit is bound to a div, not a button) surfaced
`GET /api/pcsx/search`, and the "PCSX" in the earlier 403 turned out to
be the route's own name.

Registered as a new source type, `EIGHTFOLD_PCSX`, rather than a branch
inside the existing adapter: the shapes genuinely differ. Every PCSX
response wraps its payload in `{status, error, data, metadata}`, uses
`standardizedLocations` instead of a raw joined string, and exposes
`postedTs` instead of an update stamp. `_clean_html` is reused from the
classic adapter; everything else is new.

Verified against production, not a fixture: `Software Engineer -
Graduate` at Amdocs is now `PASS`, `Plano, TX, US`,
`SOFTWARE_ENGINEERING`, reachable through `/api/jobs`. The other 16
Amdocs postings (Fiber Engineer, Payroll Specialist, Marketing
Specialist) correctly rejected.

Worth remembering for the next Eightfold tenant that 403s: guessing the
URL from the classic shape is not reliable, and the fastest path is
watching the real page's network traffic rather than a fourth guess.

## Double-encoded descriptions were hiding requirements from every phrase rule (2026-09-09)

Asked to filter out security-clearance postings, a live check of one
that should have matched found the phrase wasn't there as text: the
stored description held the literal six-character string `&nbsp;`
between "security" and "clearance", not a space. Greenhouse's own
source content is already HTML-encoded once, so the adapter's single
`html.unescape()` call only resolved the outer layer of
`&amp;nbsp;` and left `&nbsp;` sitting in storage looking clean. This
was found duplicated across five adapters (Greenhouse, Lever, Amazon,
SmartRecruiters, Workday), each with its own single-pass call, and it
does not just affect clearance: every phrase rule in the eligibility
gate -- citizenship, experience figures, anything matching
`\s+` between words -- silently fails the same way. A scan of the
database found 15,008 stored jobs affected, 14,485 of them still
active, 138 of those currently marked PASS.

Fixed with one shared `unescape_fully()` (`html_text.py`) that loops
`html.unescape()` to a fixed point, used by all five adapters. Since
raw HTML isn't retained after cleaning, the already-stored rows needed
a separate repair: `backfill_decode_descriptions.py` re-decodes stored
descriptions in place and recomputes `content_hash` so the correction
is picked up as a content change, matching the same discipline as
every other backfill script in `backend/scripts/` -- read-only until
`--apply`. Also widened `CLEARANCE_BLOCKER_PATTERNS` for bare "TS
clearance" (previously only "TS/SCI" was caught).

One thing this fix surfaced by accident: the scheduler container was
still running the old single-pass code while the backfill ran against
the database directly, so it kept re-writing freshly polled Greenhouse
postings with the old bug for as long as the stale container stayed
up. Docker bakes source at build time (see Operational gotchas below);
a code fix to an adapter is not live until the image is rebuilt and
the container recreated, and a long-running backfill against the
database is not a substitute for that. The decode backfill was run a
second time after rebuilding and restarting `scheduler`/`web`, to
catch what the stale container re-corrupted in the interim.

Chasing the last active job still holding a literal entity after that
second pass found two more independent copies of the same bug class,
neither in the original five adapters: Eightfold's `_clean_html` had
its own hand-rolled table of six entities rather than calling
`html.unescape` at all, so anything outside that list (an em dash, a
curly quote) survived as literal text; Ashby's adapter never decoded
its `descriptionPlain` field at all, on the assumption "plain" meant
no entities either, which one real WHOOP posting's `&#39;` disproved.
Both now route through `unescape_fully()` too. The lesson generalizes:
this bug class is "whatever independently reimplements the same idea,"
not "these five files" -- it's worth grep'ing for `html.unescape` and
hand-rolled entity tables again the next time an adapter is added.

## One missing role, two independent causes (2026-09-17)

The user found a Plaid "Software Engineering, New Grad" posting on
RippleMatch, could not find it on Plaid's own careers site, and asked
why ACE did not have it. Two separate faults, either of which alone
would have hidden it. Both had to be fixed; fixing one and declaring
victory would have looked like a fix and changed nothing.

**One: the source did not exist.** Plaid's Ashby board carried 110 live
postings at the time and not one mentioned new grad, graduate,
university or campus. The role was never published there. RippleMatch
is a university-recruiting platform where employers post early-career
roles *instead of* their own ATS, so every such role is invisible to an
adapter that only reads company boards -- and they are exactly the
roles this user wants. See invariant 6 for why the apply link is the
narrow exception it is.

`sitemap.xml` lists every public job page, which makes it the
authoritative snapshot for lifecycle, and each page carries a complete
`JobPosting` in JSON-LD, so the gate runs on real requirement text
rather than a title alone. The sitemap is served `no-cache` with no
ETag, so conditional HTTP is impossible: this is an unconditional
adapter and polls **daily**, which is also the `changefreq` the sitemap
declares. Live: 423 listed, 418 parsed.

**Two: the classifier could not read the title.** The patterns matched
"software engineer" and "software development engineer" but not the
`-ing` form, so a role written as a *field* rather than as a *person*
came out `UNKNOWN`. The gerund is common in precisely the
campus-recruiting titles that matter most here.

Measured before applying rather than after: 224 corpus titles newly
match, 184 of them senior or managerial and still rejected (now with an
accurate reason instead of "unrecognised"), **40 genuinely new
candidates**. Rule version `2026-09-17-v30`; 57,857 evaluations
re-run, without which the fix would only have reached jobs discovered
afterwards.

## Microsoft's October roles arrived days late, for four reasons (2026-10-04)

The user saw Microsoft software engineering roles posted October 1 only
on October 4, in the portal, with no email. Each cause was independent:

1. **The only route was a feed.** Microsoft was reached through Simplify
   alone, and Simplify's own commit history shows the roles were not in
   `listings.json` until after 03:01 on October 4.
2. **The probe could not see Eightfold.** Microsoft's board is Eightfold
   PCSX (`apply.careers.microsoft.com`), and the diagnosis never looked
   for one, so Microsoft read as unreachable. `find_eightfold_board`
   now tries the PCSX and classic endpoints on the likely hosts, each
   gated by the host's robots.txt (RFC 9309 longest-match -- Python's
   `robotparser` is first-match and wrongly blocks Eightfold's
   template). Ten Eightfold boards were found; Microsoft is polled
   directly, hourly.
3. **The laptop is dark about eight and a half hours a night.**
   Nothing posted overnight is seen until it wakes. Only 24/7 hosting
   fixes that.
4. **No email.** `RESEND_API_KEY` is unset, so alerts are composed and
   logged, never sent.

## One long location failed a whole board (2026-10-04)

`jobs.location` was `varchar(500)`. Arcadis lists dozens of sites; once
country names were spelled out, some rows passed 500 and every Arcadis
poll failed with `StringDataRightTruncation`. Applied Materials and
Eaton had never stored a job. Migration 0032 makes it `TEXT` --
truncating could drop the only US site and turn a US role into a silent
rejection. The suite runs on SQLite, which ignores lengths, so a
structural test pins the column unbounded. Same class as the Target
Workday path that broke `external_id` at 255.

## Three restarts in twenty minutes got ACE refused by Eightfold (2026-10-04)

Every source was due the moment the scheduler started, so each deploy
swept all ~550 boards. Three deploys in twenty minutes swept every
Eightfold board in full three times, and Eightfold's edge then answered
`405 Not Allowed` on every tenant but Microsoft -- Netflix's classic
board included. The same GETs had returned 200 three minutes earlier.
The block lifted within the hour. Nothing was done to get round it: a
refusal is treated as one.

- **Restarts resume.** The scheduler starts each source from
  `source_states.last_success_at`; one polled three minutes before a
  restart waits out its interval. The next deploy logged
  `scheduler_schedule_resumed due_now=7 waiting=546`. `--once` still
  polls everything, because that is what someone running it wants.
- **Refusals back off.** 401/403/405/429 doubles the wait each time, to
  six hours at most, reset by the first success; logged as
  `source_poll_refused` without a traceback.
- **One Eightfold board at a time.** PCSX returns ten postings a page
  whatever `num` asks for, so Qualcomm is ~200 search requests a poll,
  Starbucks ~300. The seven boards at fifteen minutes came to about
  4,500 requests an hour from one address. Boards behind a shared edge
  (`SHARED_EDGE`) are now polled one at a time; new Eightfold boards
  register hourly (`registration_interval`); and the existing ones were
  set by yield -- Qualcomm 30 min, Microsoft/Eaton/Applied
  Materials/Ralliant/John Deere/Netflix/Amdocs hourly, Starbucks and
  Arcadis (0 passing roles in 4,351 postings) every 6 h.

The better fix, not built: ask PCSX for newest first and stop at known
postings. It needs persistence to accept a partial snapshot without
closing every posting it did not see, and a periodic full sweep to
catch closures.

## Waiting for the slowest source made every source wait (2026-10-04)

The loop started every due source and waited for all of them before
starting any more. Accenture (Workday, 2,000 postings, none passing)
takes ~345 s every fifteen minutes, so for those six minutes nothing
else was polled, and five-minute sources ran at ten-minute gaps.

A cycle now waits at most 20 s. A source still running carries on in a
persistent pool, reschedules itself in a `finally` (a source stuck as
"running" would never poll again), and is not started twice. Its
discoveries are grouped into a pull from the earliest start of any poll
finished since the last grouping, so a late finisher's jobs still reach
an alert. Measured on the first Accenture poll after the change (342 s,
18:26:28 to 18:32:10): 402 other polls completed while it ran, and the
114 five-minute sources were polled every 306 s at the median and 318 s
at worst -- against 10.7 minutes measured for Cursor before.

## Recent source fix (2026-10-09)

- **Feed-link boards rejected for a 429 were switched off for good** until
  2026-10-09 (92 boards, Workable and Workday). Transient errors now
  record nothing and the provider is skipped for the rest of the run;
  the 92 rows were deleted so the sweep re-reads them.
