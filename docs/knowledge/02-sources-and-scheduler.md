# Sources, adapters, polling and persistence

> Part of the ace knowledge set (index: `README.md`). Dated entries, each a problem found, its cause, the fix and the lesson. An entry describes the system on its date: where it disagrees with the code, trust the code and fix the entry. Superseded entries carry a Status line.
>
> Read this when: you touch an adapter, the scheduler, conditional HTTP, retries, identity and diffing, or see a source misbehave.

## Chat 8 readers and feeds (2026-11-20 to 2026-11-28 Pacific)

- **Workable's job file** (`adapters/workable_feed.py`, source `workable_feed/jobs`, hourly): one compressed XML file of
  every posting on Workable's job board. Read conditionally (304 when unchanged); US postings that are full-time or
  state no type and whose title the gate could pass become list copies linked by Workable's own posting link; a
  posting ACE holds open from a Workable board or another list is dropped by shortcode. Workable's server ends a
  response about a minute after it starts, so the compressed body is saved to a temporary file as fast as it arrives
  and read from disk; judging postings while streaming made most reads break off. Only a whole file closes anything,
  and only its own copies. A burst of full downloads earns a 429: never download it repeatedly to measure.
- **SuccessFactors** (`adapters/successfactors.py`, board = host): a careers site's `/sitemap.xml` is an RSS feed of
  every posting with its whole description, one request a board. Detected from `/job/<city>-<title>/<id>/` links on
  any host (tried last); every add route reads the feed as text; the feed's employer is the postings' claim.
- **BambooHR and Rippling** (`adapters/bamboohr.py`, `adapters/rippling.py`, `adapters/listed_details.py`): a list,
  then each promising posting's description, kept in the shared reading store (the Workable pattern).
- **iCIMS** (source `icims`, board = host): read by the careers-site reader (`adapters/sitemap_jobs.py`) under its own
  name; its sitemap lists every posting and the posting's `?in_iframe=1` view carries the JobPosting (the plain page's
  JSON-LD is something else). Titles from addresses are now percent-decoded.
- **Paylocity** (`adapters/paylocity.py`, board = the board id): the board page's `window.pageData` lists postings with
  a teaser; each posting page carries the whole JobPosting.
- **Not read:** Paycom (its job list answers 401 without the page's token; its sitemap is 404) and ADP (FreeHire reads
  it only through a proxy and a browser fingerprint; no plain public route was found). Both are refusals by the rules.
- **Test systems:** an Oracle or Workday host labelled dev, test, uat, stage, sandbox and the like is refused before it
  is read on every route (`coverage/identity.py` `staging_host_reason`), after a lead added two test copies of a live
  board and they reached Pulls (2026-11-24, repaired the same hour).
- Labels for every new type are on Sources and Leads; FreeHire's weekly list names boards on SuccessFactors, BambooHR,
  Rippling, iCIMS and Paylocity as leads.

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

## Six workers were all busy, all the time (2026-10-29)

Measured read-only after the startup-network release: 3,262 enabled sources asked for about 10,900 polls an hour and
the scheduler completed about 5,400. Its six workers were busy 100% of a 15-minute window with the CPU mostly idle
(load below 1.8 on two cores): Workday paging 54% of worker time, Workable 16.5%, Oracle 10.5%, and 950 Ashby,
Greenhouse and Lever polls about 14% at under half a second each. Boards meant for fifteen minutes were read every
twenty to twenty-five.

Workable's 429 had become a standing refusal of the VM's address. `request_with_retry` retried it twice, honouring
`Retry-After` up to 20 seconds, so each refused listing held a worker for 40 seconds before the runtime's own refusal
backoff applied. It now takes `retry_statuses`; Workable's listing leaves 429 out (`LISTING_RETRY_STATUSES`), so the
backoff starts at once. `DEFAULT_CONCURRENCY` is 8 (pool 12 plus 8 overflow). The refusal backoff is in memory, so a
restart repeats every Workable refusal once; that is now a fast failure rather than 40 seconds a board.

