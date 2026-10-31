# Operations, incidents and testing lessons

> Current layout, 2026-10-30: canonical/default branch is main; ace-next is standalone. Local legacy services/comparison are retired with verified recovery retained. Use the current handoff and consolidation record; older dated operating instructions below are historical.


> Part of the ace knowledge set (index: `README.md`). Dated entries, each a problem found, its cause, the fix and the lesson. An entry describes the system on its date: where it disagrees with the code, trust the code and fix the entry. Superseded entries carry a Status line.
>
> Read this when: you deploy, restart, debug the scheduler, or write browser tests.


## Inbox-to-Analytics API/web release LIVE (2026-10-30 Pacific)

Owner-approved exact tested `a48d71b` activated only API/web at
2026-10-31T04:31:22Z–04:31:35Z (21:31 Pacific October 30). PR #20 is merged on
canonical main. Production checkout deliberately uses the tested ancestor;
documentation follow-ups do not authorize another rebuild. Parser 15/schema
0050 and scheduler `fca4673` remain. All 371 backend/four script hashes, public
frontend SHA, 15 bundles/fonts, 85 logos and ten auth-boundary probes pass.
Installed primary/independent/expanded Analytics audits pass all four ranges and
exact email drilldowns without Gmail calls, bodies or writes. Nineteen protected
table row sets match exactly across preparation/cutover/post-startup; unrelated
service identities, mounted/private configuration hashes/modes/inodes match.

Fresh backup under `private-backups/analytics-inbox-sync-20261031T0421Z/` passes
gzip, catalog and full expansion, with no restore drill or retention pruning.
Retained actual prior API/web tags and guarded rollback replace images only;
never restore a database over later owner work. Two operational observations
matter for future releases: a `pg_restore --list` reader can stop after the TOC,
giving upstream gzip SIGPIPE under pipefail; use private regular-file input and
still verify complete gzip integrity and full expansion. Also API health can
precede the Gmail monitor's documented 15-second startup delay. Preserve that
early zero-lease observation, then verify one lease and actual sync advancement
after startup. This release did so without another service restart/manual sync.
Original diagnostics and successful final proofs are private and retained.

Exact-source hosted review passes 2,499 backend/PostgreSQL and 53 Inbox/Analytics
browser cases, with web checks/build. Full CI keeps the disclosed 25/22 extension
baseline; no new/resolved failed names. No local Chrome or signed-in production
browser ran. Historical rechecks remain false and parser 7 stays stopped. No
migration, scheduler operation, extension publication or historical replay ran.
See [contracts, live verification and rollback](../analytics/inbox-sync-review.md).

## Inbox parser 14 corrective release LIVE — 2026-10-29 Pacific

Owner-approved API/frontend source **`4116aa01dd5cdd3a6ea3d707017a7d9f7fad5bd7`**
is live at https://ace.opik.net, parser **14**, schema **0050**. API/web activation
ran 00:38:13–00:38:30 UTC on October 30 (17:38 Pacific October 29). All **367**
tracked backend hashes and prepared image IDs match the running implementation;
public health, deployed frontend SHA, served assets and auth boundaries pass.
Only API/web were replaced. The concurrent gate-v55/startup code is retained;
the eight-worker scheduler at `4796e4c`, PostgreSQL and Caddy kept their identities.
Resume Studio, Pulls, authentication and extension 1.31.3 are preserved.

Inbox and email Analytics share a July 1, 2026 midnight America/Los_Angeles floor
(`2026-07-01T07:00:00Z`) across counts, categories, search and pagination. Older
mail remains stored and accessible by audit/Undo links. Application cohorts stay
independently selectable. Exact owner receipt choices now project as
acknowledgements while preserving earlier raw machine classifications for audit;
this projection rewrites neither owner-filed receipt. The reader accepts complete
bodies up to 256,000 characters and distinguishes personal interviews from generic
future selection processes and invitation-only event headings.