After: about 136 polls a minute instead of 88; fifteen-minute boards a median 8 to 11.5 minutes old, 90th percentile
17 to 19, instead of 15 to 19 and 23 to 25. Workday is now two thirds of worker time; that is the next limit.

## One line for every board, and two writes nobody needed (2026-11-09, Chat 4)

Capacity was measured before any growth (OPS-05). Eight workers were busy 99.6% of the time. Workday held 69% of
worker time at about 11 seconds a read, Oracle 13% at 17, against half a second for Greenhouse and a quarter for
Ashby. Every due board was handed to the pool at once, so the pool's first-come queue held several hundred boards
and every read, quick or slow, started about four minutes after it was due.

- **Fair turns** (`scheduling/runtime.py`). A board starts only when a worker is free, the one due longest goes first,
  and a platform at its limit waits while other boards go ahead (`PLATFORM_LIMITS`: Workday 5, Oracle 2; a shared
  edge stays one at a time). A finished worker takes the next due board at once instead of waiting for the next
  cycle. A single run (`--once`) still polls every due board once. Each cycle logs `waiting=`, the line of due boards.
  `SCHEDULER_WORKERS` (1 to 16, default 8) and `SCHEDULER_PLATFORM_LIMITS` are settings, so a measured step up needs
  no rebuild. An offline replay of the measured durations predicted quick boards' wait falling from minutes to about
  a minute and a half at eight workers, and to near zero at ten.
- **Workday dates moved on every read** (`adapters/workday.py`). The list says "Posted 3 Days Ago"; the adapter made
  that "now minus three days", and `posted_at` is in the content hash, so 97% of Workday postings counted as edited on
  every poll: about 725,000 needless gate evaluations and row rewrites an hour, and Workday jobs claiming a posted
  time of day Workday never gave. The label now names a day (midnight UTC, like the detail `startDate`), and
  `steady_posted_on` keeps the stored day while the label still agrees within a day (Workday's midnight is not UTC's;
  "30+ Days Ago" names no day). The dispatcher reads the stored days in its own short session first.