Separately approved historical work corrected exactly three unprotected message
meanings: two acknowledgements and one personal video-interview reminder. Only
four classification/filing fields changed, with three appended email audits;
application statuses, links, snippets, Gmail metadata, owner choices, Undo and
prior ledger entries remain intact. Stale-preview guards first stopped without
writes while owner application activity advanced. A tested atomic wrapper then
preserved the exact approved body/row/event/patch fingerprints, refreshed only
application context and verified all three changes in one REPEATABLE READ
transaction. Subsequent owner application/answer-memory activity is preserved
and reported separately from the transaction proof. No guard was bypassed.

Validation: 2,241 backend and 267 matcher tests; dedicated 983 focused backend,
89 Inbox DOM, 33 overlapping render/calculation and 48 hosted browser cases;
TypeScript, lint and build pass. Private operator/verifier/atomic checks pass.
A read-only 121-candidate real-mail audit plus nine subsequent arrivals verifies
the reviewed controls, including six future-process negatives. Fresh committed
row/audit checks, all four Analytics ranges, a single Gmail monitor lease and
sync advancement pass. Population precision/recall remains unmeasured; this is
not a claim of perfect or exhaustive classification. No signed-in production
browser was used. Full CI retains the same 22 unrelated extension-browser failed
names (25 pass), with zero new names; later broad app browsers were skipped.
The owner approved that known limitation. Dedicated Inbox browsers pass.

Fresh backup completed 00:01:47 UTC:
`/opt/ace/private-backups/inbox-july-corrections-20261030T0000Z/database.dump.gz`,
533,672,847 bytes; gzip, catalog and full archive expansion pass, without a restore
drill. Retained API/web tags `oracle-api:before-inbox-july14-20261030T0000Z` and
`oracle-web:before-inbox-july14-20261030T0000Z` preserve the immediately preceding
startup API and Inbox frontend. The folder's guarded `rollback.sh` recreates only
API/web. Data compensation is separate and must protect later owner activity.
Private applied HMAC journal: `semantic-atomic-final/atomic-apply-plan.json` under
that folder; source/row/audit proof and rollback notes remain private. Global
historical rechecks stay false and the stopped parser-7 operator stays stopped.
Do not broaden the three-message approval or infer a full-mailbox replay.

## Historical accuracy dispute — parser 13, superseded by parser 14 above

Inbox parser 13 remains deployed (frontend `e64c547`; the newer startup-network
API release preserves that Inbox implementation). The owner disputed the semantic
accuracy of acknowledgements, offers and an interview after reviewing the live UI. The release is not accepted as accurate.
Source, health, preservation and arithmetic projection checks do not establish
semantic accuracy; agreement between a saved label and the same parser's fresh
reading is not independent validation.

The confirmed active email scope is July 1, 2026 onward, using the owner's
America/Los_Angeles calendar. Older Gmail evidence must remain preserved for
audit/Undo, while the active Inbox and email progress metrics use that scope.
Correction and representative regression work are in progress. No new historical
rewrite or deployment is implied by this checkpoint. Resume Studio is outside
scope. The stopped parser-7 runner and global historical rechecks remain off.

## Parser 12 API/frontend release and completed bounded history (2026-10-28)

Owner-authorized `873ee080` is live, parser 12/schema 0050, activated at
2026-10-29T04:21:54Z–04:22:11Z (October 28 21:22 Pacific). Only API/web were
replaced. All 355 backend files match running source; protected cutover row sets
and pre-existing events match exactly. Source/header, HTTPS/auth, served assets,
logos, real-mail routes, filters, monitor lease and subsequent sync checks pass.
Scheduler, PostgreSQL, Caddy, authentication, Studio and extension 1.31.3 remain
preserved. No migration or signed-in production browser session is claimed.

The fresh 495,228,138-byte backup is
`/opt/ace/private-backups/inbox-system-20261028T2355Z/database-pre-activation.dump.gz`.
Gzip, catalog and full expansion checks pass; no restore ran. Retained prior API
`02629e6` and web `97e4158` support API/web-only rollback without overwriting SQL
data. Use current guarded evidence rollback before retiring its supporting code
if that operation is separately authorized. Historical filing, exact-target
outcomes and targeted corrections completed with private preservation proofs;
no second operator or unrestricted replay is authorized. Historical rechecks
stay disabled and the stopped parser-7 runner remains stopped.

Dedicated CI passes 811 backend and 40 hosted browsers plus render/DOM,
TypeScript/lint/build; full backend passes 2,045 and matcher 267. Full CI remains
red: its older extension browser stub lacks `chrome.runtime.id`, which canonical
extension 1.31.2+ now requires before drawing a card. Actual source-function
reproduction proves the early exit without an API call; preserved extension,
browser tests and CI bytes match canonical. Do not claim the failing browser
suite passed or substitute earlier broader results. No local Chrome was started.


## Continuous Inbox API/frontend release and preserved concurrent work (2026-10-28)

Status: historical release checkpoint; superseded by the parser-12 LIVE record above.

Source `5109fcd` is live, parser 11/schema 0050. Merge the newer learned-answer
API before preparing images; do not deploy the older Inbox branch over it.
Concurrent extension-only 1.31.2 work remains preserved. Only API/web activation
ran. Fresh backup under `inbox-system-20261028T2320Z` passes gzip, archive catalog
and full expansion; retained rollback API is 7ce4007 (learned answers), web 6b2e712.
The earlier 19:42 backup captured an older API and is not this release's rollback.
Never automatically restore SQL data during image rollback.

All 350 running backend hashes, public exact web SHA/four assets/85 logos, auth,
real-mail viewer and four-range Analytics probes pass. PostgreSQL read-only
lease exclusion/reacquisition and actual background ingestion are verified.
Cutover preserves all eleven non-connection table row sets and existing events;
new ingestion later appends email/outcome events and one intended status change,
with old mail and protected decisions intact. Keep those intervals separate.
The first new-mail probe incorrectly compared raw `unknown` intent with stored
`unclear` correspondence. Preserve that diagnostic; compare reconciliation's
documented projection instead. The corrected complete probe passes. Do not
alter production data to make a validation assumption pass.

Dedicated checks pass 687 backend and 38 hosted browsers; full backend 1,921 and
matcher 267 pass, with web checks/build. Full extension browsers 46/1 reproduce
the canonical employer-field assertion; broader app browsers are skipped at this
source, and overall CI stays red. No local Chrome or signed-in production browser
claim. The new historical plan remains unapplied pending condition-4 approval;
global historical checks stay false and parser-7 remains stopped. Root knowledge
and the ignored private release package contain the complete evidence and limits.

## Inbox parser-10 API-only release and scoped cleanup (2026-10-28)

Owner-approved `6ee2eb2` is live; frontend remains 95f4a97 and all four other
service identities remain unchanged. Fresh backup passes full gzip, catalog and
full expansion, with API-only code rollback. The guarded cleanup defaults to
read-only preview, seals source/cohort/grant/plan, rechecks labels/body/current
matching, compares locked rows and appends email audit events. It never mutates
application statuses. Private before/after plans support row rollback with later
owner work protected. Apply uses no more than 50 known records per invocation.
Keep the global historical gate false and the exhaustive parser-7 runner stopped.

A critical reference comparison stopped release; the owner explicitly approved
the concrete tested source/scope while preserving conflicting historical links.
Full cutover hashes and independent post-cleanup field/event checks pass. A broad
private snapshot heuristic treated all reasons beginning `You ` as owner choices,
including the classifier's `You applied to several roles...` explanation. Retain
the original failed comparison; prove every difference belongs to the approved
machine-review cohort, preserve all outside hashes and check actual owner actors/
reasons. Do not silently force that heuristic to pass or change data to match it.

Full CI passes backend 1,735, matcher 258, extension browser 47 and web checks;
dedicated review passes focused backend 481, DOM/calculation 77 and browser 36.
Broader browsers 166/20 have no new failure names versus canonical history but
one extra versus the last deployed run; root causes are not proven identical,
and overall CI is not green. Exact source/API, public/auth/assets, real-mail and
Analytics probes are separate from a signed-in production browser test.