- **Every read rewrote every posting's last-seen time** (`persistence/repository.py`), about 1.2 million row writes
  an hour, 88% on boards read every fifteen minutes or faster, for a time shown only on a job's own page. An unchanged
  open posting is now not written at all except to refresh `last_seen_at` once it is an hour old
  (`LAST_SEEN_REFRESH`, the auth sessions' pattern) or to keep a changed provider update time. A 304 never touched
  job rows anyway. Changed, reopened and new postings are written in full as before.

Lessons: count writes, not only requests. The database had the indexes polling needs; its time went on rewriting
rows that had not changed. A field derived from "now" must never sit in a content hash. And a queue in front of a
thread pool hides waiting: in-flight looked like eight, the log's `still_running` was really the queue.

The Sources tab's "Can ace keep up?" box (`coverage/capacity.py`, `/api/coverage/capacity`) shows reads in the last
four complete quarter hours against the reads the boards ask for, boards read within one and a half planned
intervals, and how fast new jobs arrive (median and nine in ten, last day, boards already read, posted times with a
real time of day; midnight UTC is a date).

Measured steps up the same day: ten workers (Workday 6, Oracle 2) by setting, and every one-request board at fifteen
minutes whatever its origin (579 startup boards promoted), together since 19:52Z. Against eight workers in the afternoon
(quick boards waited a median 92 s, Workday 377 s, 178 reads a minute), one hour later quick boards waited 22 s, Workday
85 s, 222 reads a minute, workers 93% busy, scheduler CPU 51% on average, new jobs typical 7.2 minutes. A first
ten-worker try rolled back on a false alarm: the scheduler's own moved-board repair switched a board off, and the strict
settings check did not know it; measured numbers had not been saved before the check.

## Workday turned ACE away, so ACE now reads it gently (2026-11-17, Chat 5)

The new "Is reading on schedule?" table showed most Workday boards a day late. The scheduler's log showed why: from
2026-11-14 Workday answered more and more requests with 429, and from about 07:00Z on 2026-11-16 most of them. Every
board backed off on its own (doubling to six hours) while the other 970 kept asking, which probably kept the limit in
place. ACE had been sending tens of thousands of Workday requests an hour: about three quarters were list pages (a
2,000-posting board is a hundred pages, read in full every fifteen minutes) and the rest were posting details fetched
again on every read although nothing had changed.

- **One shared pause** (`scheduling/runtime.py`, `LANE_PAUSES`). Three refusals within five minutes, with no Workday answer
  in those five minutes, pause every Workday board (on Nov 17 Workday answered about half, and pausing on any refusal read
  almost nothing): ten minutes, doubling to two hours while Workday keeps refusing, starting over after an answer. Paused boards stay
  due and go first, oldest due first, when the pause ends; a single run (`--once`) leaves them to the next run instead of
  waiting. A refused Workday board's own backoff stops at an hour (`LANE_BOARD_BACKOFF_CAP_SECONDS`), so no board sits for
  six hours after Workday answers again.
- **No instant repeat.** A refused list page fails the read at once (`adapters/workday.LISTING_RETRY_STATUSES`, as Workable
  already did); a refused detail stops further detail reads in that read.
- **Fewer at once.** Three Workday boards at a time (was six; `PLATFORM_LIMITS`, `SCHEDULER_PLATFORM_LIMITS`), two requests
  at a time per board (`DEFAULT_CONCURRENCY`).
- **Big boards hourly.** A board that listed 200 or more postings waits at least an hour (`BIG_BOARD_CADENCE`); small boards
  keep their plan. Nothing is written to `job_sources`, so cadence promotions and the polling-settings checks are unaffected.
- **Stored details reused.** The dispatcher hands the adapter what each active posting's detail gave before
  (`_stored_workday_details`, `StoredDetail`); it is reused, and each posting's detail is fetched afresh in one hour of every
  24 (`detail_refresh_due`, by its identifier). A detail read that fails keeps the stored text: before, a refused detail
  stored the posting with an empty description.

Release lesson: two activations were rolled back by wrong checks in their own measurement ("Workday still being read" when
Workday's refusal is its choice; a daily-score log line in an hour when the score runs once a day). A check must match its
stated rule; test a measurement's checks against the expected states before it can roll back production.

**Second step the same day: one steady pace** (`adapters/workday.WorkdayPace`, wired by the dispatcher as `WORKDAY_PACE`).
Pausing on any three refusals read nothing while Workday refused most requests; pausing only when nothing answered let
1,384 refused polls through in an hour. In one quarter hour Workday answered 15 of 18 requests sent gently, so every
Workday list and detail request now waits its turn on one pace: six a minute to start, halved on a refusal down to one,
raised a quarter after twenty answers up to 120. Boards read every fifteen minutes (those with matching roles) go first;
a slower board overdue six hours goes first anyway (`PRIORITY_LANES`, `NO_STARVING_SECONDS`). Between daily full reads a
board reads only its newest three pages and is never sliced (`quick`, `QUICK_READ_PAGES`, `WORKDAY_FULL_READ_EVERY`); a
partial read closes nothing. That evening Workday still refused nearly everything even at one request a minute: ACE waits.

Lessons: a refusal that covers a whole platform needs a platform answer, not 975 separate ones. Count requests per platform
before adding boards (OPS-05), and read only what changed.

## Workday's outage, and the refusal that followed it (2026-11-17, Chat 6)

The owner heard Workday had been down since Monday. Workday's real outage was Friday November 13 to Saturday November 14:
a disaster-recovery test reached production databases, and service was restored by the Saturday morning. ACE's own log
tells the rest. During the outage Workday answered ACE less but refused nothing. When it came back, every Workday board
was overdue at once and ACE caught up at about twice its usual Workday load; Workday began refusing part of it, and from
2026-11-16 07:00Z most of it. A day later others were still reading Workday (a public new grad list showed Workday roles
minutes old) and ACE's own few answers carried postings from that day, so Workday was up and limiting ACE's address.
ACE keeps its steady pace and never reads another way.

- **Room to get back to speed.** The one Workday pace (`WorkdayPace`) climbs a quarter after twenty answers in a row and
  halves on a refusal. Its top is now a setting, `SCHEDULER_WORKDAY_PACE_MAX` (default 150 a minute; the scheduler applies
  it at start and logs it in `ace_scheduler_ready`), because every Workday board on its plan needs about 140 requests a
  minute with newest-pages reading and reused details, a fifth of what ACE sent before; the old top of 120 kept ACE a
  little short of its plan. Nothing changes while Workday refuses: the pace stays at its floor.

Lessons: an outage is followed by a catch-up burst, and a burst is what a platform's limit sees. Read what a platform's
users can see (its status, other readers, the dates on what it still answers) before calling a refusal an outage. A
platform's top speed belongs in a setting, measured against what its boards need.

## Workday's job API refuses automated readers, so ACE reads its sitemaps (2026-11-18, Chat 7)

Two days after the catch-up burst, ACE's pace sat at its floor of one request a minute and Workday still refused most of
it. The refusal was not about ACE alone: other public job readers logged the same 429 on Workday's job API
(`/wday/cxs/{tenant}/{site}/jobs`) from November 16, for Bank of America, Morgan Stanley and others. Workday had
tightened its job API for automated readers. It is not a block of ACE's address: robots files, sitemaps and posting
pages kept answering from the same VM, and the job API itself answered some requests on some data centres (wd1 and wd10
about half, wd3 and wd5 almost none).

Workday's robots.txt (served through Cloudflare) names a sitemap for every career site and allows crawlers on the site:

    Sitemap: https://{host}/{Site}/siteMap.xml
    User-agent: *
    Allow: /{Site}/

A sitemap lists a board's newest hundred postings by link (a smaller board in full), and each link is
`https://{host}/{Site}` plus the path ACE already stores the posting under, so the two ways of reading give the same
postings. A posting's page carries a schema.org `JobPosting` with title, description, place, date and requisition.

- **Quick reads go by the sitemap** (`adapters/workday.read_by_sitemap`): one request finds what is new; only a new
  posting whose title could pass costs a page; a posting ACE holds is handed back exactly as held (title included, from
  `_stored_workday_details`), so its content hash does not change. A sitemap read never closes anything.
- **Full reads ask the job API**, which alone lists a board whole. A refusal rests it (`ApiRest`: 30 minutes, doubling to
  six hours, ended by an answer; boards refused together start one rest) and the read goes by the sitemap.
- **Two paces**: `PACE` for the job API, `PAGE_PACE` for sitemaps and pages; one's refusals never slow the other. Both
  climb to `SCHEDULER_WORKDAY_PACE_MAX`.
- **One pause for every reader** (`scheduling/holds.py`): before, the feed-link sweep and the lead check kept reading
  Workday boards through the scheduler's pause, and the employer-page check read Workday pages with no pace. The
  scheduler now sets `HOLDS["workday"]` when it pauses; the fetcher raises `PlatformHeld` (transient, so a sweep puts the
  board off), and the employer-page check skips Workday pages while held and paces them otherwise.
- **List copies of unread boards stay**: a Simplify (or Zapply) copy is dropped only when ACE has read its board within
  six hours (`READ_DIRECTLY_WITHIN`); before, any registered board counted, so no copy of a refused Workday board's
  postings reached ACE.

Not done, by rule: no other address, proxy, browser fingerprint or sign-in. Paid scrapers read Workday from their own
addresses, which is the same thing at one remove. A link to a Workday posting cannot be spelled from a list's data (the
title slug must match exactly), so list rows for Workday are not turned into made-up links.

**What the release showed (23:34Z to 23:38Z).** Workday refused ACE's scheduler on the sitemaps too: of its first seven
sitemap reads two answered, four got 429 and one 403, and the page pace fell to its floor within a minute. Yet a single
plain request for AES's sitemap from the same VM, with the same user agent, answered 200 at 23:38:00, ninety seconds
after the scheduler's read of that same file got 429; the manual checks earlier in the day answered nine of nine.
Workday's edge (Cloudflare) treats ACE's own HTTP client as an automated reader and refuses most of what it sends,
whatever the path or the pace. Making ACE's reader imitate another client to pass that filter is the "fingerprint" the
rules forbid, so it is not done: the refusal is Workday's answer to ACE's reader. ACE keeps its pace, pause and rest,
reads by sitemap whenever Workday answers (one request instead of several), and the six-hour rule lets Simplify's copies
of refused Workday boards through. The employer-page check holds Workday pages back while Workday refuses (its page pace
at its floor) and reads at most ten paced pages a poll, because at one request a minute a feed poll with a hundred
Workday pages due would have held the whole feed for hours (51fdabc).

Lessons: when a platform refuses, look at what its robots.txt invites crawlers to read before waiting it out; a refusal of
one endpoint is not always a refusal of the site, and a one-off manual check is not the scheduler's client, so measure the
real reader before relying on a route. Every reader in the process must see a platform's pause, not only the scheduler's
own turns, and no reader may queue long on a refusing platform's pace.

## Workday's bot check, Zapply's lists and employers' own sites (2026-11-19, Chat 7)

**What blocked Workday.** From 2026-11-16 Cloudflare, in front of every Workday career site, answered automated readers
with a bot check: HTTP 429 with `cf-mitigated: challenge` and a "Security Check: Enable JavaScript and cookies" page, on
sitemaps, posting pages and the job API alike. Many public job readers reported it the same days (one aggregator went
from 106k-170k Workday jobs a day to about 5.5k). Readers traced it chiefly to Python's short default cipher list, which
gives httpx a rare TLS fingerprint; the address counts as a second factor. From ACE's own server a plain request with
OpenSSL's standard list was answered while ACE's reader was not.

**What ACE does, with the owner's approval (2026-11-19).** The Workday reader (`adapters/workday.workday_client`) offers
OpenSSL's standard cipher list (`ctx.set_ciphers("DEFAULT")` on httpx's own context; certificates still checked), keeps
the honest User-Agent `ACE/0.1 (personal career-intelligence project)`, its pace and robots, and uses no proxy, other
address or browser disguise. A bot check is still an answer: at the first one every Workday read in the scheduler stops
for 24 hours (`BOT_CHECK_HOLD_SECONDS`, the shared Workday hold) and nothing is retried; a plain 429 keeps the existing
backoff. The employer-page check never opens Workday pages itself. A scheduler restart clears the day's hold (in memory).
Not done, by rule: relays (Zapply sends Workday requests through a Cloudflare Worker, in its own words to "bypass" the
block), proxies, other addresses, browser impersonation.