## Inbox API/frontend release with history disabled (2026-10-28)

Owner-approved `95f4a97` is LIVE, parser 9/schema 0050, PR #11 merged. Build and
activate only API/frontend with `--no-build --no-deps --wait`; do not run migrate,
scheduler, PostgreSQL or Caddy. Fresh backup checks include full gzip, archive
catalog and full expansion to `/dev/null`, without a restore. Retain actual old
API/web images before building; rollback those services only and retain newer
owner data. The complete root LIVE record controls exact operation/evidence.

A parser version bump is also a potential data operation: the page-open sync
loop can call historical recheck automatically. This release therefore adds
`GMAIL_HISTORICAL_RECHECKS_ENABLED`, default false, enforced by both stale
selection/counts and the server recheck handler. Verify the real loaded setting,
not just the image default. Never enable it incidentally during deployment.

The strict whole-row-set comparison initially rejected a concurrent owner
application addition even though every pre-existing row/event hash matched.
Retain that original failure report; independently verify provenance and links
before treating growth as legitimate. Do not erase owner additions to force
snapshot equality. The extended verification also observes ordinary extension
usage/upserts; report that active-owner interval separately from exact cutover
preservation. Unexplained changes still require stopping for owner approval.
Read-only route probes and source/HTTP asset checks do not certify a real
signed-in browser interaction or independent semantic accuracy.

## Analytics web-only activation and continuity (2026-10-27)

Owner-approved web `70d95a9` is live, PR #10 merged. The first root knowledge
section is the complete release record. Build the exact reviewed SHA, verify
fresh private backup integrity/catalog and a retained web rollback tag, then
activate web with `--no-build --no-deps --wait`. Earlier broad instructions to
rebuild every image apply to coordinated backend/schema releases, not this
deliberately web-only operation. API/scheduler/PostgreSQL/Caddy and schema must
remain unchanged for this scope. Do not run migrate or restore data implicitly.

Use fresh read-only row-hash snapshots immediately before/after activation and
keep a separate preparation snapshot so concurrent owner activity is not
misattributed to deployment. All protected rows/events matched in this release.
Verify the exact public frontend SHA/header, API health, auth boundaries and
served JS/CSS/logo hashes. Production HTTP/source verification is separate from
hosted fictional browser QA; no signed-in production browser claim here.

Avoid standard-library names for private Python helpers: `operator.py` shadowed
Python's `operator` import; rename it `operator_state.py` before verification.
Analytics `undated` metadata is family-wide, so subtract it only for all-time
dated timeline reconciliation. Finite selections already exclude those records.
The corrected independent harness passes all 12 calendar aggregations; no runtime
patch was necessary. Keep private output outside Git and synchronize the full
root knowledge plus supporting docs to the restored checkout without replacing
its older application code or touching the concurrent Inbox worktree.

## Operational gotchas

- **`docker compose build` before `up`.** Containers bake the source at
  build time. Skipping this has caused "Can't locate revision" migration
  failures three separate times.
- Maintenance scripts are read-only until `--apply`.
- Postgres runs on host port **5433**, web app on **8000**.
- Containers run on UTC. Anything rendering a **date** for a person to
  read must go through `settings.display_timezone`, not the container
  clock, or it reports the wrong day every evening.
- **`docker compose build migrate` too.** The migrate service has its
  own image off the same Dockerfile, so rebuilding only web and
  scheduler leaves migrations that exist on disk unapplied and the
  alembic head one revision behind, silently.
- **The extension does not reload itself.** It is unpacked, so a change
  to `extension/` reaches the browser only after the refresh icon on
  its card in `chrome://extensions`, and only on pages opened after
  that.
- A **machine shutdown needs no recovery**. Compose restarts everything
  at boot and the scheduler's next cycle closes the gap by itself; see
  the 2026-09-10 entry.
- **A restart no longer re-polls everything.** Each source resumes from
  its last successful poll. Still, do not restart in a loop: sources
  that are overdue or failing go at once, every time.
- **`docker compose exec web` can land in a one-off `docker compose
  run` container**, with whatever image it started from. Address the
  server as `docker exec ace-web-1`. Two "the rebuild did not take"
  scares on 2026-10-06 were this.
- **A 405, 403 or 429 from a provider is a refusal.** The scheduler
  backs off by itself; nothing should be done to get round it.
- **A registered source is picked up within a cycle**, no restart
  needed: the scheduler re-reads `job_sources` between cycles and logs
  `scheduler_sources_reloaded` when the list changes. This was not
  always true, and the old behaviour looked exactly like a bug.
- **Generic plans and expression indexes.** psycopg prepares a statement
  after five runs on a connection and Postgres may then plan it once for
  any parameters. An expression index (`ix_jobs_posting_link_key`) only
  matches if its constants are in the SQL text, not sent as parameters
  -- `literal(..., literal_execute=True)`. On 2026-10-07 the parameterised
  version made `/api/sessions` run for hours and the page sat loading
  ("ace is not live"). Test a suspect query with `PREPARE` + `SET
  plan_cache_mode = force_generic_plan` + `EXPLAIN EXECUTE`; a plan with
  literals tells you nothing about what the app runs.
- **Re-evaluating after a gate bump**: the full backfill is ~25 jobs/s
  (hours for ~600K). A rule that only adds rejections can only change
  rows currently PASS -- re-evaluate those first (minutes), the rest can
  catch up.
- **Browser client tests run against the live app on :8000.** Restarting
  web mid-run produces "the app rendered nothing" failures; re-run them.

## The scheduler stopped for an hour (2026-09-06)

Registering the Netflix `eightfold` catalog row while the scheduler
container still ran an image predating that `SourceType` crashed it on
every restart. `restart: unless-stopped` dutifully restarted it into the
same crash, so `docker compose ps` said "restarting" rather than
"broken", and discovery stopped for an hour.

Three fixes, because three separate things had to go wrong:

1. **The catalog now skips rows it cannot parse**, with a warning,
   instead of refusing to load. One unpollable source is not a reason
   to stop polling the other 131.
2. **The scheduler has a healthcheck** that asks whether any source has
   been polled successfully lately, rather than whether the process
   exists. A polling loop can be up and doing nothing, and a crash loop
   reads as "restarting"; neither is visible from process state alone.
   `backend/scripts/scheduler_health.py`, 45 minute window.
3. **The interface stops saying "ACE Live" when it is not.** It now
   reads "Not updating · Last pull 1h ago" in amber, and the popover
   says what to run. The only clue before was a timestamp quietly
   ageing next to the word "Live".

**Standing rule, learned again:** `docker compose build` alone does not
restart anything. After a build, `docker compose up -d --force-recreate
<service>`, or the container keeps running the old image. Building only
`web` while `scheduler` and `migrate` stay stale has now caused three
separate incidents.

---

## The client has browser tests now (2026-09-07)

`backend/tests/browser/`, driving real Chrome over the DevTools
protocol against a running ACE. They skip rather than fail when Chrome
or the server is absent, so a plain checkout stays green.

Written because every interface bug so far was found by a person
looking at the page, never by the 524 unit tests: a primary action
pushed below the fold, a list stuck on skeletons, a sort that silently
did nothing, and a deletion that removed unrelated functions and left
the app blank. The client is one HTML file with no seam to unit test.

Each test covers a defect that actually shipped. `open()` fails fast on
a blank app and reports what `render()` threw, because the first version
let every test wait out its own timeout and turned an eight-second run
into an eight-minute one that buried the single useful fact.

Run everything with `pytest`, or just these with `pytest -m browser`.
Point them elsewhere with `ACE_BROWSER_TEST_URL`.

## Never guess which rows are test data (2026-09-07)