**Zapply's lists (DIS-12).** ACE reads Zapply's public new grad software and data science lists from GitHub's raw host.
A row whose employer posting ACE can spell (Greenhouse, Ashby, Lever, SmartRecruiters, Workable) is a copy with the
employer's link while ACE does not read that board within six hours; a row ACE cannot spell (Workday, Phenom, Oracle,
Eightfold and others) is a copy linked by Zapply's own link until ACE holds that posting open from the employer. ACE
never opens a Zapply link itself; those copies say their requirements are unverified. A copy's detail credits its list
with a followed link (Zapply's terms). Measured: Zapply's lists held only 6 of 301 Workday roles ACE had read directly
and that pass the gate; they are a small safety net, not a replacement for reading Workday.

**Employers' own careers sites (second doors).** Many Workday employers also publish every posting on their own site.
The career-site reader (`adapters/sitemap_jobs`) reads Radancy sites and, since 2026-11-19, Phenom sites (a board named
`<host>/<country>/<language>`, sitemap index read whole or not at all). A site counts as the employer's only when three or
more specific titles ACE stored from that employer's Workday board appear in its job addresses. Boards are added only in
an owner-approved batch.

**Rule gap closed.** The feed-link sweep and the dark-board check never newly add a board on a host with a stored robots
refusal (SmartRecruiters' postings service); the dark-board check had added five SmartRecruiters boards on 2026-11-17.