While cleaning up after a test I deleted `job_marks` "updated in the
last 20 minutes" as a proxy for my own writes. The user had re-imported
their spreadsheet minutes earlier, so that caught 52 of their real
applications along with my 3. Recovered by re-running their sheet
through import, but only because the sheet still existed.

Delete by an identity that is actually specific, or read the rows first
and delete them by id.

## A test that writes must wait for the write (2026-09-07)

The browser tests for the new Applied button marked a real job, then
cleared it. The clearing test raced: its assertion was
`!!el.innerText.indexOf('Applied')>=0`, which JavaScript reads as
`(!!(...)) >= 0`, true for every possible value. So it never waited
for the browser's PUT to land, fired its own clearing PUT immediately,
and the two arrived out of order. Four real jobs were left marked
applied across two suite runs.

Three rules came out of it, and the suite now proves each:

**Assert on the server, not the DOM, for anything that persists.**
Waiting on rendered text confirms the click was handled, not that the
write completed.

**Put the comparison inside the promise.** `fetch(...).then(...)`
compared to a string is a valid expression that is simply always
false, and `awaitPromise` cannot save it because the result is already
a boolean.

**Check the test catches its own regression.** Removing
`state.pinned=id` left the first version of the held-row test passing,
because `mark()` re-renders without re-fetching and the row stays put
until the next load. The test now reloads the list, and fails when the
pin is removed. Verified both ways.

The leaked rows were cleared by explicit id after being read back
first, per the rule above.

## Waiting on a stale flag is not waiting (2026-09-07)

The browser test for the above passed against the reintroduced bug.
`page.wait_for("!state.loading && ...")` returned immediately, because
`state.loading` is still false from the previous load until `loadJobs`
actually starts, so the assertions read the numbers from before the
tap. Waiting on a value that has to *change* (`state.total!==before`)
is the reliable form, and it is what the older filter tests already
did.

Two mutation runs were needed to catch it: the first reported the test
passing with the bug in place, which is the only reason it was found.
Always confirm a new test fails against the bug it describes.

## No pulls for an hour, and nothing was broken (2026-09-10)

The user asked why there had been no checks since 9:30. The activity
log had a 73-minute hole in it and the container said "healthy", which
is exactly the pair of facts that makes a person suspect the worst.

The laptop had been asleep. The scheduler was inside a 121-second
`time.sleep` when the machine suspended; that call does not advance
while suspended, so on waking it finished the remainder and carried on.
The log shows it plainly once you look at the timestamps rather than
the messages: `scheduler_sleeping seconds=121.520` at 16:17:49, and the
next line at 17:31:34.

The diagnostic is worth remembering, because it needs no privileged
log and `journalctl` returned nothing here:

```python
time.clock_gettime(time.CLOCK_BOOTTIME) - time.clock_gettime(time.CLOCK_MONOTONIC)
```

MONOTONIC stops while suspended and BOOTTIME does not, so the
difference is the time spent asleep -- 71.7 minutes, matching the gap.

Two honest notes. First, the healthcheck could not have caught this and
should not be expected to: it was suspended too, so on waking it saw a
fresh poll and reported healthy, which was true. Second, ACE lost
nothing. It persists every posting it has seen and diffs against stored
state, so a missed poll is only a later poll -- the same property that
made the overnight shutdown a non-event earlier the same day.

What was actually wrong was that ACE could not say any of this. An
unexplained hole reads as a failure, and the user had to ask. The
scheduler now measures across its own sleep and logs
`scheduler_resumed_after_suspend` with the gap when the two clocks
disagree by more than two minutes, so the next hole has a reason
attached to it. Surfacing that on the Activity page, where the user
actually looks, is not done yet.

## A machine shut down overnight, and nothing needed fixing (2026-09-10)

The user turned the computer off at midnight and asked, on turning it
back on, whether anything had been missed. Worth recording the answer
because it is the first real test of the restart path.

Nothing was missed and nothing needed doing. Compose brings postgres,
scheduler and web back on their own at boot -- they are all
`restart: unless-stopped` -- and the scheduler's first cycle after a
7h41m gap (00:04 to 07:45 local) polled all 243 sources, found 413
postings and 12 that pass the gate. No manual catch-up, no lost
window, because ACE persists every posting it has ever seen and a
missed poll is just a later poll: the diff is computed against stored
state, not against what happened while it was watching.

The one thing worth doing on a restart is the thing the gotchas
already say: `docker compose build` before `up`, so the containers are
not running yesterday's source. That is not paranoia here -- a stale
scheduler container spent most of a session re-corrupting freshly
polled descriptions after the code that caused it had already been
fixed on disk.

## Rebuilding one image is not rebuilding the images (2026-09-14)

The gotcha in 08-operations-and-testing.md has now bitten in reverse. Migrations 0029 and 0030
were downgraded correctly, the auth code was reverted, and then
`docker compose build web` plus `up -d --force-recreate web` ran the
**stale `migrate` image**, which still contained the deleted migration
files and re-applied them. The database came back to 0030 with the auth
tables restored while no code referenced them.

Recovering needed the deleted migrations restored from git long enough
to downgrade through them properly, since alembic cannot downgrade past
a revision whose file no longer exists.

**Rebuild `web`, `scheduler` and `migrate` together, always.** The
existing note says a stale migrate image leaves new migrations
unapplied; it also re-applies removed ones.

## An ignore rule hid working code (2026-10-15)

`.gitignore` held `*resume*` to keep real resumes out of the public repo. It also matched
`web/src/app/app/resume-studio/`, `UploadResume.tsx`, migration `0039_add_resume_studio.py` and
`docs/knowledge/09-resume-studio.md`. Every test passed in the session that wrote them, because the files existed there;
every other checkout got a 404 on Resume Studio, a Settings page that could not compile, and a database that never got
the 0039 tables. The rule now re-includes code and notes (`!*resume*/`, `!*resume*.py`, `.ts`, `.tsx`).

Lesson: before pushing, check `git status --ignored` for source files, and prove a change from a clean checkout of the
pushed commit (`git worktree add --detach /tmp/x HEAD`, then typecheck and the unit tests there).

## Compose now separates the API and Next.js services (2026-10-15)

The old `web` service was FastAPI because it also served the single-file interface. After that interface retired,
the Python service became `api` on `127.0.0.1:8000` and `web` became the production Next.js server on
`127.0.0.1:3000`, with `API_ORIGIN=http://api:8000`. Both have health checks and the Next service waits for the API.

Build and start every image after a code or migration update:

```text
docker compose build migrate scheduler api web
docker compose up -d migrate scheduler api web
curl http://127.0.0.1:3000/healthz
curl http://127.0.0.1:8000/healthz
```

Backend maintenance now uses `docker compose exec api ...`. `PUBLIC_BASE_URL` and `WEB_BASE_URL` should both name
the browser-facing Next.js origin so alerts, reset links and the FastAPI root redirect land on the canonical app.


## TestClient wakeup sockets in the sandbox (2026-10-26)

A new image endpoint test stalled on its first anonymous TestClient GET, before
any asset work. Faulthandler showed the portal event loop and calling thread
waiting, with no application worker active. The same in-memory/mocked-network
test passed immediately outside the restricted sandbox; the auth/source/logo
regressions passed there too. Use an approved execution outside this sandbox
for Starlette TestClient's local wakeup sockets when this specific stall recurs.
This does not authorize connecting to real data or running Chrome; the laptop
cooling restriction still applies.

## Legacy scheduler exit 137 (2026-10-19, archived lesson)

Legacy main commit `99987b6` recorded a scheduler ending with exit 137 while the web service continued. Neither Docker nor the kernel recorded an OOM kill, and the evidence suggested an external stop rather than proving a crash cause. Process/web health alone did not prove discovery freshness; inspect successful source reads. The historical direct-container recovery avoided an incompatible migration dependency. The local legacy stack is now retired: this is not an instruction to start it again.
