# ACE Next knowledge

Last updated: 2026-10-30 Pacific, source inventory and startup coverage gaps recorded. Before that, 2026-10-29 Pacific (2026-10-30 UTC), gate v56 (no infrastructure, platform, cloud, DevOps, site reliability or mobile roles) and round-two city startup boards LIVE on API and scheduler at fca4673; Inbox parser 14, July email scope and eight-worker scheduler preserved

This is the single, standalone continuity document for ACE Next and its
independent legacy comparison system. A new chat should be able to understand
the product, architecture, safety boundaries, verified state, extension,
operations, migration history, deployment controls and remaining work by
reading this file alone. `docs/HANDOFF.md` and `docs/knowledge/` retain supporting
incident histories; also read the handoff and relevant topic as required by
repository instructions. Dated observations below are evidence from that date,
not a claim that a service is healthy now.
It intentionally contains no email address, resume text, answers, credentials
or database dump content because the GitHub repository is public.



## Source inventory and startup coverage gaps, 2026-10-30

Read-only production snapshot, about 07:00 Pacific. ACE reads **3,656 enabled sources** (3,793 catalog rows; 137
switched off: agencies, duplicates, dead boards), about 3,450 companies, holding **3,433 open passing roles**. By
reader: Ashby 1,208, Greenhouse 870, Workday 865, Lever 255, SmartRecruiters 155, Workable 118, Oracle 115, Gem 34,
Eightfold 16, 17 own-site readers (Apple, Google, Amazon, IBM, Meta, Intuit, Arm, Synopsys, ByteDance, TikTok,
Atlassian, Shopify, AMD, Booking, SIG, EA, Two Sigma) and 3 feeds (Simplify new grad and internships, RippleMatch).

Planned check interval, sources, measured minutes since last read (median / 90th percentile): 5 min, 111 (4 / 8);
15 min, 2,345 (10 / 17); 30 min, 4 (27 / 35); hourly, 1,185 (21 / 51); 6 hours, 1; daily, 10 (RippleMatch and nine
Workday employers, about 14 hours). Workable is planned at 15 minutes but read about every 17 hours: Workable refuses
the VM with 429. The 1,097 `talent_network` boards hold 667 passing roles on 405 boards; 414 are checked every 15
minutes, 683 hourly until their first passing role.

Gaps. State them whenever coverage is discussed: the owner found them only by asking, after receiving a source list
in which the new startup boards were not marked.

1. About 1,390 network boards were left out because they had no US software or ML role on 2026-10-29, and nothing
   re-checks them. Next step agreed in principle: a weekly automatic re-check (`register_network_boards` skips
   registered boards, so a re-run adds those that have started hiring).
2. About 1,400 companies with no readable board found: about 770 YC companies that post only on Work at a Startup
   (sign-in) and about 625 Built In companies.
3. About 300 startups on boards ACE has no reader for: Rippling 72, Notion pages 63, Paylocity 39, Dover 33 (robots
   disallows its API), BambooHR 27, Breezy 27, JazzHR 21, Teamtailor 17.
4. Refused or disallowed: about 23 Consider boards (CSRF token), about 19 robots-disallowed firm boards, Climatebase
   (challenge), TrueUp (403), Wellfound, LinkedIn, Handshake and Work at a Startup (sign-in). Never bypass these.
5. Cities never searched for their own startup networks: Detroit and Ann Arbor, Phoenix, Nashville, Columbus,
   Indianapolis, Charlotte, Tampa, St. Louis, Kansas City, Baltimore, Madison, Orange County, New Jersey.
6. About 40 Workable boards unread (429), and every Workable board stale as above.

Defect found: Pear VC's shared Ashby board (`pear-vc`, about a dozen portfolio startups) was registered in round two.
Built In listed it under the firm's own name, so the shared-board check in `settle_name` (a non-firm network name
against a firm declared name) did not fire. Its 16 passing roles are real startup roles shown with company "Pear VC"
and the startup in the title. Owner decision pending: keep, or disable (`enabled = false`, a production write that
needs approval). Fix the check either way, with a fictional regression.

Owner direction for the next session: deep research into startup databases like Harmonic.ai and similar public
lists of startups that are hiring; add every accessible source whose boards pass the filters, as many as possible,
within robots.txt, terms of service and no-sign-in rules. A paid API only with a key the owner adds to `.env`.
Private lists (complete CSV, startup boards by network, the read-only regeneration query) are in the ignored
`artifacts/ace-sources-20261030/` folder on the owner's laptop.

Release caution (2026-10-30): another session put API `b03d251` (Inbox parser 15, gate v56 preserved) live; canonical `wine-rose-platform` does not contain it until PR #19 is merged. Before any API release from source work, rebase onto that source or confirm the merge, or the release rolls parser 15 back. Check the running image first.

## Gate v56 and city startup networks LIVE, 2026-10-29 18:18 Pacific

The owner approved ("Approve, go live", Workday and Oracle boards included). Canonical
fast-forwarded to **`fca4673033dc92833bbf217182738026f414bf3d`**, rebased onto the
concurrent Inbox parser 14 release (`ecc72c6`) without touching it. Only **api** and
**scheduler** were built and recreated; web stays the Inbox release's `4116aa0`;
PostgreSQL and Caddy untouched. Both containers report gate `2026-10-29-v56`. The
PASS-only backfill re-evaluated 5,133 stored passing decisions: passing roles are now
3,849 software, 879 ML and 214 forward deployed, none infrastructure, site reliability
or mobile. Scheduler healthy. Fresh private backup
`/opt/ace/private-backups/startup-networks-round2-20261030T0116Z/database.dump.gz`
(534,810,553 bytes, mode 600, gzip and catalog checks); rollback tags
`oracle-api:before-startup-networks-round2-20261030T0116Z` and the matching
`oracle-scheduler`. Applied marks moved 1,007 to 1,010 during the release: the owner
applying, not the release, which writes no application data.

- Gate v56: infrastructure, platform, cloud and DevOps titles off the list, as the
  owner asked ("not on this cloud DevOps"); software, backend, frontend, full stack,
  developer, founding, member of technical staff, ML (including ML infrastructure and
  AI platform) and forward deployed stay; "Software Engineer, Infrastructure" stays.
  Experience unchanged (0 to 3 years; open-ended 3+, 4+, senior rejected): the owner
  asked for 3+ and corrected it to "only up to 3 years" within minutes. See
  `docs/knowledge/01-gate-and-roles.md`.
- Round two of city networks: 15 regional VC boards, YC's hiring companies (public
  yc-oss dataset) and Built In entry-level and junior listings in 22 cities; boards
  found by ACE's verified name and careers-page lookup. The collected list grew from
  2,139 to 2,726 boards; 105 networks explored, 59 read. Details in
  `docs/architecture/2026-10-29-startup-networks.md`.
- Registration on the server: 1,443 already in ACE, 1,283 read with
  `--include-paged`: **336 registered** (228 Ashby, 58 Greenhouse, 23 Lever, 21
  SmartRecruiters, 3 Gem, 3 Oracle), 164 with 299 roles passing at once; left out 767
  with no US software or ML role today, 99 unreadable, 26 agencies, 15 empty; Workable
  answered 429 again. Every Workday board failed in that run: the collected list had
  kept the source host only for Gem, and a Workday source cannot be read without its
  tenant host. `4cfc188` restored all 251 hosts and added a test that reads the
  committed list as the script does; a Workday-only run (`--input` a filtered copy in
  the container) then registered **34** large employers (45 had no US software or ML
  role today). Total from the networks today: **1,097 boards**.
- At 01:50 UTC: 1,094 of the 1,097 boards polled, holding **667 active passing
  roles**; fifteen-minute boards a median 8 to 9 minutes old, 90th percentile 15 to 16;
  about 192 polls a minute; load average 1.4 to 1.7 on 2 cores. Workable stays stale
  (refusal backoff), as before.
- Read-only feature check after the release (`check_features.py` in the private
  release folder, run in the API container as a local caller with read-only
  connections): all 40 page, filter and sort requests answered 200 (Opportunities,
  family, new grad, early career, experience fit, verified, match, big tech, source,
  search, age, company include and exclude, Applications, Saved, Archive, Pulls,
  Analytics, Coverage, Resume Studio, Answers, history); the family filter offers only
  software, ML and forward deployed; no excluded family among passing results.
  Opportunities 1,347 before, 1,275 after.

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

## Inbox parser 15 API live; reviewed correction pending — 2026-10-30 Pacific

API source **`b03d251047f531ba60a75812d9c088b395a6d943`** is live at
https://ace.opik.net, parser **15**, schema **0050**. All **371** tracked backend
file hashes match the tested source and prepared image. Only API was replaced;
web stays the July-scope release `4116aa0`. The running gate-v56 code, registered
city-network sources and eight-worker scheduler are preserved, as are PostgreSQL,
Caddy, authentication, Pulls, Resume Studio and the extension. The protected mail,
application, status, owner-decision and prior-event inventories pass cutover
verification. One authentication last-seen heartbeat was separately identified;
it is not an application or classification change.

The owner-reported invitation was already imported, complete and authenticated,
but parser 14 read it as unclear correspondence. The cause was rigid invitation
phrasing, a blanket conditional guard, and a two-sentence proximity requirement;
personal hiring interest, interview-description paragraphs and an opt-in request
to select a time were not combined. Application linkage and the July floor were
not responsible. The archived 121-message audit did contain this message and read
it as unknown; it lacked an explicit owner-labelled positive assertion. That was
a validation miss. Zero pending and same-parser agreement do not prove recall.

Parser 15 combines current personal hiring contact, bounded interview context and
scheduling, including recipient-interest/availability opt-ins. Direct invitation
subjects require a current body contact or scheduling request. Subject-only,
URL-only, generic calendar, future-selection, preparation, public-event and
unrelated meeting evidence remain insufficient. An independent release check
also exposed an older parser-14 bug: the words "interview invitation" inside a
withdrawal were treated as a positive action. The final source applies current
withdrawal/denial guards across both readers. Actual withdrawals can establish
cancelled-interview evidence; not-yet-invited denials cannot invent interview
history. A genuinely later re-invitation or reschedule remains eligible.

The actual reported invitation is now an explicit required positive in read-only
verification, with separate negative and owner-protected controls. This is a
known-case regression check, not held-out accuracy. Exact-image validation passes
**2,462 backend tests**; dedicated hosted checks pass **1,201 focused backend** and
**48 Inbox browser cases**. The new fictional suite has **218 cases**, with
**561 focused cases** passing; **83 private operator/verifier controls** pass.
At source b03d251, a canonical-doc conflict prevented the new full CI run.
The docs-only follow-up resolves that conflict without changing runtime source.
Exact-image and dedicated hosted checks validate this release; do not carry an
older full-run result forward or claim overall CI is green. Earlier full CI had
22 existing extension-browser failures outside this change.

**The one authorized historical correction completed atomically.** Exactly one
saved email meaning changed, with four permitted classification/filing fields
and one appended email-only audit. Application statuses, links, snippets, owner
choices, original evidence, Undo and all prior ledger rows are preserved. The
corrected email is returned by the production Interviews filter. Its receipt-date
history appears in the applicable Analytics ranges; the later rejected status
remains intact. No confirmed role-stage event or application match was invented.
All four Analytics ranges, independent category projections, one monitor lease,
sync advancement, public health/served assets and auth boundaries pass. No signed-in
production browser was used. Global historical rechecks stay disabled; the stopped
parser-7 operator remains stopped. No bulk historical replay occurred.

API activation ran 14:29:32–14:29:42 UTC on 2026-10-30. Fresh backup completed
14:19:51 UTC: 555,065,199 bytes, gzip/catalog/full archive expansion verified, no
restore drill. Private release folder:
`/opt/ace/private-backups/inbox-personal15-20261030T1416Z/`.
Retained tag `oracle-api:before-inbox-personal15-20261030T1416Z` and its guarded
`rollback.sh --apply` replace API only. Data compensation is a separate sealed,
unchanged-row-only operation; never restore the whole database automatically or
overwrite later owner activity. The original strict snapshot saw one normal auth
last-seen heartbeat. An independent read-only proof checks every static auth field
against the fresh backup and other protected records against cutover fingerprints;
it does not claim reconstruction of opaque pre-cutover auth column values.
Population precision/recall remain unmeasured. Calendar-only/attachment parsing
is outside this patch.

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

## Scheduler capacity release LIVE, 2026-10-29 16:54 Pacific

The owner approved ("Yes, do it now") after the measurement below showed all six
workers busy all the time. Canonical fast-forwarded to
**`4796e4c396cfb267f6b110a9bb1e417066978c69`**; only the **scheduler** was built and
recreated (API stays `fc81876`; web, PostgreSQL and Caddy untouched, container IDs
verified). The running scheduler reports `DEFAULT_CONCURRENCY` 8, Workable listing
retries `[500, 502, 503, 504]` (no 429) and gate v55; healthy. Fresh private backup
`/opt/ace/private-backups/scheduler-capacity-20261029T2352Z/database.dump.gz`,
533,736,103 bytes, mode 600 (gzip and catalog checks); rollback tag
`oracle-scheduler:before-scheduler-capacity-20261029T2352Z`.

- Why: Workable's 429 is a standing refusal of the VM's address; each refused listing
  was retried twice for up to 20 seconds before the runtime's refusal backoff, holding
  a worker 40 seconds (16.5% of all worker time). `request_with_retry` takes
  `retry_statuses`; Workable's listing passes `LISTING_RETRY_STATUSES` (without 429).
  Eight workers stay below the twelve-connection pool. Tests: `test_retry.py`,
  `test_workable_adapter.py`; full backend 2,167 passed.
- Measured 15 minutes after (00:09 UTC, read-only): 1,357 polls in 10 minutes (about
  136 a minute, up from about 88); 1,271 sources read in the last 10 minutes (was
  855). Fifteen-minute boards a median 8 to 11.5 minutes old, 90th percentile 17 to
  19 (were 15 to 19 and 23 to 25). Workers 7.85 of 8 busy, Workday now 67% of worker
  time; Workable no longer holds workers. Scheduler container about 17% of one core,
  PostgreSQL 3%, 3 GB of 12 GB memory in use; load average 2.7 to 3.7 on 2 cores
  while the new boards' first polls write their jobs, falling. Public health 0.15 to
  0.25 s and the sign-in page about 0.2 s. Workable boards stay stale (refusal
  backoff, a median 5 hours): Workable refuses this address, as before.

## Startup talent networks and gate v55 LIVE, 2026-10-29 16:04 Pacific

The owner approved ("Approve, go live", hourly cadence for boards without a passing
role). Canonical `wine-rose-platform` fast-forwarded `e64c547` to
**`fc8187680e5ed0dc18a982af28477bd2eeadade7`** ([PR #17](https://github.com/anwarbuilds/ace/pull/17)
recorded merged). Only **api** and **scheduler** were built and recreated
(`--no-deps`; API with `--wait`, the scheduler started without it because its health
check first runs five minutes in, then confirmed healthy). Activation 23:03:5x UTC.
Web, PostgreSQL and Caddy kept their container IDs; schema stays **0050**; applied
marks (969), external applications (48) and users (1) unchanged. Both containers
report gate `2026-10-29-v55`. The PASS-only backfill re-evaluated all 4,956 stored
passing decisions; passing roles are now 3,758 software, 800 ML, 165 FDE and **zero**
site reliability or mobile. Public `/healthz` ok; web still reports `e64c547`.

- Images: API `sha256:0b32c359087b92e512578bbe179f57db60fd07f7b6363046c712d98c5d863039`,
  scheduler `sha256:c71974526266852fb03e2955ca963d404e4535c13c4f99021bd06c3657e69214`.
  Rollback tags `oracle-api:before-startup-networks-20261029T2302Z` (`afa126d9`, the API
  found running, built from `e64c547` rather than the older 873ee080 record below) and
  `oracle-scheduler:before-startup-networks-20261029T2302Z` (`84c91f31`).
- Fresh private backup: `/opt/ace/private-backups/startup-networks-20261029T2302Z/`,
  mode 700, `database.dump.gz` 507,220,377 bytes, mode 600, gzip and 293-entry catalog
  checks passed (not a restore drill). The folder holds `release.log`, inventories,
  container and image records and `register.log`.
- `register_network_boards --apply` runs in the background on the VM (nohup), about ten
  boards a minute: 2,139 collected, 683 already in ACE, 1,379 to read, 77 Workday or
  Oracle left out. **Result: 727 boards registered** (239 at 15 minutes with a role
  passing now, 488 hourly), finished 23:30 UTC. One more read as hiring but had just
  been registered by the feed path. Left out: 580 with no US software or ML role today,
  18 unreadable (moved boards, 404), 13 empty, 1 agency. Workable answered 429 on its
  first board, so the other 39 Workable boards were not read; run the script again
  later to read them (it skips everything already registered).
- First scheduler minutes: normal polling; two pre-existing empty-board refusals
  ("Refusing to process an empty source snapshot as authoritative", 2K early careers
  and 21Shares), Workable 429s as before, and the feed maintenance registering boards
  as usual (including a Gem board, now detectable).

- Scheduler after the restart (measured read-only): all 727 new boards were polled
  within 40 minutes and held **382 active passing roles** at 23:46 UTC. Existing
  15-minute boards were a median 20 to 23 minutes old 15 minutes after the restart,
  then 15 to 19 (90th percentile 23 to 25) at 23:46 as the queue drained (1,865 to
  1,315). The scheduler completes about 5,400 polls an hour against a nominal 10,900
  for 3,262 enabled sources: its six workers were 100% busy, 54% of worker time on
  Workday, 16.5% on Workable 429 waits, 10.5% on Oracle, and about 14% on 950 Ashby,
  Greenhouse and Lever polls (under half a second each). It was saturated before
  this release; the new boards add little. Load average stayed below 1.8 on 2 cores;
  PostgreSQL 24 of 100 connections; pool 12 plus 8 overflow per process.
- Next, each needing its own approval: (1) re-run `register_network_boards --apply`
  when Workable is not refusing the VM, for the 39 Workable boards; (2) done the same
  day: the scheduler capacity release above; (3) a Rippling reader (72 startups in
  these networks link Rippling boards). Every scheduler restart still resets the
  in-memory refusal backoff, so each restart briefly repeats the Workable refusals.

What the release contains, as prepared before approval:

The owner asked for every startup in networks like a16z's speedrun talent network
(new grad roles across US cities), listed first, then added without breaking
anything; and for site reliability and mobile engineer roles to stop appearing.

- **Networks**: 79 explored, 42 read within robots.txt with zero refusals in 3,910
  requests (speedrun, 35 Getro boards, a16z and Initialized CareerPuck, South Park
  Commons, Greylock, Paradigm, HN "Who is hiring?" August to October). 20 Consider
  boards (Sequoia, Kleiner Perkins, GV, Lightspeed, Bessemer, Felicis, NEA, First
  Round, USV and others) refuse with a CSRF requirement and were not read; 13
  disallow their job pages; Climatebase challenges; YC Work at a Startup needs a
  sign-in. `api.getro.com` disallows crawlers and was never called.
- **Boards**: 2,181 readable employer boards; 682 already in ACE (legacy proxy); **732
  new boards hiring US software, ML or FDE engineers** (241 with 395 roles passing
  v55 now; 2,188 US engineering roles); 580 left out until they hire; 41 agencies;
  Pear VC's shared board; 117 Workday, Workable and Oracle boards left to the server.
- **List for the owner**: `artifacts/startup-networks-20261029/boards-to-add.md`
  (private, ignored). Committed data: `backend/app/discovery/network_boards.json`.
- **Registration**: `backend/scripts/register_network_boards.py`, dry run by default.
  Reads each new board once through the normal adapter; adds it only when it reads,
  is not an agency's or a firm's shared portfolio board (Pear VC's Ashby board lists
  a dozen companies), and has a US software, ML or FDE role today. Registers under
  the board's own declared name when the network used another (Data.ai is Sensor
  Tower now). `discovery_source = talent_network`. A board with a role passing today
  polls every 15 minutes; the rest hourly, promoted on their first passing role
  (`coverage/cadence.py`). Workday and Oracle boards only with `--include-paged`.
  Run it only after the scheduler carries this release, or the old scheduler
  promotes the hourly boards within half an hour.
- **Gem**: the detector now recognizes `jobs.gem.com/<board>` (API host
  `api.gem.com`), so feed and network links to Gem boards are read.
- **Gate v55** (`2026-10-29-v55`, `-v55-sde2`): `SITE_RELIABILITY_ENGINEERING` and
  `MOBILE_ENGINEERING` families, rejected as `NON_TARGET_ROLE` with a reason. Keeps
  robotics, wireless, Mobile AL, T-Mobile, Cisco IOS XR, full stack or backend
  beside mobile, dual software-or-mobile campus titles, ML on Android and bare
  hardware "Reliability Engineer" where they were. Legacy-corpus measurement: 156 of
  3,133 active passing roles change (88 SRE, 68 mobile), every title read.
  `backfill_job_evaluations.py --status PASS --apply` re-evaluates only stored PASS
  rows. Web needs no change (`familyLabel`).
- **Validation**: full hermetic backend 2,162 passed (pyenv 3.12.12 with the venv
  site-packages); dash scan 0; whitespace clean; an end-to-end dry run and apply of
  the registration script against a throwaway SQLite database with real boards.
  No browser or production check was possible: the agent permission classifier
  refused even read-only production queries this session.
- **Release plan** (needs approval): private `artifacts/startup-networks-20261029/release.sh`
  takes the approved SHA, makes and checks a fresh backup, tags rollback images,
  builds and recreates `api` and `scheduler` only (`--no-deps`), verifies gate
  v55 in both, runs the PASS backfill, then starts the registration in the
  background with its log beside the backup. No migration; web, PostgreSQL and
  Caddy untouched. Rollback: previous images; new rows switched off with
  `UPDATE job_sources SET enabled = false WHERE discovery_source = 'talent_network'`.
- **Load**: about 1,455 more polls an hour on roughly 9,400 (legacy catalog proxy).
  The legacy scheduler keeps 15-minute boards at a median of 11 to 14 minutes old,
  90th percentile near 20; watch the same after release.
- **Gaps**: no reader for Rippling (72 startups in these links; server-rendered
  pages, the next reader worth writing), Dover (robots.txt disallows its API),
  BambooHR, Breezy, JazzHR, Teamtailor, Paylocity, Notion pages, Wellfound, Work at
  a Startup. Workable answered 429 from this laptop (the legacy scheduler on the
  same address polls 123 Workable boards); its 40 boards are read on the server.
- The legacy system keeps gate v54 and its catalog, so the independent comparison
  will show these boards and the SRE/mobile difference as ACE Next only.

Details: `docs/architecture/2026-10-29-startup-networks.md`,
`docs/knowledge/03-coverage-and-discovery.md` and `01-gate-and-roles.md`.


## Company-aware Inbox Intelligence LIVE, 2026-10-28 21:22 Pacific

Owner-authorized API/frontend source **`873ee080fa724fcbe0022ad47939d38c083ca8e9`**
is live at **https://ace.opik.net**, parser **12**, schema **0050**. Activation
ran **2026-10-29T04:21:54Z–04:22:11Z**, the evening of October 28 in Pacific
time. Only API/web were replaced. All **355 tracked backend source files**
match the tested running implementation. API image:
`sha256:ff88fa7d10425b2eca76dd664fe029746963666ff79f8a91b2a2a4b27f8f69ec`;
web image:
`sha256:f35ec43f44a4995aaff5af9afb1399d936430094a3b3fae251369e879b2d5ae7`.
PostgreSQL, the discovery scheduler,
Caddy, authentication, Resume Studio, Pulls and the owner's extension **1.31.3**
remain preserved. No migration or extension publication accompanied this release.

A clear rejection with a reliably identified employer can now be recorded as
**company rejection evidence** without asking the owner to choose among roles.
Its audit event uses the email's own ledger key, validated company metadata and
no application status transition. The stored email decision remains `update`
with an exact classifier reason; the shared projection exposes
`company_rejection`. This preserves prior API compatibility and the original
email evidence. The recorded inspector shows the employer, decisive reading and
Undo, with no role picker. The Recorded automatically total includes company
filings, with a separate company rejection filter. Undo appends a correction and
returns the email to review without changing an individual application. Owner
choices and existing application outcomes remain authoritative.

Analytics presents company rejection emails separately from exact rejected
applications. Company evidence counts unique active emails, excludes undone,
refiled, linked, malformed or contradictory claims, and opens the underlying
messages. Its date filter follows **email receipt dates** in the selected time
zone, rather than borrowing submission dates. All-time includes historical
emails that predate the application register. Company filters remain exact;
unknown roles are excluded from selected role-family totals with an explicit
explanation. Company-only evidence never enters individual application statuses,
role stages, response timing or application cohort rates, and does not mark every
application at an employer rejected.

Inbox also provides **Assessments and tests** and **Interviews and screens**
filters. The action-language reader distinguishes invitations and reminders from
completed tests, cancellations, routine coordination and public learning mail.
Its **56 fictional intent regressions** include safeguards for conditional,
negated, quoted and conflicting wording. A recognized employer action can remain
visible without becoming a fabricated application outcome. Positive automation
retains its existing opt-in, live-message, exact-job-identity and employer-origin
requirements.

The existing API-owned Gmail monitor continues bounded checks for ready grants
while the page is closed. Pause, disconnect, changed grants, quota cooldown and
shutdown remain authoritative. `GMAIL_BACKGROUND_SYNC_ENABLED=false` disables
that monitor. Global historical rechecks remain disabled; approved historical
work uses explicit sealed operator plans. Do not restart the stopped parser-7
operator or treat a parser bump as permission for an unrestricted replay.

Cutover verification preserves **all eleven protected row sets and the complete
pre-existing event set exactly**. Public HTTPS health, exact frontend source,
private-route authentication, four served asset hashes and all 85 logo hashes
pass. These production checks are separate from hosted fictional browser tests;
no signed-in production browser session is claimed.

Exact-source [dedicated run 40791122175](https://github.com/anwarbuilds/ace/actions/runs/40791122175)
passes **811 focused backend, 27 calculation/render, 67 Inbox DOM and 40 hosted
Inbox/Analytics browser cases**, plus TypeScript, full lint and production build.
The calculation/render and Inbox commands overlap in their render cases; those
totals are not a count of unique tests. Viewed Day/Night company screenshots
show recorded evidence without a role choice and a visible Undo control. Both
hosted company cases verify that Undo returns only the email to review and makes
no application-review, creation or filing request.

[Full run 40791129522](https://github.com/anwarbuilds/ace/actions/runs/40791129522)
passes **2,045 backend, 267 matcher, 105 extension DOM, 11 logo and 67 Inbox DOM
checks**, TypeScript, lint and build. Its extension browser step has **25 pass /
22 fail**; subsequent app-browser steps are skipped. The preserved canonical
extension now requires `chrome.runtime.id` before refreshing its card, while the
older browser fixture omits that property. Executing the actual source guard and
refresh functions with and without the missing property reproduces the absent
panel before any API call. Extension/browser-test/CI source is byte-identical to
canonical `b633b7c`; no exact canonical workflow run exists for that commit, so
this is a demonstrated fixture mismatch, not a claim that the 22 failures were
rerun on canonical. **Overall CI remains red.** No local Chrome was launched.

Fresh pre-activation backup:
**`/opt/ace/private-backups/inbox-system-20261028T2355Z/database-pre-activation.dump.gz`**,
**495,228,138 bytes**, refreshed immediately before activation. Gzip integrity,
archive catalog and full expansion checks pass; no database restore was
performed. The private rollback plan retains the prior API image **`02629e6`**
and web image **`97e4158`** and replaces only API/web, retaining SQL data. Full
image digests and rollback commands remain in the private release record.
Never restore a database automatically over later owner work. Company evidence
remains readable as stored correspondence after an image rollback; use the
current guarded event/row rollback while its supporting code is available if a
separately authorized evidence rollback is required.

**The separately approved bounded historical processing is complete and its
final preservation checks pass.** Classification and filing changes preserved
application statuses. A separately authorized exact-application outcome plan
changed only its verified targets; existing matching statuses received evidence
without an unnecessary transition. Targeted action-reading corrections were
filed separately. No arbitrary role was selected to reduce the review queue.

Protected owner decisions, Undo, all prior ledger entries, original Gmail
identity/metadata, outside-cohort mail and unrelated application data remain
preserved. Only the specifically authorized application status transitions and
append-only evidence/correction events occurred. Post-processing Inbox/Analytics
projections agree across all four audited ranges, with no orphan active outcome
events. Live Gmail viewer/readings, the supported filters, PostgreSQL monitor
lease exclusion and single-leader and post-activation sync checks pass. Actual cohorts,
results, remaining review reasons, exact seals and journals stay in the private
owner package; no private message totals, internal IDs, employer examples or
owner decisions belong in the public continuity record. The completed scope is
not permission for another historical replay or an expanded cohort.

Population precision, recall and false-positive rates remain unmeasured. The
available independent owner decisions are predominantly rejections and do not
establish representative accuracy across acknowledgements, assessments,
interviews, offers and routine mail. Passing the defined regressions and private
live checks does not establish perfect accuracy or complete mailbox observation.

Private release evidence and rollback instructions: ignored owner-local
`artifacts/inbox-intelligence-system-20261028/RELEASE.md`.


## Continuous Inbox Intelligence LIVE, 2026-10-28 16:29 Pacific

Status: historical release checkpoint; superseded by the parser-12 LIVE record above.

Owner-authorized API/frontend source **`5109fcd919b76a588bed848c4ac4bf07d0e5acbc`**
is live at **https://ace.opik.net**, parser **11**, schema **0050**. Canonical
was fast-forwarded through this release ([PR #13](https://github.com/anwarbuilds/ace/pull/13)).
Activation ran **23:29:21Z–23:29:38Z**. API image
`sha256:02629e6c1b989c22a3404d90f4e8b55ae4f233b2dbb7cae46469570d560dae3a`,
container `005789a98cbaef8e049e2fd44b1630b0e697b248c84cb36747336ea3298ffdb3`;
web image `sha256:97e41584d481e06a412de9c3337ddee841684c90080082fb736e888bf898963d`,
container `4aafbf6f824c86bfb8cf2960dbdb3db218bd3a4453f85ccacbb848dcf8045d3b`.
Only API/web were built and replaced, using `--no-build --no-deps --wait`.
Scheduler, PostgreSQL, Caddy, environment bytes and schema are unchanged.
The learned-answer API from 3662f0b is included. Concurrent extension-only 1.31.2
commits subsequently advanced canonical; they do not change deployed backend or
frontend runtime source, and the owner's unpacked extension remains preserved.

The API now checks existing ready Gmail grants about every three minutes while
the page is closed. A dedicated PostgreSQL advisory lease admits one monitor;
Pause, disconnect, quota cooldown and shutdown remain authoritative. New grants
still start paused. This is separate from the discovery scheduler and never
calls historical reclassification. `GMAIL_BACKGROUND_SYNC_ENABLED=false` is the
monitor control; the existing historical switch remains false. Do not restart
the stopped parser-7 operator (saved exit 143 and owner-stop markers unchanged).

Contextual reading now covers short role-qualified decisions, evidence-supported
polite comparative decisions and public speaker invitations. Matching uses
supported public ATS posting identities and chronology without picking the
nearest application or dropping explicit role conflicts. Parent-domain Gmail
authentication requires aligned passed DKIM; explicit failures stay blocked.
Recognized rejections predating all recorded applications at an authenticated
employer can remain searchable unlinked evidence, excluded from confirmed
application outcomes. Stored `update` plus a shared projection preserves prior
API compatibility. Owner decisions, application identities and Undo are intact.
See `docs/architecture/2026-10-28-inbox-intelligence.md` for exact boundaries.

All **350 tracked backend files** match the tested running image. Public HTTPS
health/header report the exact web commit; four served asset hashes, 85 logos,
private-route auth refusals and application redirects pass. Separate read-only
owner-principal route probes verify actual Gmail readings/viewer documents and
Inbox/Analytics agreement in all four audited ranges, with no orphan active
outcome events. This is **not** a signed-in production browser test. Actual
new-message ingestion, automatic filing and an exact-requisition rejection were
observed after activation; their events and intended status change are traced
privately. Every pre-existing mail row/event and protected owner choice remains
unchanged. Cutover snapshots preserve all eleven non-connection table row sets;
subsequent new ingestion is reported separately from that exact cutover.

Exact-source [dedicated run 40786893860](https://github.com/anwarbuilds/ace/actions/runs/40786893860)
passes **687 focused backend, 24 calculation/render, 63 Inbox DOM and 38 hosted
browser checks**, TypeScript, full lint and build. Full run 40786902509 passes
**1,921 backend and 267 matcher cases**, web checks/build. Its extension browser
step has **46 pass / 1 fail**, the same employer-field assertion as canonical
3662f0b/run 40780743268; extension/browser-test/CI source is unchanged by this
Inbox release. Remaining app-browser steps are skipped at this exact source.
Overall CI is not green; earlier broader results do not substitute for this run.
No local Chrome was started. One redundant local combined test run stalled and
was stopped after hosted full verification; do not label that local run passed.

Fresh backup: **`/opt/ace/private-backups/inbox-system-20261028T2320Z/`**,
directory 700, dump 600, **492,230,994 bytes**. Gzip, archive catalog and full
`pg_restore --file=/dev/null` expansion pass; no database restore was performed.
Retained rollback tags are `oracle-api:before-inbox-system-20261028T2320Z`
(the learned-answer API image 7ce4007) and corresponding `oracle-web` (6b2e712).
The private `rollback.sh` verifies those images and replaces API/web only,
retaining SQL data. Do not use the earlier 19:42 backup's older API image as this
release's rollback. Never automatically restore a database over later owner work.

The owner subsequently approved the reviewed historical cohort, then requested
company-level rejection handling so role ambiguity no longer requires review.
That follow-up is being implemented; the historical proposal remains **unapplied**. Earlier approval covered the already completed parser-10
cohort only. The new source-sealed filing plan preserves all statuses; a separate
explicit proposal identifies verified rejection outcomes. Current measurements,
reference confusion counts, protected disagreements, queue reasons, screenshots,
preservation evidence and rollback details stay in the ignored private package
`artifacts/inbox-intelligence-system-20261028/RELEASE.md`. Saved owner decisions
provide a narrow rejection reference set, not representative population accuracy.
Independent per-category precision/recall and full-mailbox recall remain
unmeasured, as the owner chose existing decisions rather than new labeling.

## Extension 1.31.3 and learned-answer API LIVE, 2026-10-28 Pacific

Follow-up 1.31.3 (extension only), from the owner's Workday screenshots. The self-identification Date
showed ACE's digits but Workday reported "The field Date is required and must have a value": the
ArrowUp method did not register on the real widget and the plain-write fallback only drew the digits.
Date sections are now clicked and typed per digit (keydown, keypress, `document.execCommand('insertText')`
unless the page took the key, keyup), with ArrowUp and the plain write as fallbacks, and a date whose
box shows the value while Workday reports it missing or invalid (or `aria-valuetext` is still a
placeholder) is typed again. ACE ignores its own trusted typing events (`aceTyping`). This mirrors the
public Workday-Autofill-Assistant approach; it is unverified on a live Workday page. Name boxes holding
only the owner's own name words in another split (a résumé import put a middle name as Last Name) are
replaced by the saved name; other names stay. "Please check one of the boxes below" disability boxes
are recognized from their options (disability, veteran, gender and race option sets map to their
Answers-page rows) and an exact repeat of an answered question always matches. Automatic theme now
matches the page background (`pageTheme`), not the computer. 105 DOM contracts pass.

### Follow-up 1.31.2

Follow-up 1.31.2 (extension only, no server change), after two owner reports. (1) On an embedded
Greenhouse form, a content.googleapis.com picker frame woken by the toolbar Fill started an empty card
and took the full-viewport relay slot first, leaving the real card confined to its iframe. Frames with
no questions (and a top page that has frames) now never render or publish a card, and the top page
accepts a relayed card whenever its own card is not shown. (2) On a busy employer application page, Fill appeared
dead. Not reproduced in the DOM harness (a Greenhouse-shaped fill works in 210 ms); likely causes fixed:
`render()` rebuilt the card every few hundred milliseconds on busy pages, replacing the button under a
click in progress (now redrawn only when the HTML changes; the relayed card does the same and keeps
outer edits); a stuck `filling` flag after any exception silently disabled Fill and refresh (now
try/finally, a 45-second self-heal, and every fill entry point surfaces the error on the card with Try
again); and a copy cut off by an extension reload, including its relayed card, ignored clicks (it now
says "ACE was updated" and asks for a refresh; relayed cards carry `data-ace-instance` and the owner
style hides stale ones). Matcher maps are prototype-free. 101 DOM contracts pass. If Fill still fails,
the card now shows the exact error to report.

### Release 1.31.1 and learned-answer API

Status: the owner approved ("deploy. I need ace to work."). Canonical `wine-rose-platform` was
fast-forwarded to **`3662f0bef4fc3cb59458e1adb5e0153888799bdf`** ([PR #14](https://github.com/anwarbuilds/ace/pull/14)).
Only the API was built and recreated with `up -d --no-build --no-deps --wait`; activation ran
**22:36:41Z to 22:36:48Z (15:36 Pacific)**. New API image
`sha256:7ce4007cc67aede71334366c45ded4cb53275221096a920b2ab6bdf5d3091ae0`, container
`408f1e9c71dc55887b8b360cfd95ab4dbe0639326ea1fb675bdff6f37e4cba39`. Web (95f4a97), scheduler, PostgreSQL,
Caddy, environment bytes and schema 0050 are unchanged; no migration. The running `main.py` and
`screening.py` match the release; 21 Memory tests pass inside the deployed image against in-memory
SQLite; protected inventories (counts plus answer-bank and Memory row hashes) are identical before
preparation, just before activation and after. Public health is ok; anonymous Memory GET and PUT
return 401. Fresh private backup: `/opt/ace/private-backups/extension-learn-20261028T2233Z/`
(mode 700, dump 600, 491,657,561 bytes, full gzip check and 293-entry catalog read; not a restore drill).
Rollback image `oracle-api:before-extension-learn-20261028T2233Z` (the former
`sha256:3f8041f83ece93499013fd1d886d9dc2d5a4bd7c73dc7b0af0a248d8814b21dd`); an app rollback replaces API
only and never restores data. Answers saved in the browser before this release move to ACE on the next
page load. The extension itself is the unpacked root checkout: Reload, then open tabs receive it.

The owner reported a Workday From date failing as "Error: Invalid Date: 01/", voluntary disclosures and
common screening questions (authorization, sponsorship, government ties, conflict of interest, other
opportunities, accuracy acknowledgement, privacy tick box) never filling or saving, and asked for clear
filled/saved counts and reuse by meaning rather than exact wording.

Causes:
1. Workday date sections (`dateSectionMonth|Day|Year-input`) accept a value only through their own key
   handling. ACE typed the value and blurred the month, so Workday validated "01/" and never stored the year.
2. Since the V4 Memory release (2e7c1dc, 2026-10-25) the extension refused to fill Answers-page values
   for sensitive or company questions (EEO, sponsorship, government, consent), and both the extension and
   the API refused to save them. Before V4 every bank value filled.
3. History detection treated any question containing "to", "from" or "organization" as a job-block
   field, hiding whole Workday question pages from filling and saving.

Changes:
- Dates: set one below the target, ArrowUp keydown, click; walk with arrows if needed; blur only once
  every section holds a value; a section Workday rejected after an earlier fill is redone; a
  self-identification Date gets today. Technique cross-checked with the public job_app_filler extension.
- Answers-page values fill every matching question again. Company motivation stays excluded; a US
  authorization or sponsorship value never answers a foreign-country question; under-18 wording is guarded.
- New Memory policy `learned`: every finished owner answer is saved except motivation, signatures,
  passwords, history-owned fields, date sections and native multi-selects. Keys:
  `learn:fact|bank|topic:<text|choice>:<name>[@tenant]`. Reuse: exact reviewed screening fact, else the
  same answer-bank rule, else topic similarity at least 0.72 (Dice, or 0.8 times containment when the
  shorter question has 4+ meaning words) with equal negation, timeframe, numbers and country. History
  with a named employer (worked, applied, interviewed, referred) is scoped to the tenant. Learned beats
  older reusable/scoped records; newest wins. Choices reuse by exact label, then the label before its
  qualifier, so "Asian (not Hispanic or Latino)" never selects "Hispanic or Latino".
- Server refusal or no connection keeps the answer in `chrome.storage.local` key `aceLearnedLocal`,
  fills from it, and migrates it on the next connection (one probe per page load).
- Rules added: Government official or close links (composed from both bank rows), Conflict of interest,
  Responses are accurate and complete, Privacy notice acknowledgement; more phrases for Consent to keep
  my application on file. History roles need short labels (6 words, description 12, bare from/to 3).
- Card: "N filled by ACE · N saved for next time" opens "Answers on this form" with each answer and its
  source. The Memory switch is now "Save my answers for next time".
- API (`backend/app/api/main.py`, `backend/app/answers/screening.py`): `reuse_policy=learned` only with
  `learn:` keys; refuses motivation and signatures. Routine and scoped rules unchanged; no migration.
- Release note: a verification script under `set -euo pipefail` stopped at `diff | grep` when there
  were no differences (grep exits 1). Use `|| true` around optional greps in release checks.

Follow-up 1.31.1, same day. The owner reloaded the extension without refreshing an open Workday tab;
its old content script showed "Extension context invalidated" when saving. Chrome never re-injects
declared content scripts on reload, so `background.js` now injects the new scripts into open tabs on
`onInstalled` reason `update`. Each copy marks its card `data-ace-instance`, a shared `#ace-card-owner`
style hides every other copy's card, and Alt+A is taken on the window in capture so an orphaned copy
cannot fill with old rules. The outer-frame card accepts the new `focus-answers` class. The card now
counts Filled by ACE, Known, Unknown and Saved from page load (`formCounts`); "Saved" includes answers on
the form ACE already holds. The V4 release (2e7c1dc) had rewritten the Meijer, Verizon, ServiceNow and
Workday screening Playwright specs to expect blanks, disabling the owner's 2026-10-24 mappings; their
original expectations are restored (except the later rule that "now or in the future" needs both saved
sponsorship facts) and the same fixtures now run in the DOM suite.

Validation: 97 DOM contracts, 267 rule cases, Memory cases, 88 backend auth/Memory tests, TypeScript,
ESLint, dash and whitespace checks. Backend tests ran with pyenv 3.12.12 plus
`PYTHONPATH=.venv/lib/python3.12/site-packages`: the `.venv` python symlink now points at
/usr/bin/python3.12 and fails importing `_ctypes`. No Chrome (cooling); Playwright specs updated only.
No real Workday page was exercised: the date fix is proven against a simulated Workday spinbutton.

## Inbox backlog correction LIVE with explicitly scoped cleanup, 2026-10-28 Pacific

The owner approved exact API source **`6ee2eb223ce91f5464c9e825bf3d66f8d11aadd3`**
and a separately enumerated historical classification/filing cleanup at
**https://ace.opik.net**. [PR #12](https://github.com/anwarbuilds/ace/pull/12)
is merged by canonical fast-forward. Parser is **10**, schema **0050**.
Only API was built/recreated. Frontend remains the previously verified
**`95f4a97318d10935c9183341627ff78f08f0a85b`**; the existing UI consumes the new
API classifications. Later documentation commits do not rebuild these images.
This record supersedes earlier parser-9/no-cleanup statements below.

### Why ordinary mail remained pending and what changed

A prior-outcome guard retained old machine assessment/offer/interview readings
when the current reader returned unknown. Actual pending evidence showed that
many were optional coding lessons, account notices, digests or other routine
messages. Parser 10 identifies substantive purpose using paired body/context
signals, without relying on the platform sender or silently treating every
unknown as routine. It recognizes additional genuine branded/year-bearing test
invitations, due-in reminders, actual offers and named test completion. HTML
mislabelled as plain text is read as visible text. Workday notification branding
does not create a competing employer, and nested generic titles do not defeat a
unique longer exact title. Duplicate roles, subsidiary/agency identity, sender
authentication, chronology, positive opt-ins, final stages and Undo stay guarded.

### Explicit approval and historical scope

The user separately approved an explicit pending cohort with **no application
status changes**. A subsequent read-only comparison found protected owner links
that disagree with requisition/title evidence. Release was stopped under the
owner's critical-test condition; the owner explicitly approved the exact tested
commit and cleanup while preserving those decisions and all application
statuses. Those references were neither silently rewritten nor treated as
independent proof of the new match. Private counts, target comparisons and the
known remaining recognition gap are in the owner-local report.

The completed operation uses `backend.scripts.inbox_historical_cleanup`, which
defaults to enforced read-only preview. A complete private plan seals source,
cohort, grant and proposed fields. At most 50 known records are read per call,
with pacing and Spam/Trash metadata preflight. Apply rereads each body,
reconciles current application records, checks the plan and locked row
fingerprint, and updates **only email classification/filing fields**. It appends
one email audit event per record and never invokes status automation. Owner
choices, recorded outcomes, deferred mail and Undo remain protected. An initial
small batch passed full preservation checks before the remaining batches ran.
All original Gmail identities/metadata and out-of-scope evidence are retained;
original mutable fields remain in the private rollback plan and fresh backup.

**`GMAIL_HISTORICAL_RECHECKS_ENABLED` remains false.** This approval is for the
completed enumerated cohort, not blanket historical replay or new bulk cohorts.
Never restart the stopped exhaustive parser-7 operator. Its saved exit 143 and
owner-stop marker hashes remain unchanged. New-message ingestion continues.

### Runtime, backup and rollback

All **344 tracked backend files** match the tested source in the prepared image
and live API. API container is
`5c46fe86e386975dea3313f8f8b6dacf3801d53d1602972c1de378ba16075d91`, image
`sha256:3f8041f83ece93499013fd1d886d9dc2d5a4bd7c73dc7b0af0a248d8814b21dd`.
The exact activation snapshots at **18:27:39.435884Z / 18:27:47.708442Z** prove
every pre-existing row in twelve protected tables and the full event ledger
unchanged, with no additions/removals across that cutover. Web, scheduler,
PostgreSQL and Caddy retain their exact former container/image identities;
environment bytes, schema, auth, Pulls, Studio, Memory/extension and discovery
source remain unchanged. No migration or extension publication occurred.

Fresh private backup/rollback directory:
**`/opt/ace/private-backups/inbox-cleanup-20261028T1814Z/`**, mode 700.
The database archive is mode 600 and passes full gzip integrity, catalog and
complete expansion; no restore or restore drill occurred. The retained API
image is **`oracle-api:before-inbox-cleanup-20261028T1814Z`**, exact prior image
`sha256:dc54a2e88b8d849bc39cb4f5f17ae95eb286196d9c035c8341d6b129afe7440c`.
`rollback.sh` validates it and recreates API only with no build/dependencies.
Never restore the database automatically. Email rollback is separate: use the
reviewed private manifest/plan/seal with the tested operator rollback while the
parser-10 code is available, then revert API code if desired. It appends
corrections, preserves old events, and refuses changed fields or later owner
work. No rollback was executed.

### Validation and practical limits

Exact source full CI [40743695147](https://github.com/anwarbuilds/ace/actions/runs/40743695147)
passes **1,735 backend**, **258 matcher**, web checks/build and **47 extension
browser tests**. Dedicated [40743684914](https://github.com/anwarbuilds/ace/actions/runs/40743684914)
passes **481 focused backend**, **22 calculation/render**, **55 DOM** and **36
Inbox/Analytics browser tests**, TypeScript/lint/build. Final local Gmail/history/
cleanup verification passes **346** tests, pinned to CPU 0. No local Chrome ran.
Broader browsers finish **166 passed / 20 failed**, all names present in canonical
40615561429. The last deployed source had 19; the additional search-debounce
failure also appears in earlier canonical history. Identical names do not prove
identical causes. **Overall CI is not green.**

Live HTTPS/API health, unchanged exact frontend header, auth 401/307 boundaries,
four served bundles and all 85 logo hashes pass. Read-only production route,
mail, full-viewer and Analytics checks are separate from hosted fictional browser
QA; no signed-in production browser or independent population accuracy is
claimed. Available owner references are narrow and contain protected conflicts;
representative non-rejection precision/recall and false-positive rates remain
unmeasured. Remaining work mainly concerns safe application identity, protected
policy/timing or incomplete evidence, with a known routine-recognition gap.
Do not describe every remaining item as requiring semantic classification.

Private complete evidence and exact before/after measurements:
`artifacts/inbox-intelligence-review-20261028/backlog-cleanup/RELEASE.md`.
Keep the entire package ignored and mode 700/600. The original review/release
reports remain historical evidence. The restored root application code and
concurrent ace-inbox worktree remain preserved; only continuity docs are synced.

## Inbox Intelligence LIVE, owner-approved and verified, 2026-10-28 Pacific

The owner explicitly authorized production deployment of the reviewed Inbox
Intelligence update, requiring fresh backup/rollback, API/frontend-only scope,
preservation, no bulk historical reclassification and live verification. Exact
runtime **`95f4a97318d10935c9183341627ff78f08f0a85b`** is live at **https://ace.opik.net**. Activation completed
at **2026-10-28T16:43Z (09:43 Pacific)**; public verification completed at
**2026-10-28T16:49:03Z**. [PR #11](https://github.com/anwarbuilds/ace/pull/11)
is merged by canonical fast-forward without force. Later documentation commits
do not rebuild these images. This LIVE record supersedes the candidate status
below. No deployment approval remains pending for this completed operation.

### Historical reclassification is separately disabled

The deployment review found that the existing page-open verification loop can
call `/api/inbox/recheck` automatically. Parser 9 would otherwise make older
records eligible. To honor the owner's explicit exclusion, the tested release
adds `gmail_historical_rechecks_enabled`, default **false**, configured by
`GMAIL_HISTORICAL_RECHECKS_ENABLED`. Both eligible stale selection/counts and
the server recheck handler enforce it. Disabled requests return zero reads,
writes and remaining work with `historical_disabled: true`; new-message reading
continues. Existing recheck tests explicitly exercise the separately authorized
mode; the new regression verifies the default-off path and continued new-email
processing. Production `.env` is unchanged and the real loaded setting is false.
Do not enable it without separate owner approval. The private backlog reduction
proposal remains unapplied. Manual owner decisions/Undo remain available.

### Exact runtime, scope and preservation

API and frontend alone were built and recreated using
`up -d --no-build --no-deps --wait --wait-timeout 180 api web`. No migrate,
scheduler, PostgreSQL or Caddy service was operated. Runtime parser is **9**;
source migration head and live schema both remain **0050**. All **340 tracked
backend files** match tested source in the prepared image and actual running
API container. Public frontend commit/header and served assets match that SHA.

- Running API image: `sha256:dc54a2e88b8d849bc39cb4f5f17ae95eb286196d9c035c8341d6b129afe7440c`.
- Running frontend image: `sha256:6b2e71298f4e0f6ace548905e9eeae79e3e7e6bbdcaf861477a7d8d2266bda1c`.
- API container: `ec63918fbe4ab05ae93bbb87f82d261ac7898c40057c86282ce679433d5cd594`.
- Frontend container: `0f9a7368522012d4e4fcde7127f71f88e47f99c866eb2fa70202f1e6e7b2cf9d`.

Scheduler/PostgreSQL/Caddy retain their exact original container/image IDs and
health. Environment bytes, authentication, Pulls, Resume Studio, Memory/extension
handlers, source discovery, creation/submission rules and all unrelated runtime
source remain unchanged. The extension was not published/reloaded. ACE never
submits employer applications or marks them Applied after filling.

Fresh read-only snapshots immediately around activation prove every pre-existing
row in twelve protected tables and the complete pre-existing event ledger
unchanged. This includes existing applications, Gmail evidence/grant/decisions,
answers, Memory, history, users and Studio documents/versions. A strict whole-set
equality check initially failed on a concurrent owner-created application/event.
The successful authenticated owner request, matching event link/timing and all
unchanged prior hashes established preservation; the original failure report and
exit status are retained. No data was removed/restored to force equality.
During the longer verification interval normal owner application writes and
extension-memory usage/upserts continued and were traced through authenticated
requests. The private report distinguishes exact cutover preservation from
ongoing owner activity; do not claim a frozen database across the whole release.
All Gmail evidence, grant and prior application events remain unchanged.

No migration, database restore, bulk historical reclassification, synthetic
production record, auth-session creation, OAuth change, scheduler action or
stopped-operator restart ran. The exhaustive parser-7 operator remains absent;
saved exit **143** and both owner-stop hashes match before/after. Never restart it.

### Backup, rollback and private evidence

Fresh private release directory: **`/opt/ace/private-backups/inbox-intelligence-20261028T1633Z`**, mode **700**.
`database.dump.gz` is mode **600** and passes full gzip integrity, PostgreSQL
archive catalog and full archive expansion to `/dev/null`. No production restore
or restore drill occurred. Backup size/hash, snapshots, manifests, failed strict
comparison, owner-activity provenance, source/public/live-mail audits and service
records are private. Do not commit them.

Retained prior images are
`oracle-api:before-inbox-intelligence-20261028T1633Z` and
`oracle-web:before-inbox-intelligence-20261028T1633Z`, verified against the actual
formerly running IDs. The checked `rollback.sh` in that directory validates
the tags and recreates only API/frontend with `--no-build --no-deps --wait`.
It retains the current database, newer owner records, schema, scheduler, Caddy
and volumes. Never restore a database backup automatically for an app rollback.
Rollback was prepared, not executed; live verification passes.

Owner-local complete release record:
`artifacts/inbox-intelligence-review-20261028/release/RELEASE.md`, with source
manifest, CI logs/comparison, live verification, backup metadata and rollback.
The original fourteen-deliverable assessment remains linked from `REVIEW.md`;
its candidate status is historical. The entire ignored owner-local package is
mode 700/600 and must never be staged. Actual mail measurements remain private.

### Verification and remaining limits

Exact source hosted review [40726740989](https://github.com/anwarbuilds/ace/actions/runs/40726740989)
passes **422 focused backend**, **22 calculation/render**, **55 DOM** and
**36 Inbox/Analytics browser tests**, TypeScript, lint and production build.
Full run [40726749948](https://github.com/anwarbuilds/ace/actions/runs/40726749948)
passes **1,676 backend**, **258 matcher cases**, web checks/build and **47 extension
browser tests**. Broader browsers finish **167 passed / 19 failed**; all 19 failed
names occur in canonical run 40615561429 (165/21), with no new names. Identical
names do not prove identical causes; overall CI is not green. The final local
Gmail/history/persistence safeguard run passes **281** tests. Hosted Day/Night
desktop/mobile captures use fictional data; no local Chrome ran.

Live HTTPS/API health, exact frontend header, anonymous 401/307 auth boundaries,
four served application asset hashes and all **85** logo hashes pass. Separate
read-only production route probes verify saved/current explanations, all new
filters, the disabled historical endpoint, full mail viewer and a bounded real
mail sample against reviewed readings. Nonempty owner-reference links agree;
known body/outcome reference disagreements remain protected. Inbox/Analytics
agree, all four range invariants pass and there are no orphan active outcomes.
The probes used an in-memory owner principal in a separate process, not a real
browser session or a change to live authentication. No signed-in production
browser verification or universal classification accuracy is claimed.

The owner chose existing decisions with remaining accuracy gaps reported.
Representative non-rejection/multi-category labels, false-positive rate,
unnecessary-review rate and semantic mailbox recall remain unmeasured. The
private audit discloses reference disagreements and incomplete historical
content. New mail and the improved inspector are live; historical cleanup is
still a separate unapproved operation. Reload Inbox once for the new client.

## Pre-deployment Inbox candidate assessment, superseded by the LIVE record above

Parser 8 and the Analytics dashboard were already released. Parser 9 application
source is **`7657b62a7dab37cd77d345fcff280fb45737c15f`**, based on canonical `d5c38dc`, in
`artifacts/inbox-intelligence-worktree`, branch `inbox-intelligence-20261028`.
The restored root and concurrent `ace-inbox` worktree keep their application code.
[Draft PR #11](https://github.com/anwarbuilds/ace/pull/11) targets canonical;
later documentation commits do not change that tested runtime. Root continuity
is synchronized separately without merging or deploying this candidate. Read
`docs/architecture/2026-10-28-inbox-intelligence.md` for the focused implementation,
intent catalog, evaluation limits and exact production boundary.

The existing classifier separates substantive intent, safe application linkage
and mutation permission. It distinguishes actual requests from completion or
cancellation, conditions, negation, generic policy, progression, quoted history
and conflicting assertions. Wrapped sentences retain context. The shared body
limit is 60,000 characters with explicit incomplete evidence; the existing bounded
snippet retains decisive evidence without full-body storage or a migration.
Eligible classifier-filed correspondence can be rechecked; owner decisions,
recorded/deferred evidence and Undo remain protected. A previously recognized
outcome cannot silently become passive because the current reader does not
establish it. Actual routine account/practice/alert evidence can resolve an old
false reading. Future completion instructions do not establish a finished test.

Safe identity persists independently of status permission. Authentication is not
employer identity: parent/subsidiary and agency conflicts, Workday tenants and
shared ATS origin remain conservative. An ambiguous or uncertain inspector target
requires explicit selection. Shared SQL/Python workflow states separate linkage,
owner action, filed correspondence, routine, recorded and deferred evidence in
the existing list. The inspector explains saved/current reading, decisive
excerpt, linkage, review reason and policy. Existing strict positive opt-ins,
live/exact-ID rules, protected stages and no employer submission remain. No
Analytics design/projection or unrelated platform implementation changed.

Read-only stored-evidence inventory, stratified historical body-pattern discovery
and a completed proposal audit of the entire observed unresolved cohort ran
through the existing grant. Supplemental reads selected only known unresolved
records absent from current search, with metadata preflight. Bodies were
discarded in memory. Actual counts, proposals, reference disagreements, matching
abstentions and all 14 deliverables are private in
`artifacts/inbox-intelligence-review-20261028/REVIEW.md`, with evidence, metrics,
logs, source manifest and fictional Day/Night desktop/mobile captures. That
ignored mode-700 folder must never be staged. Short private decisive excerpts
remain only in the owner-local report. No production mutation ran.

The owner explicitly chose **existing owner decisions and reporting remaining
accuracy gaps**, rather than acquiring new labels. Existing outcome/link choices
supply narrow references; filing choices are not semantic gold labels. There is
no representative non-rejection/multi-category corpus, population accuracy,
false-rejection-rate or complete mailbox-recall certification. Unestablished
prior outcomes remain visible review work; protected disagreements were not
rewritten. Do not require new owner labels as an unrequested completion step.

Final-source hosted [review run 40705070766](https://github.com/anwarbuilds/ace/actions/runs/40705070766)
passes **421 focused backend**, **22 calculation/render**, **55 Inbox/Analytics
DOM** and **36 browser tests**, TypeScript, full lint and production build.
Full CI backend passes **1,675 tests** plus **258 matcher cases**; web checks/build
pass. Local final-change verification passes **193 parser/persistence tests**.
Final-source full run **40705078658** also passes extension browser tests (47)
and focused browsers (36); broader browsers finish **166 passed / 20 failed**.
All 20 failed names occur in canonical run 40615561429 (**165/21**); no new names.
The former Pull navigation timeout passes. The prior candidate run was 167/19;
the search-debounce browser case varies between those runs. Identical names do
not prove identical causes. Full CI is not green. Final source/results and
comparison logs are retained in the private manifest. A clock-dependent Studio
fixture failure was reproduced on
unchanged canonical source and fixed by freezing only the fictional test clock;
assertions and runtime remain unchanged. No local Chrome ran. No signed-in
production browser verification is claimed.

Fresh live read-only verification confirms parser **8**, schema **0050**, the
same five service identities and retained protected source. The exhaustive
parser-7 operator remains absent; saved exit **143** and owner-stop hashes are
unchanged. Never restart it. Audit database transactions enforced read-only;
no ingest/apply/sync/recheck, service recreation, migration, scheduler change,
extension publication, external AI or OAuth scope change ran. A full row-hash
snapshot was not captured immediately before this audit; do not describe these
checks as a new all-row cryptographic preservation proof.

A later API/web release and any normal guarded historical recheck each need
specific owner approval of the exact reviewed source and operation. The owner's
general instruction to continue finishing the review was not treated as
production-release approval.


## Analytics dashboard LIVE, owner-approved and verified 2026-10-27 Pacific

The owner explicitly requested production deployment and an exhaustive shared
knowledge update after reviewing the implementation and its CI limitations.
The exact reviewed head **`70d95a9b17a81cf475f58a7c67b19ac3ad74e31e`** is now
running on **web** at **https://ace.opik.net**. Web started at
**2026-10-28T01:58:09Z, October 27 at 18:58 Pacific**. Public verification
completed at **02:00:35Z, October 27 at 19:00 Pacific**. Canonical
`wine-rose-platform` was fast-forwarded without force to that exact head;
[PR #10](https://github.com/anwarbuilds/ace/pull/10) is merged. No approval is
pending for this completed operation. Later documentation commits do not rebuild
the running image. This section supersedes the candidate/not-deployed statements
below and older specific runtime image/SHA observations.

### Exact source, scope and preserved services

Tested runtime source is **`1376b68333311df006adacccc999c5d68850ed0d`**; the
deployed head changes only documentation after that tested source. The final
implementation diff preserves canonical backend, extension, deployment files,
Inbox components, the shared app layout and persistent `AnalyticsRefresh`
byte-for-byte. The restored root checkout supplied the starting UI; canonical
integration preserved current backend/Inbox safeguards rather than reverting
them. The code and data do not take sample numbers or employers from the images.

Preflight found production checkout **34f4663**, with its web already labeled
34f4663 and an API image different from the older 14:12 release record. Those
were the actual retained baseline for this operation; do not infer the old image
IDs still ran. The six protected running API source hashes match the approved
source, **parser 8**, schema **0050**. This operation built and recreated **web
only**, using `up -d --no-build --no-deps --wait --wait-timeout 180 web`.
API, scheduler, PostgreSQL and Caddy retained identical container/image IDs.
Environment bytes and schema are unchanged.

- Running web image: `sha256:7862199301108ecde0d59bcdfc4a70b75b922834a55ce5c73c68e8759a990038`.
- Running web container: `b2d009c19f59b75314a8d5c3f7dc40608f64564cdd8ac0b385b4b251a88d49a8`.
- Retained API image: `sha256:6192c32c4f0c37a979869c43e8ea38985a4b8a7bca2abf58f0d6b3ae780ee244`.
- Retained API container: `92dd1cc7b7ebc2aa9643c51c1d6ae77ca9a77b1cda16b37c9ff026e39e9dfbd2`.

No API rebuild/recreation, migration, scheduler change, OAuth change, discovery
change, historical Gmail recheck, extension publication, cleanup, data restore
or destructive operation ran. Auth, owner decisions/Undo, identity and submission
rules, Pulls, Resume Studio, Answer Memory and company-logo security retain their
existing implementation. ACE still never submits employer applications or marks
them Applied after filling.

### Preservation, backup and rollback evidence

Enforced repeatable read-only snapshots at **01:54:16.868962Z** before preparation,
**01:58:08.886948Z** immediately before activation and **01:58:17.182372Z** after
activation match every row in all eleven protected tables and the complete
application-event set. This includes job marks, external applications, answers,
private Memory, career facts, history entries, resumes, resume documents/versions,
users and stored Gmail records, plus protected owner mail decisions. No additions,
changes or removals occurred in these compared snapshots, either during
preparation or across activation. Audited rows were not frozen or restored.
Fresh production counts and anonymous timestamps remain private, not in Git.

Private VM release directory:
`/opt/ace/private-backups/analytics-dashboard-20261028T0153Z/`, mode **700**.
`database.dump.gz` is mode **600**; full gzip integrity and PostgreSQL archive
catalog checks passed. This is not a restore drill. The exact former web image
is retained as **`oracle-web:before-analytics-dashboard-20261028T0153Z`**,
image `sha256:1e819382130f1f2c4cf1d11c83a0e6ec3b55ddd3322867dbb98b65f95c52d5b1`.
A future approved web rollback replaces web only; it never implies restoring
older production data.

That directory retains `prepare.log`, `activate.log`, exit statuses, source/image/
container/environment records, the three private row-hash inventories,
`verification.json`, `release-summary.json`, `live-services.json`, `post-audit.json`
and owner-stop record hashes. Local private working evidence is in
`/tmp/ace-analytics-dashboard-release/`; a retained owner copy is under
`/home/ubuntu/Documents/ace-next/artifacts/analytics-production-review-20261027/release/`.
Do not stage these private files. The stopped exhaustive operator remains absent;
saved exit **143** and both owner-stop marker hashes match before/after.

### Live verification and calculation evidence

Public `/healthz` reports healthy API and exact frontend **70d95a9** with matching
`X-Ace-Frontend-Commit`. Anonymous Inbox messages/connection and Analytics API
requests return **401**; Inbox, Analytics and application-record pages return
**307** to sign-in. All **85** public company-logo hashes and all four deployed
application asset hashes match the running image. Exact served assets:

| Asset | Public path | SHA-256 |
| --- | --- | --- |
| Analytics CSS | `/_next/static/css/5b4bf304e399c6e7.css` | `4b5ca10d86cb6d78f8f26c63988254d7732f3d8f97e4ed9628efb5592dafc7e6` |
| Persistent refresh layout | `/_next/static/chunks/app/app/layout-450f09c9a7722679.js` | `d10a75a45dd5449d022f5c9ce0339d2880f0897904606787fda805da509234aa` |
| Analytics controls | `/_next/static/chunks/app/app/analytics/page-c6e54494552475ed.js` | `b6a94051a60ffb8b21729e1247ac3bfbca4e559ceff4e95b843369d5cdb91855` |
| Preserved Inbox client | `/_next/static/chunks/app/app/applications/inbox/page-f6624b592739e9b7.js` | `80e1e8a4d47af5a6344f49e18cd94024ccb77c51ff967ad12ef48cbc22db9536` |

The post-deployment primary audit passes all identity, status, cohort, role,
company, outcome and timing invariants for **14/30/90/all** selections. The
existing independent Analytics audit also passes. The exact frontend calculation
module independently reconciles all **12** daily, calendar-week and calendar-month
aggregations against that live snapshot. The audit made no Gmail calls, body
reprocessing, authentication-session creation or writes. This verifies recorded
arithmetic, not complete mailbox recall or perfect real-world identity deduplication.
Private actual metrics, full series and anonymous input remain in `post-audit.json`
and `frontend-production-audit.json` with their observation timestamps.

Hosted fictional visual and interaction evidence remains green on the unchanged
runtime: **23 Analytics browser**, **34 combined Inbox/Analytics browser**,
**47 extension browser**, **22 calculation/render**, **53 DOM**, **237 focused
backend**, **1,586 full backend**, **258 matcher** checks, TypeScript, full lint
and production build. Production image compilation and TypeScript also pass.
Eight inspected 1672 x 941 Day/Night screenshots, reference comparisons, responsive
and keyboard checks remain in the owner-local review package and hosted run
**40615555332**. Wider run **40615561429** remains **not green**: **165 pass /
21 fail** in the remaining app browser suite, the same prior 20 titles plus the
opened-Pull navigation timeout in unchanged source/test. Its cause remains
unproven. No unrelated assertion was weakened or skipped. No signed-in production
browser interaction was performed, and no local Chrome ran under cooling rules.
Reload Analytics once to obtain the new client assets.

### Product behavior, remaining dependencies and continuity

All four reference layouts retain current Inter, Wine and Rose themes and shell
dimensions. Existing APIs drive five KPIs, calendar timeline, historical-week
controls, exact date/status/evidence drilldowns, status partitions, explicit
overlapping outcome pairs, age-qualified cohorts, reliable first-response timing,
real Inbox review counts and recorded role/company breakdowns. Submission trends
compare equivalent elapsed local periods and use honest zero-prior states.
Historical chart weeks do not change the current-week headline. Full role
inspection and the existing rejected-company grid are retained.

Submitted resume/source attribution, comparable role/resume/source combinations,
complete-observation response-effectiveness rates and absent official employer/
year sponsorship records remain explicitly unavailable. A connected mailbox
does not establish complete coverage; the primary resume is not a submitted
resume; petitions/LCA certifications are not hires or new-graduate sponsorship
eligibility. Separate capture/coverage/official-ingestion dependencies are
documented in `docs/analytics/metric-sources.md`; none was implemented or approved
by this web deployment. `docs/analytics/review.md` holds the complete file
inventory, validation limits and visual differences.

The released code is in canonical `wine-rose-platform` and the isolated
`artifacts/analytics-worktree` checkout. The owner's root
`extension-context-reuse-20261026` checkout keeps application code at restored
**b5531ab**, with this complete knowledge and supporting docs synchronized by a
documentation-only commit. Do not mistake its older code for the live release.
The concurrent `ace-inbox` worktree is untouched. Future chats must read this
complete file, inspect Git/remote state and use the released source before new
implementation/deployment. Public continuity is pushed to canonical and the
root's tracked branch; raw data, audit measurements and screenshots stay private.

Operational corrections from this release: name the stop-state helper
`operator_state.py`; `operator.py` shadowed Python's standard module during a
local HTTP verification attempt, then was renamed and the check passed. In the
independent calendar harness, `undated` is family-wide metadata; subtract it
from the all-time timeline only. Finite selections already exclude undated
records. That corrected audit assertion reconciles against the API's dated
series; no dashboard/runtime change was needed. Keep both findings in future
verification rather than hiding the initially failed engineering checks.

## Analytics screenshot/data rebuild ready for review, 2026-10-27 Pacific

Status: historical pre-deployment checkpoint, superseded by the verified LIVE
release above. Its source, design decisions and earlier verification remain
useful; its pending/not-deployed statements are no longer current.

Status: source and verification complete in [draft PR #10](https://github.com/anwarbuilds/ace/pull/10),
remote branch `analytics-rebuild-20261027`, tested runtime
`1376b68333311df006adacccc999c5d68850ed0d`. Nothing was deployed. This is the
current development handoff; prior LIVE sections retain their dated observations
and do not imply that this candidate is running.

The owner rejected the reverted Analytics implementation as a design baseline.
The four attached reference PNGs match the retained approved pixel-lock kit.
The interface was rebuilt from the restored checkout in isolation, then integrated
with canonical `34f4663` so the final diff preserves all current backend, Inbox,
extension, deployment and persistent app-layout refresh source byte-for-byte.
Root `ace-next` remains `extension-context-reuse-20261026` at `b5531ab`;
`ace-inbox` was not edited or reset. The review worktree is
`/home/ubuntu/Documents/ace-next/artifacts/analytics-worktree`, local branch
`analytics-fidelity-review-20261027`. Do not stage its `.venv` symlink or ignored
artifacts, and do not reset the owner's root to this branch implicitly.

The four layouts retain Inter and existing Wine and Rose shell/tokens. Five
desktop KPIs align; Role has the four approved modules and access to all recorded
families; Companies retains six reference modules before the existing rejection
grid. Actual identities/timestamps drive daily, Monday-week and calendar-month
series, exact date drilldowns, historical-week navigation and equivalent elapsed
submission comparisons, including DST and zero-prior states. Supplemental reads
reuse authenticated existing APIs, keep identity rows server-side and refuse
inconsistent/incomplete reads. Outcome coverage, submitted resume and channel
attribution are never inferred. Missing official records leave sponsorship
analysis unavailable. LCA records are never renamed approvals or employee hires.

Green dedicated hosted run
[40615555332](https://github.com/anwarbuilds/ace/actions/runs/40615555332):
22 calculation/render tests, 53 Inbox/Analytics DOM contracts, 237 focused backend
regressions, TypeScript, full lint/build and all 23 Analytics browser cases.
All four tabs have inspected 1672 x 941 Day/Night captures plus reference comparisons;
responsive, keyboard, filters, drilldowns, logo fallback, refresh bounds and
cross-tab counts pass. Full CI
[40615561429](https://github.com/anwarbuilds/ace/actions/runs/40615561429)
passes web and 1,586 backend tests plus 258 matcher cases, 47 extension browser
and all 34 combined Inbox/Analytics browser cases. Remaining app browser suite:
165 pass / 21 fail, so overall CI is not green. Exact title comparison finds
the same 20 failures as prior run 40577319214 plus the opened-Pull navigation
test (`browse.spec.ts:78`), which timed out waiting for a company button after
scrolling. Its snapshot shows the window collapsed after an earlier expanded
assertion. Pulls source/test and global styles are unchanged. Cause is unproven;
do not call the extra failure proven pre-existing or claim no broad regression.
`docs/analytics/review.md` and private `ci-failure-comparison.txt` retain details.
Browser work ran on hosted infrastructure, honoring local cooling restrictions.

The enforced repeatable read-only audit, existing independent Analytics audit
and separate frontend calendar reconciliations pass. Actual production numbers
and anonymous timestamp input remain private and ignored under
`/home/ubuntu/Documents/ace-next/artifacts/analytics-production-review-20261027/private-audit/`.
No new real measurements are published here. No Gmail calls, body reads, new
authentication session, writes or completeness certification were made by the
audit. An automatic public-push review rejected an earlier document containing
fresh production aggregates; those were removed from Git and retained privately,
and the corrected source-only push was approved. Keep this boundary in future
handoffs.

`docs/analytics/review.md` contains the changed-file inventory, verification and
intentional visual differences. `docs/analytics/metric-sources.md` maps every
measure to definitions, fields, dates, denominators, drilldowns and missing states.
The owner-local package's `REVIEW.md` links all eight screenshots, comparisons and
the actual metric verification table. It is review evidence, not production
browser verification or a pixel-perfect claim. Submitted-file/source capture,
observation coverage and official employer/year ingestion are separate documented
dependencies requiring approval before implementation. No backend, auth, OAuth,
reconciliation, owner decision/Undo, Pulls, Resume Studio, Answer Memory, scheduler,
migration, production data, Gmail historical recheck, extension publication or
release operation was changed. The exhaustive operator stays stopped.

## Analytics refresh fix LIVE, owner-approved and verified 2026-10-27T21:13Z

The owner explicitly approved: "Approved deploy this and whatever the knowledge
you have possessed, update that in the ACE_NEXT_Knowledge.md." The approved
review head **`268e1fc64634abe324f2a4f47503ae4f4fd4e41f`** is now live on **web**
at **https://ace.opik.net**. API remains the prior approved **3cd87a5**, parser
**8**, schema **0050**. This supersedes pending-approval/not-deployed and the
older both-services-at-3cd87a5 statements below. No fresh approval is pending
for this completed operation. Canonical `wine-rose-platform` was fast-forwarded
to the exact approved head; GitHub records [PR #9](https://github.com/anwarbuilds/ace/pull/9)
as merged and closed. Later knowledge commits do not rebuild running images.
Runtime web/backend/extension/deploy source matches tested **2bceb2b** exactly;
only continuity documents differ. Backend, extension and deployment files also
match the previously running 3cd87a5 source.

**Behavior and cause:** Analytics had a coordinator inside each refreshed server
page that requested another refresh on mount. The observed production incident
was 464 Analytics GETs versus one Inbox sync in a bounded four-minute window.
The coordinator now lives once in the persistent app layout, depends on the
stable refresh method and records the route before refreshing. The initial
server response is already fresh, so hydration and replacement responses make
zero extra refresh requests; returning from another route requests one. Both
Analytics pages remove their page-local coordinators. Evidence notifications,
focus and visibility updates remain on overview and application-record routes;
unrelated routes have no Analytics listeners. The normal two-minute shell poll
and scoped Inbox checks remain. This removes the continuous self-refresh cycle
without keeping a second local application ledger or changing mail decisions.

**Activation:** web started at **21:12:07Z** (14:12 Pacific), became healthy,
and only web was recreated with `up -d --no-build --no-deps --wait`. API,
scheduler, PostgreSQL and Caddy have identical container and image IDs before/
after; environment bytes and schema are unchanged. No API build/recreation,
migration, scheduler change, extension publication, data cleanup or restore ran.
Running web image is
`sha256:d9fbd34408304c006a8b716fa99455c3a10ce59f9229c4382c402fee87eba479`.
Retained API image is
`sha256:008a0af93eed1bf1fddab600d4ccfa108bca7287934e205ff1b499ee88935af2`.

**Preservation:** enforced read-only row-hash snapshots at **21:12:06.485905Z**
and **21:12:15.508699Z** match every row in **11 tables**, including all
**7,948 stored mail rows**, all **334 protected Inbox decisions** and all
**10,263 existing audit events**. Zero additions, changes or removals occurred
across activation in these snapshots. Applied marks remain **910**. Table
counts are: job marks 1,258; external applications 48; answers 104; private
Memory 102; career facts 111; history entries 2; resumes 5; resume documents 6;
resume versions 6; users 1; stored Gmail messages 7,948. The six protected
backend source hashes also match the approved unchanged source.

Do not confuse build-window app activity with deployment changes. Between the
initial **21:07:50Z** inventory and pre-activation snapshot, one new job mark
and one audit event appeared, with applied marks **909 to 910**. An aggregate
API-log check confirms one concurrent `PUT /api/marks/:id` request. No existing
row or protected mail changed or disappeared in that comparison. The release
kept that legitimate activity; it did not freeze clients, undo it or restore
older data. `preparation-activity.json` retains the aggregate evidence privately.

**Fresh backup and rollback:**
`/opt/ace/private-backups/analytics-refresh-20261027T2108Z/database.dump.gz`,
**472,957,215 bytes**, mode **600**, containing directory **700**. Full gzip
integrity and PostgreSQL archive-catalog checks pass; this is not a restore
drill. Rollback web tag is
`oracle-web:before-analytics-refresh-20261027T2108Z`, retaining the former
3cd87a5 web image `sha256:249cd2421f94bb44a41d25da341052908ec431ac3c968ae2def822acc124c38a`.
A web rollback replaces web only and never restores production data
implicitly. The private folder retains preparation/activation logs, exact
source/image/environment/service records, all three row-hash snapshots,
`verification.json`, `live-queue.json`, `live-services.json`, operator-record
hashes, `web-bundles.json`, `public-check.json` and the preparation activity
comparison. The private local working folder is `/tmp/ace-analytics-release/`.

**Live verification:** public HTTPS checks completed at **21:13:45Z**. Health
reports API healthy and exact frontend **268e1fc**, matching
`X-Ace-Frontend-Commit`. Anonymous Inbox messages/connection/Analytics return
**401**; Inbox, Analytics and application-record pages redirect **307** to
sign-in. The publicly served shared layout bundle containing the new coordinator
and the Inbox bundle match hashes read from the running image; all **85** logo
hashes match. Shared layout bundle:
`/_next/static/chunks/app/app/layout-450f09c9a7722679.js`, SHA-256
`d10a75a45dd5449d022f5c9ce0339d2880f0897904606787fda805da509234aa`.
This verifies source, packaging and HTTP delivery, not a signed-in production
browser interaction. Reload Analytics once to load the released client code.
No local Chrome ran under the cooling restriction, and no owner session was
fabricated to claim browser verification.

The read-only live audit at **21:13:04Z** reconciles **229 pending** in Inbox,
Analytics and SQL/Python queue projections, versus **1,250 raw pending** rows.
All four date selections (14, 30, 90, all) pass identity/status/cohort/evidence
invariants. Current identities are **958**: **910** applied marks plus **48**
external applications. These are dated measurements, not UI constants; earlier
227/952 observations remain historical. The audit made **zero Gmail calls and
zero body reads**. The web fix changed no queue rule, stored decision or status.
This release does not certify search recall, complete all old-parser body
processing, or claim every stored email was understood.

**Validation and known limits:** hosted run **40577319214** on runtime 2bceb2b
passes **45 Inbox/Analytics DOM**, 82 extension DOM, 11 company contracts,
TypeScript, full lint, production web build, **1,586 backend**, 258 matcher,
**47 extension browser** and **32 focused Inbox/Analytics browser** cases.
The focused browser tests cover Inbox sidebar entry, bounded idle requests,
evidence notifications, return navigation, both Analytics routes, Day/Night
and responsive layouts. Production image build also passes compilation and
TypeScript. Broader browser results are **166 pass / 20 fail**, so overall CI
is **not green**: the previous live-runtime run has the same 19 failures, plus
one additional shortcut-focus failure whose exact title/error occurred in an
earlier 21-failure run before this fix. All 20 titles exist in that earlier
history; there is one extra versus the latest 19-failure run, not zero. Search
handler/list-controls/navigation-test source is unchanged. Pre-hydration key
handling is a plausible timing explanation, not a proven production diagnosis.
Exact runs, intermediate failures and comparisons remain below; no unrelated
assertion was removed, skipped or quarantined.

**Operating lessons:** keep refresh coordinators outside the server subtree
they refresh and avoid refetching an already fresh initial response. Test
response replacement and changing contextual router wrappers, not just stable
mocks. Streaming can briefly stage hidden `S:0` markup, so retain exact count
and clipping assertions but wait for committed page/active-tab counts. Isolate
route-refresh browser fixtures from unrelated Gmail bodies/iframe sandbox
messages while retaining browser-error assertions; email sandbox protections
stay enabled. On this VM `rg` is unavailable, so use available shell/Python
fallbacks without installing tools incidentally. Keep SSH stdin explicit for
compose exec, private artifacts mode 600 under mode-700 directories, and long
builds durable with private logs and short progress polls. Distinguish concurrent
owner actions during preparation from changes across actual activation.

The exhaustive parser-7 runner stays **absent** (zero matching runner processes)
and its saved exit **143** and both owner-stop records retain identical hashes.
It was never restarted. Normal scoped page-open checks are separate and remain
available. All requested knowledge is recorded here without mail bodies, real
answers, credentials, private row data or owner screenshots in this public repo.

## Analytics refresh correction ready for web-only approval, 2026-10-27T20:27Z

**Current candidate:** tested runtime **`2bceb2bb835e7ca78ef68248444022f26b70d95b`**,
[draft PR #9](https://github.com/anwarbuilds/ace/pull/9), branch
`inbox-analytics-refresh-20261027`. Hosted run **40577319214** passes **45 Inbox/
Analytics DOM tests**, 82 extension DOM, 11 company contracts, TypeScript, full
lint, production web build, **1,586 backend tests**, 258 matcher cases, 47
extension browser cases and **all 32 focused Inbox/Analytics browser cases**.
The expanded regression covers Inbox sidebar navigation, evidence notification,
return navigation and bounded idle request counts on overview and records.
All responsive widths and Day/Night checks pass. Web job **122447111497**,
backend **122447112099**, e2e **122447859847**, focused step 13 is successful.
The completed broader browser run is **166 passed / 20 failed** (10.4m), so
overall CI remains non-green. Exact title comparison with the previous live
runtime job **122404261309** finds its same 19 failures plus one additional
`navigation.spec.ts` search-shortcut focus failure. That exact title and error
(`#q` inactive after pressing `/` immediately after `page.goto`) already occurred
before this correction in job **122393874866** (165 passed / 21 failed). All 20
current failure titles therefore exist in that earlier 21-failure history; none
are newly observed across those historical runs. There is one extra failure
versus the latest 19-failure run, not zero. The shortcut handler, list controls
and navigation test have no source differences from the live 3cd87a5 runtime.
An early keyboard event before hydration is a plausible timing explanation,
not a proven production diagnosis. No unrelated search/extension assertion was
changed, skipped or quarantined. Final e2e job: **122447859847**; focused **32/32**
and extension browser **47/47** pass. This follow-up was checked at 20:39 UTC.
Subsequent continuity-only commits have identical runtime source. The prepared
web-only release plan is `/tmp/ace-analytics-web-release-plan.md`; execution still
requires specific owner approval of the final reviewed SHA.

**Not deployed.** Public HTTPS at 20:23 UTC confirms API healthy and web/header
still approved **3cd87a5**. Production diagnosis was read-only. Obtain specific
owner approval for this web correction, then prepare a fresh private backup,
retain the current web rollback image, and build/recreate **web only** with
`--no-deps`. Do not rebuild/recreate API, run a migration, change the scheduler,
modify data or restart the stopped exhaustive operator. Verify the approved
web SHA, public auth/assets and unchanged API/scheduler/PostgreSQL/Caddy and
protected evidence after activation. The previous 3cd87a5 approval is historical.

The incident and candidate-verification history below preserve intermediate
observations and failed checks; their pending statements are superseded above.

The owner reported indefinite refreshing when opening Analytics from Inbox.
Read-only production log aggregation confirms **366 successful Analytics GETs**
in the 19:56 to 19:59 UTC minute buckets, with 92, 118, 128 and 28 respectively.
No raw logs, owner data, Gmail calls or database changes were used by diagnosis.
Runtime remains the approved **3cd87a5**, parser 8; this correction is not live.

`AnalyticsRefresh` was mounted inside both server-rendered Analytics pages and
refreshed on mount. A replacement page could therefore start another request.
The new fictional regression renders the actual layout and page repeatedly,
replacing the page subtree and varying the contextual router wrapper: old code
requests five refreshes for five responses; the first candidate 2319739 requests just one.
This is a simulated lifecycle reproduction, not a signed-in production browser
trace. The coordinator now lives once in persistent `/app/layout.tsx`, tracks
route entry before requesting a refresh, and depends on the refresh method
rather than the router wrapper. Both Analytics pages remove their coordinators.
It listens to evidence messages, focus and visibility only on the two Analytics
routes. Returning from Inbox refreshes once; replacing a server page, changing
the router wrapper and ordinary unrelated-route focus do not restart it. The
existing two-minute shell poll and Inbox checks retain their normal behavior.

Local fictional Inbox/Analytics DOM suites, TypeScript and full web lint pass.
Added hosted browser regressions check both overview and application records
settle after opening and after an `ace-marks` evidence notification. Hosted
run **40574704624** on **2319739** passed both new quiet-page regressions,
45 DOM contracts, backend 1,586, matcher 258, extension browser 47 and web build/
checks. Its focused browser step was **29 pass / 3 fail**: three existing width
checks read `.an-page` while React staged a second hidden streaming fragment
under `S:0`. Fictional failure screenshots show one correctly drawn page. The
width test now additionally requires exactly one `.an-page` before retaining
all original overflow/clipping assertions; none are removed or narrowed. The
overview regression also opens via the actual Analytics sidebar link in Inbox
and checks return navigation. Run **40575974544** on **b6fc4f1** then passed all
refresh-request assertions (opening, evidence, return), all five responsive
widths and 30/32 focused cases, but failed an immediate active-tab count during
streaming and the new navigation test's console check from an email iframe's
sandbox refusal. These are retained failures, not a green CI claim. The active
tab count now uses the same exact, retrying count assertion. The navigation
fixture uses an empty fictional Inbox, so no Gmail body/iframe participates;
all browser-error and request-count assertions remain intact.

The final source also avoids any redundant refresh of the initial server
response: `lastPath` starts with the rendered pathname. First load and server
page replacement request zero extra refreshes; returning to Analytics from
another route requests one. This removes an unnecessary streaming overlap
rather than depending on its timing. Persistent layout coordination and all
evidence/focus/visibility updates remain. The earlier five-versus-one DOM
measurement describes the first candidate; the final regression expects zero
extra initial/response requests and one on return. Final hosted run
40577319214 on 2bceb2b passes all 32 focused browser cases, including the expanded
navigation fixture, and all 45 DOM contracts. No assertion is skipped or
quarantined. The final initial-load expectation is intentionally zero because
the actual server response already supplies fresh data.
No local Chrome runs
under the cooling restriction.

The later complete read-only 19:56:00 to 20:00:00 UTC log window counted **464**
Analytics GETs and **one** Inbox sync POST; the earlier 366 count was a snapshot
while that fourth minute was still in progress. Other paths were aggregated,
never printed as raw logs. This supports page feedback, not repeated Gmail
sync notifications. Production service start times/health were reconfirmed
unchanged during diagnosis.
A new, specific web activation approval is required after the correction is
reviewable and verified. Prior approval covered 3cd87a5 only. No API changes,
release, migration, scheduler operation or stopped exhaustive recheck ran.

## Approved job-mail release LIVE, verified 2026-10-27T19:27Z

The owner explicitly approved the prepared release with "Approved. I want it to
live." Exact approved commit **`3cd87a5948f0ac68768c5b9e0a815d25b5abcc31`** now
runs on API and web at **https://ace.opik.net**. This supersedes all pending
approval, parser-7-live and unfinished-draft statements below. Canonical
`wine-rose-platform` was fast-forwarded to that exact SHA; GitHub records PR #8
as merged and closed. Later documentation commits do not change running images.
Runtime source is identical to tested `2554569`; their difference is three
continuity documents only.

API started at **19:25:03Z**, web at **19:25:09Z** (12:25 Pacific). Both are
healthy. Running parser is **8**; all six Inbox/Analytics runtime source hashes
match the approved checkout and prepared image. Prepared/running image IDs:

- API: `sha256:008a0af93eed1bf1fddab600d4ccfa108bca7287934e205ff1b499ee88935af2`.
- Web: `sha256:249cd2421f94bb44a41d25da341052908ec431ac3c968ae2def822acc124c38a`.

Public HTTPS verification at **19:26:59Z** returns healthy API and the exact
approved frontend SHA in both `/healthz` and `X-Ace-Frontend-Commit`. Anonymous
Inbox/connection/Analytics requests return 401; Inbox/Analytics pages redirect
307 to sign-in. The deployed Inbox client bundle containing the job-mail scope
and new status wording matches its served hash. All **85** bundled logo hashes
match through HTTPS. This verifies HTTP, source and packaged assets; it is not
a signed-in production browser interaction test.

The enforced read-only live audit at **19:25:50Z** reconciles **227 pending** in
Inbox and Analytics, versus 1,320 raw legacy pending rows. The 1,093 passive
correspondence messages remain searchable, with original rows/events retained.
SQL and Python agree. Four selected date ranges pass all identity/status/cohort/
evidence invariants. There are **952** application identities: 904 applied marks
plus 48 external records; all time 757 Applied, 193 Rejected, 2 Screening and
178 dated rejections. These are observations, not UI constants. Existing possible
duplicate/date/fallback limits and six owner-filed outcome-worded receipts stay
untouched. The audit made **zero Gmail calls and zero body reads**.

Preservation is verified by full row hashes, beyond aggregate counts: all rows
in **10 protected tables**, all **259 protected Inbox decisions**, and every
existing audit event are identical across activation, with zero additions,
changes or removals in those snapshots. Applied marks remain 904. Protected
table counts before/after: job marks 1,248; external applications 48; answer-bank
104; private Memory 97; career facts 111; history entries 2; resumes 5; resume
documents 6; resume versions 6; users 1. The schema stays **0050**. Environment
bytes and scheduler/PostgreSQL/Caddy container/image IDs match exactly. Only API
and web were recreated using `--no-build --no-deps --wait`. No migration,
scheduler operation, extension publication, data cleanup or restore ran.

A fresh consistent private backup is retained at
`/opt/ace/private-backups/inbox-job-mail-20261027T1918Z/database.dump.gz`,
**471,244,094 bytes**, mode 600 in a mode-700 directory. Full gzip integrity and
PostgreSQL archive catalog checks passed; this was not a restore drill. The
folder retains preparation/activation logs, exact image/source records, private
row-hash inventories, `verification.json`, `live-queue.json` and
`public-check.json`. Rollback images are
`oracle-api:before-job-mail-20261027T1918Z` and
`oracle-web:before-job-mail-20261027T1918Z`; rollback replaces API/web only and
never restores production data automatically. An initial read-only inventory
attempt failed before backup/activation because `dict(CursorResult)` needs
`.all()` here. Its log is retained separately. Fixing that diagnostic did not
change runtime source; the corrected preservation checks passed.

Final hosted run **40564903560** on runtime `2554569` completed: **1,586 backend
tests**, 258 matcher cases, web checks/build, **47 extension browser tests** and
**30 focused Inbox/Analytics browser tests** pass. The broader browser step is
**167 passed / 19 failed**. Exact failure-title comparison finds zero new names
versus the parser-7 20-failure baseline (job 122268531501); the former scrolling
failure passes. The two additional shortcut-focus failures in the earlier
candidate run also pass in this final run. Overall CI is still not green, and
no assertion was weakened or skipped to hide those 19 failures. Final e2e job:
122404261309. No local Chrome ran.

The exhaustive parser-7 operator remains absent: **zero processes**, saved exit
status **143** preserved. It was never restarted. This release verification did
not import mail, replay bodies, file owner decisions or claim completion of the
1,661 previously measured scoped old-parser reads. Existing page-open checks now
select job-mail candidates across all dates, excluding Spam/Trash, and reclassify
eligible evidence through the new guarded code. **Refresh Inbox to load the new
UI and begin its normal scoped check.** The separate 18:29Z ID-only scope snapshot
(1,869 candidates / 1,860 stored / 9 missing) remains dated evidence; neither
that search nor the current 227 count certifies perfect wording recognition or
completed body processing. No fresh coverage claim is invented from deployment.

## Job-mail triage completed locally, 2026-10-27 11:31 Pacific

This supersedes the unfinished-draft status in START HERE below. Continued from
checkpoint `053ae41` in `/home/ubuntu/Documents/ace-inbox`. Canonical remote
`wine-rose-platform` was fetched and remains `d1b9fd2`. No release, production
mail import/recheck, migration, scheduler change or destructive operation ran.
The stopped exhaustive parser-7 operator was not restarted. Live API parser 7
was reconfirmed over SSH. Parser 8 remains a candidate until specific API/web
activation approval and verification.

Completed behavior:

- All-date job-mail candidate search includes archived mail and excludes
  Spam/Trash. It uses application phrases and recruiting senders, with no date
  cutoff by default. It is a heuristic search, not certified semantic recall.
  Ordinary personal history additions trigger ID selection, never direct body
  reads. Metadata label preflights prevent full-body reads of excluded mail.
- Listing follows every page in bounded batches. History additions and excluded
  label changes cause one scoped re-list at the captured cursor; continuing
  personal arrivals cannot perpetually restart that pass. Next checks catch
  later changes. Initial/restarted history is never treated as live positive
  evidence. Pause/regrant checks cover metadata-to-body and body-to-write races.
- Removed the provisional age cutoff and predating-email suppression. Every
  recognized unmatched historical outcome remains visible. Only legacy
  classifier-generated `unclear` correspondence projects to searchable `update`;
  partial-read reasons, owner filings, deferred and both historical Undo reasons
  remain protected. No legacy rows or events are rewritten by this projection.
- Scoped old-parser `unclear` mail is actually re-read, so a newly recognized
  outcome can still become an automatic rejection. The badge and Analytics use
  the same SQL/Python queue policy. Stale counts intersect the same completed
  all-date candidate manifest as the worker; scope-pending is an explicit client
  failure, not successful zero remaining. The client asks for recheck after
  discovery even when its pre-discovery stale count was zero.
- Removed bare assessment-platform-name classification. Complete account notices
  and job alerts are routine; an explicit body outcome takes precedence even
  under a generic account subject. Correspondence never claims an application
  status change or owner review. UI formats the single pending number with
  separators and explains the search scope/limits in Inbox and Analytics.
- A previously linked same-sender Gmail thread can narrow several roles at one
  company to one consistent target for a rejection. Conflicting thread targets,
  IDs, companies, roles, timing, sender authentication, final/newer statuses and
  positive-outcome opt-in/live/exact-ID rules retain their existing guards.

Read-only production candidate preview at **2026-10-27T18:29:00Z** (11:29 Pacific):
1,869 all-date job-mail search IDs, 1,860 stored, 9 missing; 6,071 retained stored
messages outside that search. No bodies were downloaded. PostgreSQL default
read-only transactions and a repeatable snapshot enforced no database writes.
Candidate modules ran only in a separate diagnostic process; running application
modules/files/services were not changed. Raw pending 1,320 projects to **227**,
with **1,093** legacy correspondence messages searchable without owner tasks;
all **226 recognized pending outcomes** remain visible. SQL/Python agree and
Inbox/Analytics both return 227. **1,661** stored messages are eligible for a
scoped parser recheck after an approved activation. This is a queue projection,
not a claim that 1,093 full bodies were newly understood or that the remaining
227 all require a new owner decision after reclassification.

Analytics arithmetic passes for 14/30/90/all selections: **952** identities =
904 applied marks + 48 external records; all time 757 Applied, 193 Rejected,
2 Screening, 178 dated rejections. These are dated observations during owner
activity. Two possible duplicate groups, two old date conflicts, one undated-only
recorded message and six owner-filed outcome-worded receipts remain untouched.
Private aggregate report: `/tmp/inbox-production-preview.json` on this laptop
(disposable). It contains no sender, subject, body, real application ID or token.
The initial diagnostic failed on a detached SQLAlchemy connection ID; storing
that scalar before rollback fixed it, without any production mutation.

Local validation: **319 focused fictional backend tests** and **44 React/DOM
contracts** pass, plus TypeScript, changed-file lint, forbidden-dash scan (zero)
and whitespace. New `backend/tests/test_inbox_triage.py` covers scope, history,
label preflight, routine/outcome precedence, queue agreement, old outcomes,
thread matching and Undo. Existing full-history/quota/pause/pagination fixtures
now assert the new scope and retain their safety boundaries. No local Chrome
was launched. Hosted build/browser validation and exact candidate SHA are
recorded in the follow-up below before approval is requested.

### Final candidate and hosted validation follow-up

Runtime candidate is **`2554569ea9a462ee7d7006384aa91abcac4b6472`**, draft
[PR #8](https://github.com/anwarbuilds/ace/pull/8), review branch
`inbox-job-mail-20261027`. The local worktree remains on
`inbox-clarity-20261026`. Canonical `wine-rose-platform` and production have not
been advanced. The GitHub connector could read CI but could not create the PR
(403 integration permission); the configured owner-authenticated GitHub CLI
created the draft instead. No merge or activation occurred.

The final thread guard additionally rejects anchors received before the recorded
application minus the shared 24-hour marking grace. Its 138-test fictional
parser/persistence/triage run passed. The UI and extension sources are identical
to browser-tested `fc5b006`; the only subsequent runtime change narrows this
backend thread hint. Hosted run **40564903560** on exact final runtime `2554569`
passes **1,586 backend tests**, 258 matcher cases and the web checks/build. Its
full e2e rerun is still running at this save. No overall CI-green claim is made.

The final wording safeguard recognizes direct "will not proceed with your
application" declines and preserves specific outcome/decision-worded uncertainty
even without an acknowledgement opening. Conditional instructions, withdrawals
and routine progress remain non-outcomes. A final 137-test fictional parser/
persistence/triage run passed after that correction; two additional cases pin
opted-in exact live positives versus historical/ambiguous evidence. Recheck
progress reports the count read so far instead of an obsolete pre-scan total.

Hosted run **40561850063** on preceding runtime `fc5b006` passes all **1,585
hermetic backend tests**, 258 extension matcher cases, the web checks including
44 Inbox/Analytics DOM contracts, TypeScript, full lint and production build.
The focused Inbox/Analytics browser step passes **30 tests** on that identical
web source. The older Python extension browser step reports **1 passed / 46
skipped** on that runner, not 47 exercised passes. The subsequent broader
Playwright step reports **165 passed / 21 failed**. Compared by exact failure
titles to parser-7 job 122268531501, 19 failures are shared, the old scrolling
failure passed, and two additional `/` focus assertions failed in
`navigation.spec.ts:68` and `search-and-navigation.spec.ts:22`. Those tests and
their runtime files are unchanged by this branch. Their shape is consistent
with the previously documented shortcut-before-hydration race, but no fresh
baseline reproduction was run, so do not call the two differences proven
pre-existing or describe this run as the same 20 failures. No assertion was
skipped or weakened to hide these results. Full e2e job: 122393874866. No local Chrome or signed-in production
browser mutation test was used. The earlier run 40560908265 tested 94ea47d and
was superseded by the final safeguard.

A final-candidate repeatable read-only PostgreSQL audit at **18:38:49Z**
(11:38 Pacific) again confirms **1,320 raw pending, 227 projected pending**,
SQL/Python agreement, equal Inbox/Analytics queues and 952 application identities
with every four-range projection invariant passing. It made **zero Gmail calls
and zero body reads**. Private disposable aggregate result:
`/tmp/inbox-final-production-audit.json`. The separate 18:29Z all-date scoped-ID
listing remains the source of the 1,869 / 1,860 / 9 coverage measurement above;
do not describe that as a fresh or semantically complete final body audit.
A separate read-only VM check confirms **zero exhaustive-operator processes**
and the preserved saved exit status **143**. The stopped operator was never
restarted.

Approval scope: exact reviewed API/web candidate only, using a fresh private
backup, prepared/running source match and `--no-deps`. No migration, scheduler,
PostgreSQL/Caddy recreation, extension publication, cleanup or exhaustive
operator is incidental to that approval. After approved activation, existing
page-open checks perform only scoped job-mail catch-up/reclassification; the
measured queue is a preview, and actual outcomes may change during that work.

## START HERE: job-related Inbox triage continuation, 2026-10-27 11:06 Pacific (18:06Z)

This is the latest owner scope and handoff. It supersedes older statements that
all Inbox work is finished, that parser 8 is live, or that the exhaustive
parser-7 operator recheck should continue. The owner requested this knowledge
save so a new chat can resume efficiently. **Implementation stopped at an
unfinished local backend draft. No new job-mail-only release occurred.**

### Owner intent, scope and approval boundary

The owner objected that reviewing 1,318 messages defeats the purpose of Inbox
Intelligence. Their latest instruction was: “Then do that. I'm still seeing this
13018 waiting for me and you need not to go through each and every message.
Only job-related should be fine, right? Why are you going through everything
like trash and spam?” They then requested this handoff, specifically in
`ACE_NEXT_KNOWLEDGE.md`. Do not create a second competing knowledge file.

- Cover **job-application-related mail across ALL dates**, including archived
  mail. Do not reintroduce a 30-day limit or silently discard old job evidence.
- Exclude Spam, Trash and ordinary personal mail from normal discovery and
  automatic body rechecks. The previous exhaustive ID audit included Spam/Trash
  to establish a completeness baseline; that is not the desired ongoing product.
- Automatically handle clear outcomes and routine mail; connect related evidence
  when justified. Owner review is for a specific genuine ambiguity, not every
  message a rule-based classifier fails to understand. Do not merely hide the
  badge or label unprocessed outcomes as reviewed.
- Retain searchable original evidence, recorded outcomes, owner filings, Undo,
  application identities and truthful Analytics. Do not invent applications or
  count pending mail as confirmed outcomes. Do not remove mail from Gmail.
- The owner explicitly authorized building this improvement. The earlier
  “everything live” approval activated exact parser-7 commit `3294139`; it does
  not preapprove this new unfinished parser-8 implementation. Finish the code,
  fictional focused tests and reviewable evidence, then ask for approval of the
  specific API/web release. No migration/scheduler change/extension publication
  is authorized as an incidental step.

### Exact workspace and source state

Work in **`/home/ubuntu/Documents/ace-inbox`**, branch
`inbox-clarity-20261026`, Git remote `anwarbuilds/ace`. Before the handoff save,
HEAD and the canonical `origin/wine-rose-platform` were
`d1b9fd2` (documentation of the approved parser-7 activation). PR #7 is merged.
This worktree is based on the fully released P1-P5/full-history implementation.
Inspect status/log and fetch before editing or publishing; preserve concurrent
owner work. Do not reset the draft or blindly overwrite it with remote source.

The default session folder `/home/ubuntu/Documents/ace-next` is a separate
worktree on **`extension-context-reuse-20261026` at `b5531ab`**. Its tracked
runtime code is older. Its knowledge file is synchronized for this handoff,
but Inbox development belongs in `ace-inbox`. Do not check out/merge or deploy
that older extension branch just because it is the initial working directory.
The existing untracked `ace-inbox/.venv` symlink and `web/node_modules` link
must never be staged as project files.

Unfinished runtime changes relative to the released `d1b9fd2` baseline are
these six edited files plus one new module. This save retains them in a local
WIP checkpoint commit on the Inbox branch, not a release or canonical push.
Inspect `git log` and `git diff d1b9fd2 HEAD -- backend` as well as unstaged
changes; a clean working tree does not make the draft validated:

1. `backend/app/api/routers/inbox.py`.
2. `backend/app/inbox/gmail.py`.
3. `backend/app/inbox/full_history.py`.
4. `backend/app/inbox/reconcile.py`.
5. `backend/app/inbox/queue.py` (new; preserve it with the other draft edits).
6. `backend/app/api/routers/analytics.py`.
7. `backend/scripts/inbox_analytics_audit.py`.

No frontend or test file has been updated for this new scope yet. The WIP
checkpoint has not been pushed or deployed; canonical runtime remains parser 7. The new code
is a **draft, not ready to release**. Only Python compilation and
`git diff --check` have passed for it. No new focused tests, TypeScript, lint,
DOM/browser checks, build or production verification has run for parser 8.
The 293-pass result below belongs to the released parser-7 candidate only.

### What is actually live and what was stopped

- Website: https://ace.opik.net. API runtime exact commit
  `3294139f27eaae8985b58ce6294aae0242bd747a`, **parser 7**. Web runtime
  `5ab6b1a90decfcddf8b3866fe99a9627f0f2e574`. Schema `0050`.
- Parser 7 fixes a reproduced long-email failure: extraction allowed 10,000
  characters but classification previously stopped at 8,000. Both now use the
  shared 10,000 limit with a one-character truncation sentinel; recognizable
  outcomes from partial bodies/snippets require review. Existing status,
  sender-authentication, historical-positive, exact-match and Undo guards remain.
- All P1-P5 reliability and all-time Analytics changes are already live. Fresh
  backup, API-only activation, exact source hashes, public health/auth checks
  and protected inventory evidence are in the dated release section below.
- The one-time exhaustive parser-7 recheck was **explicitly stopped to honor the
  owner's narrowed scope at 2026-10-27T16:36:09Z (09:36 Pacific)**. Only its
  Python operator process was terminated; saved per-message progress remains.
  Its runner exit status is **143, expected SIGTERM**, not successful completion.
  A later read confirmed **zero operator processes**. Do not restart it.
- Private VM records are under
  `/opt/ace/private-backups/inbox-parser7-20261027/`: `parser7-recheck.log`,
  `recheck-exit-status`, `stopped-by-owner-scope-change` and
  `stopped-by-owner-scope-change-at`. The final post-run verification sequence
  did not complete because the owner stopped the run. Do not claim it passed.
  Google had returned quota 403s and the driver was cooling down before stop.
- This did **not** deploy scoped Gmail discovery or stop the existing API
  worker's page-open checks. Live parser 7 still has the prior broad behavior;
  the owner's displayed queue has not been fixed by the local draft. Avoid
  claiming all background activity was disabled or that parser 8 is active.
- Latest read-only aggregate snapshot during handoff: connection ready, parser
  7; **7,931 stored** messages, **1,320 review**, 5,637 ignored, 781 receipts,
  167 automatic and 26 manual; 6,918 eligible stale under the *live old rules*.
  New mail/owner activity can change these. Do not resume exhaustive reads to
  force that old stale count to zero under the superseded scope.
- Earlier independently verified ID snapshot at 16:29Z was **7,928/7,928,
  zero missing**, including Spam/Trash; this is a dated whole-mailbox baseline,
  not a current scoped job-mail result. Analytics at 16:29Z reconciled 945
  identities = 897 Applied marks + 48 external records: 751 Applied,
  192 Rejected, 2 Screening, 177 dated rejections, 1,318 pending. All range,
  uniqueness, cohort, status and evidence checks passed. Do not describe all
  192 rejections as independently email-dated.
- Before/after parser-7 activation all 199 protected Inbox decisions were
  unchanged; a second retained snapshot covers the earlier 147. A concurrent
  job-mark increase 1,237 to 1,238 was privately compared against the fresh
  backup: zero existing rows changed/removed, exactly one new unapplied
  dismissal. No repair or owner override was performed.

### Review-queue diagnosis, measured read-only at 16:34:05Z

The UI number reported as “13018” has not been independently verified as 13,018.
The database audit found **1,318**, later 1,320 with arrivals. Check the real API
count/number formatting when finishing the UI; never hardcode either number.

Of the audited 1,318 pending messages:

| Classification | Count |
| --- | ---: |
| Unclear application correspondence | 1,093 |
| Online assessment | 121 |
| Rejection | 89 |
| Interview | 8 |
| Offer | 5 |
| Possible rejection | 2 |

**83% are unclassified correspondence promoted to personal work by a broad
keyword fallback.** The engine currently uses deterministic wording rules,
not a general semantic model. `application_related()` treats application words
plus a recruiting platform, job term or known company as sufficient to create
`unclear/review`. It does not separate “not understood” from an owner decision.
`_ASSESSMENT` also matches bare platform names (CodeSignal/HackerRank/HireVue),
which can label account/marketing mail as an assessment.

Reasons: 1,093 unclear wording; 105 no confident application; 60 multiple roles;
17 multiple companies; 12 positive-outcome policy; 10 unauthenticated sender;
10 email before application; 8 company only in body; 2 possible rejections;
1 duplicate job ID. The 1,093 generic cases plus 225 recognized outcomes are
not 1,318 proven genuine ambiguities.

Candidate counts: 312 none, 203 one, 803 multiple. **855 predate the earliest
recorded application** (overlap with categories above). Year counts: 2020=35,
2021=69, 2022=79, 2023=307, 2024=111, 2025=126, 2026=591. Snippet-only
indicators included 48 job alerts/recommendations and 19 verification/account
messages; these are inspection indicators, not proven classifications of the
entire body. No private body, sender, subject, real application ID or credential
belongs in this public knowledge file.

Known remaining data-review limits from the completed earlier Analytics audit:
two potential cross-history duplicate groups, two older timestamp conflicts,
one recorded message represented only by undated status fallback, and six
outcome-worded emails the owner explicitly filed as acknowledgements. Preserve
those owner decisions. Do not merge, repair or override them automatically.

### What the unfinished local draft currently attempts

- `gmail.py`: `JOB_MAIL_QUERY` / `job_query(days)` searches candidate recruiting
  terms and ATS senders, explicitly `-in:spam -in:trash`; all dates by default.
  This is only an initial heuristic. Assess missing wording/sender variants
  and non-job false positives. Do not call query matches all job mail with
  perfect recall or treat a zero query gap as proof of semantic completeness.
- `inbox.py`: both all-time and narrower sync paths share the bounded manifest;
  list requests use the job query and `includeSpamTrash=false`. Since Gmail
  history has no search filter, history additions/Spam/Trash label changes
  trigger a scoped re-list before new body reads. `FullMailboxScan` gains
  `live_ids`, `history_added`, `history_dirty` to preserve the historical/live
  distinction. Detail-time Spam/Trash excludes new ingestion. Existing rows
  and events are retained; no data cleanup/migration was performed.
- `queue.py`: shared SQL and Python projected decision helpers for legacy
  pending rows, used by Inbox lists/counts, Analytics and the audit. Draft
  turns generic unclassified mail into searchable `update` correspondence
  without rewriting rows/events. It preserves deferred, manual, automatic,
  owner-filed decisions and the explicit owner-Undo reason. It also contains
  a **provisional age/history cutoff** of earliest recorded application minus
  24 hours. This age policy is **not validated or accepted** and must be
  reconsidered so it never silently hides genuine historical outcomes.
- `reconcile.py`: draft parser version `8`, unknown recruiting correspondence
  becomes `update`; primary-subject account verification/password/job-alert
  notifications are ignored before outcome matching. This routine guard is
  also provisional: guard against losing a real body outcome under a generic
  subject. Never filter a true interview/rejection because its footer contains
  account settings or job recommendations.
- `_stale_query` omits generic `unclear` rows. `_recheck_locked` additionally
  requires a completed scoped manifest, intersects IDs and preserves original
  mail on Spam/Trash moves. It currently returns `scope_pending` with zero
  remaining when no scope is ready; **the client does not yet handle that flag**.
  Do not present it as a successful completed recheck.
- No thread-based matching, grouped decisions, historical application linking,
  expanded semantic recognition or additional safe positive automation has
  been implemented. Those were discussed as ways to reduce real manual work;
  a smaller badge alone does not finish the owner's request.

### Resume checklist and acceptance

1. Read this full knowledge file, `AGENTS.md`, `docs/HANDOFF.md` and
   `docs/knowledge/04-matching-and-applications.md`. Work in `ace-inbox` and
   inspect the saved runtime draft plus shared branch history. Preserve the
   extension/auth/data/discovery and current owner decisions.
2. Review and finish the draft before testing. In particular: verify SQLite
   and PostgreSQL SQL/Python queue projection agreement; reconsider the age
   cutoff; keep urgent unmatched outcomes visible; align stale counts with
   actual scoped eligibility; avoid repeated scoped re-lists starving progress;
   preserve cursor/positive-automation safeguards; remove stale comments and
   the now-unused cutoff local in `_backfill_locked`.
3. Update frontend `web/src/lib/inboxSync.ts`: it still declares scope only
   `"all"` and falsely describes all-time coverage as including Spam/Trash.
   Support `job_mail`, truthful scope/coverage/partial wording and `scope_pending`
   rechecks. Update `InboxIntelligence.tsx` labels, rules and counts, and
   `inboxLabels.ts` so saved correspondence is not misleadingly called an
   applied status update or owner-reviewed work. Keep a searchable view for
   retained evidence. Verify the reported review number's rendering.
4. Update `backend/scripts/inbox_coverage_report.py` with an explicit job-mail
   scope matching production selection; it currently lists all retained mail
   including Spam/Trash. Do not run an exhaustive body audit. Independent
   read-only ID comparison and DB aggregate preview are sufficient for measuring
   scoped observation and proposed queue changes. Run the reusable Analytics
   audit to verify arithmetic; never equate either report with perfect wording.
5. Add meaningful fictional regressions before claiming the change works:
   no body reads of personal/Spam/Trash mail (including history additions and
   label moves); archived old job mail still eligible; >500 IDs/all pages,
   quota/restart/deletion/malformed responses and pause/grant races; unknown
   correspondence searchable without manual task; routine account notices
   versus real outcomes; explicit owner/deferred/Undo preserved; actual
   ambiguous outcome remains pending; consistent SQL/API/Analytics counts and
   pagination; historical/live positive and exact matching restrictions.
   Existing full-history fixtures explicitly assert no query and inclusion of
   Spam/Trash, and some recheck tests invoke recheck with no completed manifest.
   Update their fixtures for the new scope while preserving their real safety
   assertions. Do not simply weaken tests to make the draft pass.
6. Focused backend command, sequential/cool on this machine:

   ```bash
   nice -n 15 taskset -c 0 .venv/bin/python -m pytest -q backend/tests/test_inbox_persistence.py backend/tests/test_inbox_reconciliation.py backend/tests/test_inbox_full_history.py backend/tests/test_gmail_reads.py backend/tests/test_inbox_display.py backend/tests/test_analytics_read.py backend/tests/test_job_marks.py backend/tests/test_external_applications_api.py backend/tests/test_auth.py
   ```

   Run focused Inbox DOM/render checks with `npm run test:inbox`, then relevant
   TypeScript/lint/dash/whitespace checks. Read `web/AGENTS.md` and the installed
   Next.js docs before web edits. No local Chrome because of cooling; use
   suitable hosted fictional browser CI. Node DOM heap 256 MB, TypeScript
   768 MB, pin heavy work to CPU 0 and avoid concurrent heavy commands.
7. Previous exact parser-7 checks: 293 focused backend pass, hosted backend/web
   pass, 47 extension browser and 30 focused Inbox/Analytics browser pass.
   Broader app suite 196 passed/20 failed, exactly the same failure set as
   parser-6 baseline. Do not claim overall browser CI green. These results
   do not validate the new draft. Exact prior run 40526589769, focused job
   122268531501, step 13. No local production signed-in browser test was done.
8. After new tests and read-only preview, present the concrete proposed release
   and measured queue effect; ask for specific API/web activation approval.
   Do not deploy parser 8 under parser-7 approval. Never restart the old
   exhaustive operator or perform cleanup/merges/destructive data operations
   merely to clear the badge.

### Operations and persistence notes for the next chat

Production: SSH via `~/.ssh/ace_oracle` to `ubuntu@161.153.89.170`, checkout
`/opt/ace`; Compose uses `--env-file .env -f deploy/oracle/compose.yaml`.
Use existing read-only reports and aggregate Python via `exec -T api python -`
without printing tokens/bodies. SSH `bash -s` non-input Compose exec commands
need `</dev/null` so they do not consume following script commands. Standalone
Python scripts in container `/tmp` need `PYTHONPATH=/app` or stdin execution.
No fake owner sessions or signed-in production mutation tests.

Current API image, private backups/rollback tag, file hashes and nine inventory
counts are in the dated parser-7 release section below. A future approved
activation requires a fresh backup and exact prepared/running source match;
replacing API/web only with `--no-deps`, never migrations/scheduler/Postgres/Caddy
as an incidental step. Backup integrity/catalog checks are not a restore drill.
Keep logs/data private with umask 077; source/build files need umask 022.

Local `/tmp` helper scripts and report files from earlier turns were absent at
handoff. Do not depend on them or rerun `/tmp/ace-job-mail-edit.py`; doing so could
apply the initial string replacements twice or overwrite further work. Source,
this knowledge file and private VM artifacts are the durable references.

### Prompt for the next chat

> Continue the reliable Inbox triage work in /home/ubuntu/Documents/ace-inbox.
> Read ACE_NEXT_KNOWLEDGE.md completely, especially “START HERE: job-related
> Inbox triage continuation”, then AGENTS.md, docs/HANDOFF.md and the relevant
> knowledge file. Preserve the saved unfinished backend draft and inspect the
> working tree/shared branch first. I want job-related mail across all dates,
> excluding Spam, Trash and personal mail. Automatically handle routine mail
> and clear outcomes; require my review only for genuine ambiguities. Do not
> just hide old or unrecognized outcomes to lower the counter. The live API is
> parser 7; the local parser-8 draft is unfinished and untested. The exhaustive
> operator was stopped at my request; do not restart it. Finish the scoped
> sync, real triage, UI/Analytics consistency and fictional focused tests, use
> production read-only for measurement, then ask before the new release.

## Historical live release checkpoint, 2026-10-27T16:30Z

The owner answered the separate parser-7 deployment question with: “What about
the developments you did? I need everything to be live.” This authorizes the
remaining API-only activation and the eligible historical rechecks described in
that question. **All developed Inbox/Analytics changes are now live.** PR #7 is
merged. The canonical branch includes `ab8d6f1`; the API image was built from the
exact tested runtime commit `3294139f27eaae8985b58ce6294aae0242bd747a`.
The merge differs from that candidate only in four continuity documents.
The existing web release remains `5ab6b1a90decfcddf8b3866fe99a9627f0f2e574`;
there are no additional web changes to release. Older pending-approval notes
below are dated history, superseded by this checkpoint.

API-only activation was verified at 16:27Z: parser 7, healthy API, unchanged
web/scheduler/PostgreSQL/Caddy container and image IDs, schema `0050`. Running
Inbox SHA-256 is `e3149312a7d2b15a95ad2ff0e79d2827a9453090921d7390a1a69b11e1e280fc`;
reconciler is `5eac2e8ef37408100f448f545940b3fb772d968bee82ed8fea0d6da7f225885f`;
Analytics remains `80db50ddcf0cb87a129680d8729ac1390fdb9947680ee79940f1cde6abd17074`.
The running API image is
`sha256:c95437dd07cc9e90c766b28f07cbf5e9edc8aa388ce358ea1cdf1e16a5c13333`.
Public HTTPS health/auth/assets passed at 16:26:51Z with the exact existing web
SHA. No migration, scheduler operation, extension publication or signed-in
production browser mutation test ran.

A fresh private consistent backup is under
`/opt/ace/private-backups/inbox-parser7-20261027/`, directory mode 700 and
`database.dump.gz` mode 600, 477,571,512 bytes. Gzip integrity and PostgreSQL
archive listing passed; this is not a restore drill. The previous API image is
retained as `oracle-api:before-inbox-parser7-20261027`. Eight of nine inventory
counts matched activation exactly. Job marks rose 1,237→1,238 during live use;
a private backup-to-live row comparison proves zero removed/changed existing
rows and exactly one additional dismissed, unapplied job. Applied marks remain
897, external applications 48, with the other seven protected counts unchanged.
All **199** current recorded/owner-filed Inbox decisions match their private
pre-activation snapshot; the earlier 147-row snapshot was also retained.

Independent read-only coverage at **16:29:29Z** again confirms **7,928 retained
Gmail IDs, 7,928 stored, zero missing**, including Spam/Trash, and zero missing
in every shorter comparison query. The real-data read-only Analytics audit at
**16:29:31Z** passes all 14/30/90/all-time projection checks: 945 identities,
751 Applied, 192 Rejected, 2 Screening, 177 dated rejections; Inbox and Analytics
both have 1,318 pending messages. The duplicate/date/status-fallback limits in
the earlier final verification remain; no merges or owner overrides occurred.

**Historical in-progress note, superseded above: parser-7 historical rechecks were running and were later stopped at owner request.** A one-time
operator runner started at approximately 16:30Z, with 7,729 eligible older-parser
messages; the other 199 are protected. It re-listed all retained mail and
confirmed 7,928/7,928, zero missing, at 16:30:12Z before rechecking. Gmail reads
are paced at least 0.7 seconds apart, with retry/cooldown handling and committed
per-message progress. The runner survives SSH disconnects; no persistent service
or scheduler was added. Its first startup failed before any work because a
standalone script lacked the application import path; explicit `PYTHONPATH=/app`
fixed that, and the failed startup log is kept separately. Runtime code is
unchanged by this operator correction.

To continue, inspect the private `parser7-recheck.log`, `recheck-runner-pid` and
`recheck-exit-status` in the backup directory. Absence of exit status means the
runner has not reported completion; check its process/log before starting any
second runner. Success runs the independent coverage and Analytics reports,
compares both protected snapshots, requires zero eligible stale messages and
zero missing IDs, and writes `parser7-final-*.json` / `parser7-final-coverage.txt`.
The runner is `/tmp/ace-inbox-parser7-runner.sh` on the VM. A container/VM restart
can interrupt it; committed SQL progress remains and must be resumed through
the same eligible service operations. Do not infer completion from code being
live, and do not claim perfect semantic recognition from full ID coverage.

## Final live verification, 2026-10-27T16:01Z

The approved API/web release `5ab6b1a90decfcddf8b3866fe99a9627f0f2e574`
is live at https://ace.opik.net. The monitored full-history import and all 441
eligible old-parser rechecks completed. A final catch-up snapshot at
`2026-10-27T16:01:16.587532Z` verified **7,928 retained Gmail messages, 7,928 in
ACE, zero missing**, including archived mail and Spam/Trash. The independent
`backend/scripts/inbox_coverage_report.py` at 16:01:48Z confirms that result and
zero missing in every comparison window. Stored evidence spans 2018-11-03 through
2026-10-27. The ready connection now has a history cursor, completed preview and
no error. Permanently deleted messages are unavailable.

The enforced read-only live Analytics audit at 16:01:47Z passes all uniqueness,
lifetime total, status, cohort and evidence checks for 14/30/90/all-time selections.
There are still **945 application identities**, 897 applied marks plus 48 external
records: **751 Applied, 192 Rejected, 2 Screening**. The Rejected count increased
from 89 to 192 after importing/rechecking real email evidence; 177 rejections now
have dates. Multiple emails about the same application do not create applications.
**1,318 messages await review**, equal in Inbox and Analytics. All 147 snapshotted
protected decisions are unchanged; eligible stale mail is zero. The 83 retained
older-parser rows are protected recorded/owner decisions, not unprocessed mail.

This verifies mailbox observation and projection arithmetic, not perfect outcome
recognition. Two potential cross-history duplicate groups, two older date conflicts
and one recorded message represented only by undated status fallback remain for
review; no repair/merge or owner override was performed. Six owner-filed
outcome-worded acknowledgements remain protected. Ignored-message indicators
remain 11 recruiting-system senders and 114 application-word messages (overlap
possible); these are inspection signals, not proven missed outcomes. The separate
parser-7 truncation-safety candidate `3294139f27eaae8985b58ce6294aae0242bd747a`
is in draft PR #7 and still awaits approval for another API activation. The
approval question was sent during the import; no answer has arrived.

Final public HTTPS health at 16:01:44Z matches the approved frontend SHA; Inbox
and Analytics require authentication. Running API source hashes match the approved
code. API/web are healthy; schema `0050`, all nine protected inventory aggregates
and scheduler/PostgreSQL/Caddy container and image identities remain unchanged.
The fresh private backup and rollback tags are recorded below. No migration,
scheduler operation, extension publication, signed-in production browser test,
destructive data repair or deployment of parser 7 occurred.

Coverage caches are process-local by design. The one-time operator process has
finished and imported rows are durable. Opening Inbox performs its authenticated
listing/history check and populates the API worker's own coverage snapshot without
re-downloading already stored messages. Ongoing checks run while Inbox is open;
this release added no always-running Gmail worker or scheduler.

## Approved activation, 2026-10-27T14:24Z

The owner explicitly approved taking reviewed commit
`5ab6b1a90decfcddf8b3866fe99a9627f0f2e574` live and requested accurate live
Inbox/Analytics data. API and web now run that release at https://ace.opik.net.
Parser 6 and the reviewed Analytics SHA-256
`80db50ddcf0cb87a129680d8729ac1390fdb9947680ee79940f1cde6abd17074`
were verified inside the running API. Public `/healthz` returns the exact frontend
SHA and healthy API; signed-out Inbox/Analytics return 401; public image assets
are readable. Schema remains `0050`; scheduler, PostgreSQL and Caddy container
and image IDs are unchanged. All nine protected inventory aggregates matched
before/after activation, including 897 applied marks and 48 external applications.

A fresh consistent PostgreSQL backup is private on the VM under
`/opt/ace/private-backups/reliable-inbox-20261027/`; gzip integrity and PostgreSQL
archive listing passed. This was not a restore drill. Previous API/web images
are retained as `oracle-api:before-reliable-inbox-20261027` and
`oracle-web:before-reliable-inbox-20261027`. Activation used API/web only with
`--no-deps`; no migration, scheduler change or extension publication ran.

The authorized one-time full-history import and parser rechecks have now
completed; the final verification above supersedes the in-progress checkpoint.
Existing automation rules and owner decisions/Undo were preserved. Historical
positive outcomes and uncertain/Spam/Trash matches remain for owner review.
Earlier unreleased/read-only notes below describe their historical checkpoints.

### Additional local candidate: parser 7, separate approval required

Deeper scrutiny reproduced a fictional long-email false-negative in live parser
6: a 9,508-character rejection was filed as a receipt because the classifier's
8,000-character cutoff was shorter than extraction's 10,000-character limit.
The candidate shares one limit, detects truncation with an extra character,
and requires review for partial-body/snippet outcomes. Parser 7 makes eligible
parser-6 mail recheckable while preserving owner filings, recorded outcomes and
Undo. All 293 focused backend tests pass. It is not included in the approved
`5ab6b1a` running release; obtain separate owner approval before API activation.
The monitored all-history import completed on the deployed parser 6. See the
additional-candidate section of the full-history report for scope and limits.

## Continuation checkpoint for new chats, 2026-10-26

This checkpoint consolidates the owner's latest decisions and the work across
sessions. Read this complete file and repository instructions before changes.
Use the dated release evidence below to distinguish tested source, built images
and running production. Later explicit owner decisions supersede older designs
or behavior notes only in the area they actually change. Preserve the history.
This checkpoint incorporates the dated deployments below. This knowledge-only
update does not deploy code, reload the browser or perform a fresh live check.

### Source and runtime state

| Item | Last recorded state |
| --- | --- |
| Repository / canonical branch | `/home/ubuntu/Documents/ace-next`, `wine-rose-platform`, remote `anwarbuilds/ace`; fetch and inspect before editing because parallel chats advance it |
| Last directly verified live API/web | API `3294139` (parser 7), web `5ab6b1a`, verified healthy 2026-10-27T16:27Z; all retained mail stored, zero missing. Parser-7 historical rechecks running; see Current live release above |
| Newer source not yet live | No outstanding developed Inbox/Analytics runtime change. Owner-approved parser 7 is live; historical rechecks running |
| Important runtime distinction | Both API and web now run the approved reliable-Inbox release. API Analytics source hash matches the reviewed projection. No extension runtime publication, migration or scheduler change |
| Unpacked extension source / browser state | Manifest **1.30.0** for contextual reuse; supporting Memory API is deployed. Browser activation needs Reload/refreshed employer tabs. No Web Store publication |
| Database | Last verified schema `0050`; no migration was run for the logo or contextual Memory releases |
| Latest recorded preservation totals | 2026-10-26 17:57 Pacific API swap: 1,231 job marks, including 892 Applied; 47 external applications; 104 answer-bank and 67 Memory rows; 111 career facts; 2 history entries; 5 resumes; 6 resume documents; 6 resume versions; 1 user. All matched before/after; these are observations, never UI constants |
| Last logo verification totals | 936 applications, 889 posting applications plus 47 external history, stable during 2026-10-26 17:19 Pacific verification; a timestamped observation, never a UI constant |

Saving knowledge does not authorize another activation. The owner separately
approved the live API/web release recorded above. Before any future release,
check running images, newer shared work and approval for that operation.
A documentation commit requires no application rebuild.

### Current product contracts

- **Website and Analytics:** preserve Wine and Rose Day/Night, Inter, the
  existing shell and the four Pixel-Lock tabs. The four approved screenshots
  under `design/ace-analytics-pixel-lock/references/screenshots/` remain the
  visual reference at 1672 x 941; read its full spec/checklist/test plan for
  visual work. The locally ignored package may be absent in a fresh clone.
  Later owner-approved changes include the Rejected companies card grid,
  newest 15 with a link to searchable records, and removal of the methodology
  section/link. Do not restore superseded table/summary-box alternatives.
- **Analytics data:** count unique actual application identities. An unanswered
  application remains pending/unknown; a 30-day observation window is not a
  rejection rule. Email evidence audit keys must not count as another
  application. Only recorded submitted resume versions, channels and comparable
  outcomes can support effectiveness claims. USCIS petition decisions are
  separate from DOL LCAs, hiring totals or new-graduate sponsorship eligibility.
  Keep missing evidence visibly unavailable instead of inventing a number.
- **Company identity:** use `CompanyLogo`/`CompanyIdentity` on every structured
  company surface. The 85 reviewed assets are an optional fast path, with
  exact aliases and source/hash provenance; newly pulled employers use the
  owner-only same-origin route. Respect refusal/robots, verified tenant
  identity, public-address pinning and raster validation. Never guess a domain,
  borrow an unrelated/parent mark, fabricate a logo or rewrite history to match
  a brand. Native dropdowns keep native keyboard behavior, with a selected mark
  beside them. Literal email bodies, notifications and inputs stay literal.
- **Inbox and Gmail:** Google sign-in and read-only Gmail are separate OAuth
  connections. `GOOGLE_*` uses `/api/auth/google/callback`; `GMAIL_*` uses
  `/api/inbox/google/callback`, with a private token-encryption key. Credentials
  remain only in private environment configuration, never this public file.
  Never claim Gmail is connected from a client ID alone. Show real ready/error/
  paused/disconnected states. Live Inbox parser 5/add-from-email and the existing audit/Undo
  rules are preserved in the verified release. Reliable-Inbox parser 6 is
  implemented locally and awaits release approval. Preserve conservative identity matching,
  ambiguity review, protected newer statuses and owner-controlled automation.
  Clear rejections can be recorded automatically under the approved exact
  matching rules; interviews/assessments/offers retain their stricter evidence
  and opt-in requirements. Importing 90 days does not mean 90 review items:
  the window controls which email is fetched; the queue counts unresolved
  evidence. Failed imports are not a successful sync.
- **Extension:** fill only after explicit Fill, toolbar Fill or Alt+A. Opening,
  hovering, focusing, typing and delayed profile responses stay passive. Mirror
  actual text/select/radio/checkbox controls and exact question labels; never
  use selected text such as Yes Required as the question. Reuse equivalent
  owner-provided routine answers without duplicate approval; keep correction,
  delete and Undo controls. The reviewed factual binary screenings can also save
  under `scoped` Memory with exact country, status-set, employer, subsidiary and
  timeframe boundaries. Saving a committed edit is separate from filling; only
  a successful save earns "saved for next time". Unsupported protected decisions
  remain manual. Work-history dates, location and current-job flags
  belong to their matched entry, not global answers. Preserve drag across the
  viewport/frames, minimize, Close and themes. Company motivation answers stay
  entirely on the employer form. Never default every question to Yes, submit
  an employer form, advance it or mark Applied after filling.

### Implementation and evidence map

| Area | Primary files / evidence |
| --- | --- |
| Analytics | `web/src/components/analytics/`, `web/src/lib/analytics.ts`, `web/src/app/app/analytics/`, `backend/app/api/routers/analytics.py`; drilldown `web/src/app/app/applications/analytics/page.tsx` |
| Shared logos | `web/src/components/CompanyLogo.tsx`, `CompanyIdentity.tsx`, `web/src/lib/companyLogos.ts`, `web/public/company-logos/provenance.json`; `backend/app/branding/{sources,discovery,transport,cache}.py` and `backend/app/api/routers/companies.py` |
| Logo cache and recovery | Four workers, 32 pending, 512 entries; seven-day success/six-hour miss; parser v4 keys; dynamic image retries at 2 and 15 seconds, at most twice, with cleanup. Unavailable evidence can still retain initials; no universal external-image guarantee |
| Inbox | `backend/app/inbox/{gmail,reconcile,display}.py`, `backend/app/api/routers/inbox.py`, `web/src/components/inbox/`; source parser version and deployed parser version must be checked separately |
| Extension | `extension/{content,fields,memory,popup,background}.js`, manifest; approved V5.1 package plus later explicit-fill and contextual reuse decisions |
| Scoped screening Memory | `backend/app/answers/screening.py`, `ExtensionMemoryInput` and existing `/api/extension/memory` handler in `backend/app/api/main.py`; `backend/tests/test_screening_memory.py`, `backend/tests/fixtures/screening_memory.json`, `extension/test-memory.js`, `web/tests/extension-review.test.mjs` |
| Exact logo release inventory, sources and rollback | Latest: `docs/architecture/2026-10-26-pulls-company-logos.md`; earlier platform, company-identity and quick-fill records remain historical |
| Extension behavior and proofs | `docs/architecture/2026-10-26-context-answer-reuse.md`, `2026-10-26-extension-explicit-fill.md`, `docs/knowledge/06-extension-autofill.md` |
| Latest private rollback on VM | API Memory release: `/opt/ace/private-backups/memory-context-20261026/`, previous image `oracle-api:before-memory-context`; logo API/web release: `/opt/ace/private-backups/pulls-company-logos-20261026/`, tags `oracle-api:before-pulls-company-logos` and `oracle-web:before-pulls-company-logos`. Never copy private artifacts into Git or automatically restore a database for a UI/API rollback |

### Validation, operating lessons and next work

Latest contextual Memory checks: 82 fictional DOM contracts, 173 fictional
backend Memory/auth/logo tests (20 screening, 67 auth, 86 logo), 258 matcher
cases, Memory safety/scope/paraphrase tests, syntax, TypeScript, lint and
whitespace/dash checks passed. The running API image also passed the 20 focused
screening tests with isolated SQLite fixtures. Public HTTPS verified the new
handler's refusal guards, existing private Memory reads, unchanged web SHA,
Pulls, Inbox, Analytics and the five reported logo hashes. No real answers were
saved by release verification.

The earlier Pulls logo release passed 159 backend logo/auth tests plus nine
source contracts, 11 company React contracts and existing Inbox/Analytics
render checks, TypeScript, lint, production builds and dash/whitespace checks.
Live checks covered all 85 bundled hashes, all five automatic routes and 15
company/job/Opportunities references. The earlier 80-image and extension 1.29.1
results below remain historical. These are recorded results, not tests rerun by
this documentation update or proof of a live employer form/browser rendering.

- Do not launch Chrome/browser tests on this laptop while the cooling
  restriction stands. Nine logo and 39 extension Playwright cases were collected
  only in those releases. Fresh browser screenshots, pixel comparison and real
  employer-form verification remain pending on suitable hardware.
- Run heavy local commands sequentially and pin them to `taskset -c 0`. For
  Node DOM tests use `--max-old-space-size=256`; assert boolean presence/identity
  instead of serializing circular DOM nodes on failure. Use relevant focused
  tests, not a new full-suite run for a documentation-only change.
- Starlette TestClient can stall on its first request under the restricted
  sandbox. An approved run outside that restriction passed with isolated
  fictional records and mocked networking. Do not mistake this for an API bug
  or substitute real owner data for a fixture.
- In SSH `bash -s`, redirect non-input `docker compose exec` calls from
  `</dev/null`; otherwise they can consume the following heredoc commands.
  Pass actual intended stdin explicitly for Python scripts or restore-catalog
  checks. A `pg_restore --list` consumer can close a gzip pipe early; distinguish
  expected SIGPIPE from a failed backup rather than suppressing all errors.
- Use umask 022 for Git checkouts/public source files and umask 077 for private
  backups. The web image grants public files read/traversal access before
  switching to its unprivileged runtime user. Verify hashes through public HTTPS;
  healthy `/healthz` alone did not catch unreadable new assets.
- Prepare/build/test before an authorized API/web activation. Do not restart
  schedulers, migrate, publish the extension, change Gmail permissions or
  perform destructive operations as incidental release steps. Both legacy and
  Oracle discovery remain independent, with separate databases and replication
  disabled. Numeric job IDs must never be merged across those databases.
- Keep source, runtime and evidence states current after each session. Fetch
  before edits/push, reconcile concurrent changes without force-push, preserve
  owner edits, record exact files/tests/limits and use the owner's Git identity
  without co-author trailers. No user-facing em dashes. Keep replies short.

Next work must follow the owner's next request. Known outstanding work includes
approval and runtime verification of reliable-Inbox P1 to P5, browser visual
validation on suitable hardware, ongoing independent discovery comparison,
actual availability of official sponsorship/resume/channel evidence, and owner
verification of the reloaded extension on real forms. Do not silently turn
these pending items into completed work or start them merely because they are
listed here.

## 2026-10-26: Contextual answer adoption, API live, extension 1.30.0

### Owner request, root cause and final behavior

The owner reported repeated screening questions after already answering them and
asked for reuse based on compatible meaning/context rather than exact wording.
The old API deliberately rejected protected/company questions, so one-form
completion could never become future Memory for most pictured screenings.
Routine canonicalization also missed common paraphrases, identical duplicate
entries were treated as conflicts, and a trusted edit committed before Memory
connected was not retried. Source `9d05673248ce6ead30652e62bb1d5e569404848c`
fixes these paths. PR #5 is merged into `wine-rose-platform`; documentation
commit `d15b2f3` records the completed deployment. Later documentation SHAs do
not identify different running images.

This specific owner-authorized `scoped` policy supersedes older blanket
per-application-only rules for the reviewed facts below. It does not authorize
loose keyword matching, inferring unknown answers or reusing arbitrary protected
questions. Existing V5.1 employer-motivation exclusion remains in force.

- **Adoption and receipts:** with **Auto-save reusable answers** enabled, a real
  committed owner edit can save once without duplicate approval. Existing
  `aceAutoLearnRoutine` preference is retained. A delayed Memory connection
  retries only the still-current trusted edit; it never initiates filling.
  Native and supported custom choices must verify committed employer state.
  Uncommitted search text/unknown options stay unlearned. Successful saving
  alone adds "N saved for next time"; failed saving preserves completion and
  offers Retry. Local completion is not proof of persistence.
- **Routine equivalence:** reviewed prompt/verb variants normalize, including
  building/developing/implementing and using/utilizing. Question kind, negation,
  numeric values and timeframe remain significant. Identical duplicate answers
  can resolve; differing answers stay conflicts requiring correction.
- **Reviewed binary screenings:** exact two-status US citizen/permanent-resident
  and four-status citizen/permanent-resident/refugee/asylee questions; combined
  present/future visa sponsorship; named-employer current/past work; temporary
  work and interview history; agency submission within the last 12 months; and
  the complete current/former-employer post-employment-obligations question.
  Only explicit Yes/No answers with the computed scope can save. Do not derive
  compound eligibility from one status, combined sponsorship from only one
  timeframe, or all post-employment obligations from a narrow non-compete fact.
- **Context boundaries:** named employer, subsidiary scope, previous versus ever,
  status sets, country and timeframe remain distinct. Explicit US sponsorship
  is separate from unspecified-country wording. Relative employer wording,
  agency submission and unspecified work country bind to the hiring tenant/site.
  Workday locale/site paths, myworkdaysite recruiting tenant/site and Oracle
  sites stay separate. Greenhouse, EU Lever, Ashby, Workable, SmartRecruiters and
  Gem use recognized employer tenant paths; unsupported shared-host variants
  are rejected. Employer-owned sites bind to their actual host.
- **Private API:** existing `/api/extension/memory` accepts `reusable` or `scoped`
  policy. Scoped keys use `fact:v1:` and are checked against the server's reviewed
  question/key/scope/binary-answer catalog. The reserved namespace cannot enter
  through ordinary reusable policy. Existing rows keep their policy and revision
  checks; incompatible edits fail instead of silently broadening reuse. The
  existing schema 0050 `reuse_policy` column suffices; no migration or historical
  answer-bank/profile rewrite. Corrections/deletions invalidate on-form reuse
  copies. Existing employer-entered values are preserved.
- **Unchanged boundaries:** Fill, toolbar Fill or Alt+A remains explicit. Opening,
  focusing, hovering, typing and late responses never start filling. Motivation
  is excluded before reading values. Attestations, signatures, consent,
  demographic choices and unsupported protected facts stay manual. No submission,
  step navigation, Applied mark, Gmail scope, auth-model or discovery change.

Runtime files: `extension/{memory,content}.js`, manifest **1.30.0**,
`backend/app/answers/screening.py` and the existing Memory handler/input in
`backend/app/api/main.py`. Fictional tests are in `extension/test-memory.js`,
`web/tests/extension-review.test.mjs`, `backend/tests/test_screening_memory.py`
and shared `backend/tests/fixtures/screening_memory.json` (18 scope cases).
Local checks passed 82 DOM contracts, 173 backend Memory/auth/logo tests,
258 matcher cases, Memory safety, syntax, TypeScript, lint and dash/whitespace
checks. Thirty-nine Playwright cases in nine files collected only. Chrome and
real employer verification were not performed due to the cooling restriction.

### Approved API deployment and verified preservation

The owner explicitly said **Deploy** after the separate API change was prepared.
Activated 2026-10-27T00:57:27Z (2026-10-26 17:57 Pacific); public verification
finished 2026-10-27T00:59:08Z (17:59 Pacific). API runs `9d05673`; website remains
`1fee67127877838f09b9a42f5edef6bc4669f34e`. API branding parser 4 and the existing
`6163f59` Inbox parser 5/add-from-email behavior remain. Reliable-Inbox P1 to P6
were unimplemented at that release; their read-only report script was present
in the API image but was not run by the Memory release. The later local Inbox
implementation and its read-only baseline are recorded in OPEN WORK below.

A fresh private PostgreSQL backup passed full gzip integrity and PostgreSQL
restore-catalog checks, not a restore drill:
`/opt/ace/private-backups/memory-context-20261026/database.dump.gz`,
470,305,554 bytes. The directory also retains private inventories, container/image
records, source hashes and preparation/activation/verification logs. Prior API
image tag: `oracle-api:before-memory-context`. Rollback replaces only the API
image; never automatically restore production data for this release.

Built only API and activated with:

```bash
docker compose --env-file .env -f deploy/oracle/compose.yaml up -d --no-build --no-deps --wait --wait-timeout 180 api
```

The prepared/running healthy image ID is
`sha256:f0a2546982ff00316276f71081654dff70ef01ec35fd393da6a93814855aede3`.
Web, scheduler, PostgreSQL and Caddy container IDs and private environment
checksum were identical before/after. Schema stayed `0050`. No migration,
scheduler invocation, data restore, Gmail sync/recheck, application write or
extension publication ran. Before/after protected aggregate counts matched:

| Resource | Count |
| --- | ---: |
| Job marks / Applied marks | 1,231 / 892 |
| External applications | 47 |
| Answer-bank rows / private Memory rows | 104 / 67 |
| Career facts / history entries | 111 / 2 |
| Resumes / resume documents / resume versions | 5 / 6 / 6 |
| Users | 1 |

These timestamped counts are release evidence, never UI constants. The earlier
17:19 logo verification had different application totals; subsequent owner
activity is not a release migration or a reason to rewrite history.

Public `/healthz` returned 200 with healthy API and unchanged web SHA. Anonymous
Memory GET returned 401; owner GET returned 200/no-store with 67 existing rows
without printing questions/answers. Intentionally invalid fictional scoped and
reserved-namespace writes returned the new handler's exact 422 refusals and
saved nothing. Memory count remained 67. Temporary five-minute verification
sessions were revoked in `finally`, including incomplete verification attempts.
Signed-in `/app/pulls`, `/app/applications/inbox` and
`/app/applications/analytics` returned 200. Uber, Optiver, Chime, temporal and
twitch assets still matched their reviewed public hashes.

Twenty focused screening tests passed inside the deployed image using isolated
fictional SQLite fixtures, not production writes. Test-process overrides were
`DATABASE_URL=sqlite://`, `ACE_AUTH=required`,
`REQUIRE_LOGIN_EMAIL_CODE=false`, `WEB_BASE_URL=http://localhost:3000`.
The initial run without local sign-in overrides passed 18 catalog cases and
failed two pairing fixtures before reaching the handler because it inherited
the production email-code requirement. Service configuration was not changed.
The first HTTPS script used root-level page paths rather than `/app/...`; its
corrected run used the actual routes. Logo preservation compares expected local
hashes because public website assets are intentionally absent from the API image.
These verification-script corrections did not change or redeploy runtime code.

Running source SHA-256 values matched the tested checkout:

| File | SHA-256 |
| --- | --- |
| `backend/app/api/main.py` | `bba3e8fec5eb68a91b774646f71d1acb4c688a37c4798d87857cc61456a22c73` |
| `backend/app/answers/screening.py` | `ac913c93b57a2eaf5bf70ab06871a204fc00adef9f9ed9426cfd9cc590d67845` |
| `backend/app/branding/discovery.py` | `b91c2b7722d7e748cd15d4d636576bd9f69dcd5d30dfc4df77610eda4e4f613c` |
| `backend/app/branding/sources.py` | `5a9dcdc81ecc2eae842aa0b119c46be20ec74daa9bd632ca71bd717ad91fba89` |

### Owner activation and remaining limits

1. At `chrome://extensions`, Reload ACE from the unpacked source directory
   `/home/ubuntu/Documents/ace-next/extension` (manifest 1.30.0).
2. Refresh each employer/application tab so it gets the updated scripts.
3. Keep Auto-save reusable answers enabled, commit one eligible answer and
   confirm "saved for next time". Completion alone is not a saved receipt.
4. On a later context-compatible question, use explicit Fill to reuse it.

Previously rejected saves cannot be reconstructed from closed forms; newly
eligible facts need entering once. Existing saved routine/profile facts remain.
Browser Reload, installed MV3 state and the owner's actual Workday interaction
have not been confirmed; do not call these production-employer verification.
No new permission or activation was granted by the knowledge-only follow-up.
Detailed supporting release record:
`docs/architecture/2026-10-26-context-answer-reuse.md`.

## OPEN WORK for the next chat: a reliable Inbox (measured 2026-10-26 evening)

**Superseded scope:** Start with the latest START HERE section above. The owner
now wants all-date job-related mail only, excluding Spam/Trash, and effective
automatic triage. P1-P5/parser 7 are live; parser-8 triage is an unfinished draft.
Do not restart the stopped exhaustive operator.

**Current status, 2026-10-27T16:01Z:** P1 to P5 and all-history scope are live on
`5ab6b1a`; 7,928/7,928 retained messages are imported, 441 old-parser rechecks
finished, and live Analytics arithmetic checks pass. Review the remaining
uncertain evidence and obtain approval for the separate parser-7 candidate in
PR #7. The measurements and pending-release statements below are historical;
start with Final live verification above.


**Owner request.** After Inbox and Rejected applications shipped, the owner
showed an employer update email from a week earlier that was not recorded, and a
search for that employer in Rejected applications found nothing. They said they
cannot tell how far to rely on Inbox Intelligence and want "this reliable
system" built. They also approved **read-only production queries** for this work
(in chat, 2026-10-26 evening). Releases still need their go-ahead.

**Status: P1 to P5 implemented locally, release awaiting owner approval.**
The original diagnosis/plan below is retained as historical evidence. The
implementation is in `/home/ubuntu/Documents/ace-inbox` on
`inbox-clarity-20261026`, fast-forwarded through concurrent source/documentation
commit `b5531ab`. `.venv` and `web/node_modules` are existing symlinks to
`ace-next`; do not commit those local links.

### Implementation checkpoint, 2026-10-26 evening

- P1 follows all Gmail ID pages, checks stored IDs in chunks of 500, downloads
  at most 60 new emails per call newest first and commits every message. The
  profile baseline is read before listing; cursor/preview completion waits for
  the full window and history to finish. Expired history falls back safely;
  incomplete listings, deleted messages, quota failures and duplicate races
  cannot earn a false completion claim. Per-connection locks serialize sync,
  recheck and the retained backfill endpoint within the API process. Pause or
  disconnect stops further batch work. Only history-added IDs can enter the
  opted-in live positive-outcome path; wider-window positives remain previews.
- Coverage `{days,gmail,in_ace,missing,checked_at,complete}` is in memory per
  connection/grant/window, returned by sync and connection, null after restart
  or reconnect. The page verifies automatically, loops batches with saved
  progress, rechecks old evidence automatically and offers Verify further back
  for 30/90/365 days. Failures remain visible; a wider interrupted verification
  keeps its selected window for retry. Counts use the same calendar boundary
  (including the boundary day) as the independent report script.
- P2 parser 6 recognizes the fictional sponsorship/eligibility wording; unknown
  application-related mail becomes `unclear` / Application email / Needs you,
  with ranked candidates. Job-board unknown mail and self-sent mail stay out of
  this review safety net. Conditional eligibility instructions do not automate
  rejection. Existing authentication, exact-identity, ambiguity, timing, final
  status, opt-in, event and Undo rules remain.
- P3 rechecks recent (120-day) ignored recruiting rows under older parsers using
  shared sender/application/job word lists and SQL `ilike`. Owner filings and
  manual/automatic outcomes remain untouched. Recheck runs on page open even
  after a recent Gmail timestamp.
- P4 empty records searches return bounded `not_listed` application matches
  across all dates/statuses/roles plus stored sender/subject/excerpt matches.
  The page explains current status, submission dates/range, decisions and email
  classifications, with existing application/Inbox links and all-time search.
  A direct rejection drilldown without explicit dates defaults to all time;
  chart-selected dates remain intact. Nothing is inferred or mutated.
- P5 warns inline and asks for an explicit override before an outcome when the
  chosen company's name or initials appear nowhere in the email. Works for
  both existing and add-from-email applications. No speculative parent aliases
  were added; automatic company matching is unchanged.

Validation: 241 focused fictional backend tests; 32 React render/workflow/DOM
contracts; TypeScript, focused ESLint, whitespace and zero-hit dash guard. The
Inbox Node contracts now run in CI with `npm run test:inbox`. Browser fixtures
were updated and collected only; no Chrome, screenshots, real employer tests or
production build/activation. Source implementation, release steps and exact
checks: `docs/architecture/2026-10-26-reliable-inbox.md`.

The approved read-only report ran once against the existing live parser 5:
516 stored emails; Gmail 7/30/90-day listings 274/949/1,625, all listing pages
complete; present 274/516/516; missing 0/433/1,109. Decisions ignored 249,
receipt 193, automatic 50, manual 24; 319 stored under older parsers. Connection
ready with no cursor and incomplete preview. These are a dated baseline,
not evidence of a completed import. No production sync, recheck, review,
application mutation, migration, scheduler operation or deployment ran.

**Remaining P6:** obtain approval for the exact implementation commit; build and
activate API/web only under Safe production release, keeping schema/services
and rollback inventory intact. Production stays on API `9d05673`, web `1fee671`
until an approved activation verifies otherwise. Then the owner opens Inbox to
verify/re-read automatically, and reruns the read-only report to compare actual
Gmail/ACE counts. Browser visuals still require suitable hardware.

### Owner scope update, 2026-10-27: ALL history, not a recent window

The owner explicitly said "I need all, everything." This supersedes the initial
30/90/365-day plan above. Sync/backfill and Analytics now default to All time.
Full scanning includes archived mail and retained Spam/Trash, with no date or
page-count ceiling. It lists up to five pages/reads sixty details per request,
saves each message independently, resumes the manifest while running and proves
coverage afresh after restart without re-downloading committed messages. The
pre-list history baseline is reconciled completely for arrivals/deletions before
completion; narrow-window checks cannot advance this manifest's own cursor.
No new schema, permission, scheduler or background service. Old ignored mail is
rechecked without the former 120-day/keyword restriction; owner filings and Undo
remain protected. Spam/Trash outcomes always require review; historical positive
automation and exact-match/status/timing guards remain protected.

**Latest full read-only coverage**, `2026-10-27T13:19:13Z`: Gmail all retained
history lists **7,927** IDs, **524** stored, **7,403** missing; all pages complete,
including Spam/Trash. Permanently deleted messages are unavailable. Mailbox
messages are not equivalent to job outcomes. Parser 5 is still live: 250 ignored,
197 receipts, 51 automatic, 26 manual; 319 under older parsers. No cursor or
completed preview. The report also prints windowed comparisons but ALL history
is the acceptance scope. These are dated observations while the owner uses ACE.

The all-time aggregate audit at `13:10:24Z` reconciles **945** persisted identities
to 897 applied marks plus 48 external records. All-time statuses: 853 Applied,
89 Rejected, 3 Screening. The 90-day selection misses one older application and
rejection. All projection invariants pass; two possible duplicate pairs, two old
date conflicts and six owner-filed acknowledgements remain untouched. A separate
read-only candidate replay at `13:16:58Z` keeps IDs/statuses/totals and the
67-application timing sample/median, restores two dated rejections (67 to 69),
corrects seven links and six latest-company dates. SHA-256 of replayed Analytics:
`80db50ddcf0cb87a129680d8729ac1390fdb9947680ee79940f1cde6abd17074`.
Live parser-5 helpers were imported in that process; it is not a full mail or
parser-6 replay. Nothing was written to production or deployed.

**Local validation:** 286 focused fictional backend tests, 42 React workflow/DOM
contracts, TypeScript, focused lint, dash and whitespace checks pass. Full-history
tests include 2010 mail, >60 pages, quota/restart, cursor/deletion races and
unconfirmed missing details. Hosted CI's obsolete extension Queue fixture was
isolated; 46/47 then passed, and the remaining old unscoped employer-answer
assertion now matches the approved protected/scoped-Memory behavior. No extension
runtime or skipped assertions. Verify the final hosted CI before release; no
local Chrome. Owner approval remains required for the final branch commit,
then API/web-only build/activation and actual full import/recheck verification.
Four additional failed-then-fixed fictional cases pin a recheck race with owner
filing/confirmation, pause and reconnection during a Gmail read. Rechecks now
refresh connection/grant state and reselect current eligibility with a short
PostgreSQL row lock only after network access, so owner actions are preserved.
Full evidence: `docs/architecture/2026-10-27-full-history-inbox.md`.

### Subsequent Inbox-to-Analytics scrutiny, 2026-10-26 evening

The owner requested a senior-level completeness audit before deciding on
release approval. **Verdict: the live Analytics uses real records, but exhaustive mailbox
coverage and distinct real-world application totals cannot yet be certified.**
The initial P1 to P5 commit `e6e6a93` is on draft PR #6, not deployed. The audit
adds tested corrections on the same review branch; approval must refer to its
new final commit, not the superseded initial release candidate.

Read-only production evidence, 18:49 through 19:10 Pacific:

- Gmail still lists 949 emails for 30 days versus 516 stored (433 missing);
  90 days lists 1,625 versus 516 stored (1,109 missing). Parser 5 remains live,
  249 messages are ignored and 319 were read under older parsers. These are
  mailbox messages, not a claim that every missing item is a job outcome.
- All 939 stored application identities reconcile to 892 applied marks plus
  47 external records. Four selected ranges (14/30/90/all) pass unique-row,
  status, cohort, outcome-record and persisted-total checks. All-time statuses
  are 850 Applied, 86 Rejected, 3 Screening. Thirty-day submission filtering
  shows 559 records and 66 rejections; all time shows 939 and 86.
- Of 74 recorded email messages, 64 have counted evidence links, 6 deduplicate
  to another email for the same application/outcome kind, and 4 retain only an
  undated stage. Two of those four are within Inbox's 24-hour marking grace;
  Analytics incorrectly dropped their dates/links. The other two predate the
  application by more than a day and remain excluded with review links.
- A repeatable read-only comparison of the reviewed projection in a separate
  diagnostic process restores 2 dated rejections (64 to 66 all time), corrects
  7 evidence links and 6 latest-company dates. Application IDs, statuses,
  rejection/positive totals, the 65-application timing sample and median stay
  unchanged. No running service or source file was replaced. The projection
  source SHA-256 was `e67da61ff031f447653dc74a17f584a5d475fdebc93ce064eb49f27ca54cfd1f`.
- Five outcome-worded messages were explicitly owner-filed as acknowledgements
  (classifier labels: rejection, possible rejection, interview and two offers).
  They are preserved, not silently promoted. Four apparently orphaned ledger
  rows are old Applied/cleared bookkeeping, not missing outcome evidence;
  orphan active outcome count is zero.
- Two exact company/title/submission-date groups span a job mark and external
  history. Both external rows lack a posting URL, so they are **potential**
  duplicates requiring owner review, not proof of duplicate submissions. No
  identity was merged, removed or reclassified. Do not describe 939 persisted
  identities as a proven count of distinct real-world submissions.

Additional local corrections: keep first response timing separate from latest
outcome dates/links; let a later verified positive outcome supersede an older
rejection in the cohort while preserving both historical events; account for
deferred mail; disclose coverage and excluded evidence on Analytics; distinguish
undated recorded stages from explicit actor provenance; notify the existing
marks bus and refresh Analytics on open/return; load a recorded email's own
event history so Undo remains usable beyond the global latest 100 events.
Opted-in live assessment/recruiter outcomes now set Screening, and positive
automation cannot regress an Interviewing or Offer stage. Opt-in, exact-ID,
authenticated origin and historical-preview restrictions remain unchanged.

The new reusable `backend/scripts/inbox_analytics_audit.py` uses a repeatable
read-only PostgreSQL snapshot, prints aggregates only and makes no Gmail calls.
Use it alongside `inbox_coverage_report.py`. A green `projection_checks_pass`
never implies mailbox completeness; `mailbox_coverage_certified` stays false.
Fictional tests also prove no SQL writes/private text in the audit output.

Validation: 255 focused backend tests, 37 React render/workflow/DOM contracts,
TypeScript, focused ESLint, whitespace and forbidden-dash checks pass. No Chrome
or real browser rendering; application image builds and release approval remain
pending. Full evidence, limitations and operator commands:
`docs/architecture/2026-10-26-inbox-analytics-scrutiny.md`.

Hosted CI on audit source `c54a352` passed backend/web, including full hermetic
tests and a Next build, but stopped before new-app tests: an unchanged extension
fixture expected the removed legacy Queue at `/` (20 tests passed, 27 setup
errors). The same failure existed on `e6e6a93`. The follow-up isolates fictional
extension forms on unique blank pages and fixes stale workflow labels without
changing extension runtime or skipping assertions. Hosted CI must validate the
final head; no local Chrome. The first fixture follow-up `e3419f7` removed the
setup errors but had 12 failures/35 passes: its fragment-only unique URL retained
prior document/extension state. The final fixture changes the actual data payload
and awaits that exact ready document. No assertions or runtime behavior changed.
The coverage report also uses a one-day date-cutoff buffer and default Spam/Trash exclusions, not exact rolling 24-hour intervals.

### Measured in production (read-only, aggregate, 2026-10-26 about 17:30 Pacific)

Run it again any time (the owner approved read-only runs; it only lists Gmail IDs):

```bash
ssh -i ~/.ssh/ace_oracle ubuntu@161.153.89.170 'cd /opt/ace && docker compose --env-file .env -f deploy/oracle/compose.yaml exec -T api python -' < backend/scripts/inbox_coverage_report.py
```

| Check | Result |
| --- | --- |
| Gmail messages listed for the last 7 / 30 / 90 days | 271 / 946 / 1,622 |
| Of those already stored in ACE | 270 / 512 / 512 |
| Missing from ACE | 1 / 434 / 1,110 |
| Stored emails | 512, received 2026-10-12 to 2026-10-26 |
| Decisions | ignored 248, receipt 190, automatic 50, manual 24 |
| Classifications | unknown 248, acknowledgement 185, rejection 74, offer 2, assessment 1, possible rejection 1, interview 1 |
| Parser versions | v1 143, v2 74, v3 95, v4 7, v5 193 (319 stored under an older parser) |
| Ignored ("No outcome found") from recruiting systems / with application words | 112 / 179 |
| Acknowledgements linked to an application | 126 of 190 |
| Applications | 888 applied marks (oldest 2026-08-23) plus 47 external |
| Gmail connection | ready, no history cursor, preview not complete, no error, last check 2026-10-26 21:59Z |

### Root causes (all confirmed in code, three also in data)

1. **The import never completes.** `sync_once` in `backend/app/api/routers/inbox.py`,
   with no cursor, lists ONE page (`maxResults` 500) of the 30 day window and never
   follows `nextPageToken`. `partial` is then true, so the cursor is never set and
   every sync only re-reads the newest 500. The window holds 946 emails and 434
   are not in ACE (45 percent); the 90 day window is missing 1,110. The manual
   100 per page "Import past email" is the only other way in. Rejections for
   applications made since late August can sit in the missing part.
2. **"No outcome found" is a silent dead end.** 248 of 512 stored emails were
   decided `ignored` and never appear in Waiting for you. `_stale_query` (what
   `/api/inbox/recheck` re-reads) covers only waiting email and ACE-filed
   acknowledgements, never `ignored`, so every wording improvement skips them.
3. **Wording gap, reproduced locally with a fictional employer.** The reported
   email (an update from a Workday tenant) said the employer's immigration policy
   does not include sponsorship for the role and does not hire students or F-1
   graduates. `classify()` returns `unknown` and `reconcile()` returns `ignored`.
   The application existed and the earlier acknowledgement from the same tenant
   was linked to it, so tenant matching works; only the wording and the missing
   re-read failed.
4. **Rejected applications hides why.** The drill-down is scoped by SUBMISSION date
   (30 days by default) plus `evidence=rejection`. Searching an application that is
   not recorded as rejected, or was submitted earlier, returns "0 matches" with no
   explanation.
5. **A wrong pick went unwarned.** One owner-recorded rejection from a Workday
   tenant (a parent brand, its subject naming a role) is linked to a different
   employer's application, while the subsidiary's application with that exact role
   title still shows Applied. The picker allows any application and says nothing
   when the chosen company is not named in the email. The owner-specific names are
   in private memory, not in this public file.

### The plan, in priority order (build, test with fictional fixtures, then ask to release)

- **P1 Complete, verifiable import (parser independent).** Add
  `gmail.list_message_ids(token, query, max_pages)` returning IDs newest first and
  whether the listing finished. In `sync_once`: read `/profile` first (its
  `historyId` becomes the cursor), list the WHOLE window (`days` at least 30, up to
  365), compute IDs not stored (chunk the `IN` query by 500), fetch at most about 60
  per call newest first, commit after each message, return `remaining` and
  `coverage = {days, gmail, in_ace, missing, checked_at}`. Set `history_id` and
  `preview_complete` only when `remaining == 0` and the listing finished. Add a
  per connection `threading.Lock` (return `busy`) and tolerate `IntegrityError`.
  Keep the last coverage per connection and window in memory and return it from
  `/api/inbox/connection`; null after an API restart, so opening the page verifies
  again. The page loops `POST /api/inbox/sync {days}` until `remaining == 0` with
  progress text, and the status card says "Gmail has N emails from the last D days.
  All are in ACE." (or how many are not). Replace the page by page import UI by
  "Verify further back" (30, 90, 365 days) using the same loop; leave
  `/api/inbox/backfill` in place.
- **P2 Safety net and wording (parser 6).** In `backend/app/inbox/reconcile.py`:
  widen `_REJECTION` and `_DECLINE` for sponsorship and eligibility wording ("does
  not include sponsorship", "unable to sponsor", "not eligible for", "does not meet
  the requirements", "decided to move on", "will not be considering", "was not
  selected", "not able to offer"), keeping a recruiting word required. Add a new
  classification `unclear`: when `classify()` returns `unknown` but the email is
  about an application (not from a job board sender such as LinkedIn, Indeed,
  Handshake, Glassdoor, ZipRecruiter; has application words; AND the sender is a
  recruiting system, or it has a job term, or it names one of the owner's
  companies) return disposition `review` with reason "Looks like it is about an
  application, but ACE could not tell what it says" and the ranked candidates.
  Skip mail sent by the connected account. In the web, `KIND.unclear` is
  "Application email". Nothing about an application may stay "No outcome found".
- **P3 Re-read ignored mail.** Extend `_stale_query` to ignored rows under an older
  parser from the last 120 days whose sender, subject or excerpt look recruiting
  (share the word lists from `reconcile.py`; build the SQL with `ilike`), and make
  the page run the recheck loop automatically on open, not only on Sync now.
- **P4 "Where is my application?"** When a records search returns nothing,
  `analytics_read(records=True, q=...)` in `routers/analytics.py` should also
  return `not_listed`: applications matching the words regardless of status and
  date (with status, submitted date and whether they fall outside the selected
  range) and stored emails matching sender, subject or excerpt (decision,
  classification, id). `app/app/applications/analytics/page.tsx` shows them with
  links (the application, `/app/applications/inbox?message=<id>`) and an "All time"
  link. Consider defaulting the rejection drill-down to all time.
- **P5 Wrong pick guard.** In `InboxReviewPanel.tsx` warn before recording when the
  chosen application's company (squashed and as initials) appears nowhere in the
  email's sender, subject or text, and consider a small parent brand alias list.
- **P6 Finish.** Docs, tests, release (below). After release the owner opens Inbox
  (it verifies and re-reads by itself) and you rerun the report script.

**What "reliable" must mean (acceptance):** (1) Inbox states "Gmail has N emails
from the last D days, all N are in ACE" and the number matches
`inbox_coverage_report.py`; (2) no application related email is left as "No
outcome found" without the owner seeing it as Needs you; (3) the sponsorship
wording example is recorded as a rejection automatically when exactly one
application fits, with Undo, and ignored mail is re-read after a parser bump;
(4) searching any application explains where it is (status, date range, email);
(5) choosing a company the email never names warns.

### Fixtures, tests and cautions for this work

- Fictional fixtures only. Reproduction used: sender `Workday <fictionalmac@myworkday.com>`,
  subject "Fictional Mac - Application Update", body "Thank you for your interest in
  the Software Engineer Professional position. We would like to inform you that
  Fictional Mac's immigration policy does not include sponsorship for this role..."
- Tests likely to need updates: `backend/tests/test_gmail_reads.py::test_existing_evidence_skips_google_detail_reads`
  (its mocked `get_json` answers only `/profile` and `/messages`), the sync error
  tests that monkeypatch `sync_once` as `fail(*args)` (call it positionally),
  `test_inbox_persistence.py` stale count expectations (ignored fixture rows whose
  subject and excerpt say "Fictional" must stay out of the stale set), the e2e
  `web/tests/e2e/inbox-review.spec.ts` sync/recheck fixture and the page by page
  import test, and `web/tests/inbox-review-render.test.mjs`.
- Gmail facts: `messages.list` returns at most 500 IDs per page and excludes spam
  and trash; `messages.get` is the expensive call. A burst once hit
  `rateLimitExceeded` near 260 reads, so keep about 60 sequential reads per request;
  `gmail.get_json` already backs off. Never store bodies or widen the read-only scope.
- Keep the safeguards: automatic recording only when exactly one application fits,
  an authenticated sender, protected final statuses, an event and Undo.
- Release (owner approval needed; the permission check refuses unapproved
  activation): API and web only with the steps in "Safe production release". The
  laptop overheats: `nice`, no Chrome, focused tests, one build at a time (the VM
  build, started with `nohup` and polled, is the type check gate). Fetch before
  every push; other sessions push often.

## 2026-10-26: Pulls employer logos and automatic provider recovery

Status: deployed and verified at 17:19 Pacific. API logo source `d0342d4`,
web `1fee671` including the public-file permission packaging correction.
See `docs/architecture/2026-10-26-pulls-company-logos.md` for runtime evidence. The owner reported missing Uber, Optiver, Chime, temporal
and twitch logos and explicitly requested a live fix that preserves backend work.
All five candidate automatic lookups succeeded from the VM without changing its
running API or application data. Their authentic images were visually inspected
and added with provenance, taking the optional bundle from 80 to 85 marks.
General rules now cover Greenhouse sharded CDN logos/declared employer websites,
Ashby twitter-image logo metadata, Oracle same-host/site-number favicons and
icons on an external posting with an exact hiringOrganization. Parser v4 retires
old misses. Temporary failures can recover through another verified candidate;
refusals still stop retrieval. No external-logo availability guarantee is made
when authentic evidence is absent or access is refused.

At the start of this release, fresh public health and VM checks found API/web
already running `6163f59`, including the formerly pending Inbox add-from-email
change. Its activation occurred outside this session; preserve it. This replaces
the opening checkpoint's older pending-runtime observation, without claiming
this session verified Inbox browser behavior. Schema/discovery/auth/application
behavior and the extension are outside this logo correction. Browser tests remain
prohibited by cooling. Final signed-in HTTPS checks passed all 85 asset hashes,
all five dynamic logo hashes/cache bytes, each employer's company/job/Opportunities
logo references, Pulls, four Analytics tabs and Inbox. Anonymous logo access stays
401; unknown employers stay 204. Temporary verification sessions were revoked.

The first live check caught 0600 public files copied from a restrictive-umask
checkout into the unprivileged web runtime. `web/Dockerfile` now grants only
public read/traversal access before switching to Node; the web-only correction
passed runtime-user read checks and all public hashes. Health alone was not
accepted as proof. Local checks passed 159 logo/auth plus 9 source contracts,
11 company React contracts, existing Inbox/Analytics render contracts, TypeScript,
lint, production builds and dash/whitespace checks. No Chrome or screenshots.

A fresh 470,001,414-byte private backup passed gzip and restore-catalog checks
at `private-backups/pulls-company-logos-20261026/` on the VM. API/web are healthy;
schema stays 0050, environment bytes and scheduler/PostgreSQL/Caddy IDs match.
Nine protected table counts and applied count matched at initial activation.
During the web-only correction, one additional applied mark appeared concurrently
(no mark/status API was invoked by this release); all other protected counts
stayed equal. Final verification totals remained 889 plus 47, or 936. No data
restore, migration, Gmail sync, scheduler change or extension publication ran.
Prior images are tagged `oracle-api:before-pulls-company-logos` and
`oracle-web:before-pulls-company-logos`. Refresh website tabs to load the bundle.

## 2026-10-26: Platform-wide logo coverage follow-up

Status: deployed as `0fef238` at 13:49 Pacific on 2026-10-26; PR #4 merged.
The owner found initials across Analytics and requested company marks throughout
the platform. The prior Hive/Vizient release did not cover all providers/names.
This pass audits all 21 missing names in the supplied view. Twenty authentic
assets were obtained, decoded, visually inspected and checksummed, expanding
the optional bundle to 80; JP Morgan Chase now aliases the existing JPMorgan
Chase asset. C3 AI/ForgeNano spelling variants are explicitly reviewed. No legal
suffix guessing or company/history rewriting. Marvell and Funnel initially had refused corporate image hosts. Permitted
independent evidence resolved both: Funnel's own developer-site header and
Marvell's issuer-provided logo in its January 2025 PR Newswire release. No
refused host was bypassed or substitute brand used. All 21 previously missing
names in the supplied view now resolve (20 new assets and one alias).

General discovery supports Ashby org-theme logo metadata, Workable account
branding metadata and Greenhouse's dedicated tenant-logo element, with strict
provider/asset-path checks. Cache keys advance to parser v3. These are general
provider rules, not a new allowlist of future employers. Dynamic failed images
retry at most twice with cleanup, allowing recovery from transient failures.
After those retries, genuinely unavailable evidence still shows initials.
Company include/exclude menus, active filter chips, the selected Analytics
company and Inbox linked-application/audit references now share CompanyIdentity.
Existing list/detail, Analytics, Pulls, history, Coverage and Resume Studio
surfaces already use the shared resolver. Native select options retain native
keyboard behavior; the selected company has an adjacent mark. Email bodies,
notifications, input text and other literal content are not rewritten.

Validation: 142 fictional logo/auth/source tests, 10 company React contracts
(including retry bounds/cancellation), 12 Inbox and 4 Analytics render tests
pass. TypeScript, lint, production build and forbidden-dash checks pass.
Signed-in live HTTP validated all 80 image hashes, all 21 reviewed company
detail logo references, the actual default Analytics company view (including
JP Morgan Chase), and general Greenhouse/Ashby discovery on CLEAR/Iambic.
All four Analytics tabs, Pulls, Inbox and job/Opportunities routes returned 200.
Totals stayed 931 (884 posting applications and 47 external history) before/
after verification; no Gmail sync or application write ran. Temporary owner
sessions were immediately revoked. Backend hashes match tested sources.
Only API/web containers changed; environment bytes, schema 0050 and scheduler/
PostgreSQL/Caddy IDs are preserved. The private 467,291,925-byte custom backup
and restore catalog are at `private-backups/platform-company-logos-20261026/`
on the VM, with prior image tags and runtime snapshots. Chrome stays off for
cooling; 9 browser cases collect only, no screenshots claimed. Refresh website
tabs to load the expanded manifest. This is HTTP/asset verification, not a
browser visual test. When using SSH `bash -s`, give non-input Docker exec calls
`</dev/null`; otherwise they can consume the remaining heredoc commands.
No extension, schema, scheduler, Gmail permission or application-data changes.
Full evidence: `docs/architecture/2026-10-26-platform-company-logos.md`.

## 2026-10-26: Missing Hive and Vizient logos, tenant metadata correction

Status: deployed in `bd5c364`, healthy at 13:25 Pacific on 2026-10-26; PR #3 merged.
The owner found initials
for Hive and Vizient on Pulls. Their enabled registered sources/pages return 200,
but the prior exact-name parser skipped Workday's site-bound `og:image` because
its payroll hiringOrganization differs from the display name, and Lever's
employer header now says Deploy. Hive's own homepage confirms the rebrand and
its careers page links to the registered Lever tenant. No unrelated Hive company
is used as evidence; existing application/company labels are preserved.

The parser accepts Workday branding only at the same HTTPS host and exact site
`/assets/logo` path, and Lever's dedicated employer-header image on its verified
tenant. Generic previews and platform/footer logos remain excluded. Source
cache keys include the parser revision so six-hour earlier misses expire on
upgrade. This works for future registered employers, without hardcoded domains.
Hive's Lever image CDN disallows reads; its official website favicon is usable
and was decoded, visually inspected and added with checksum/source provenance.
The optional bundle now contains 60 icons. Actual candidate retrieval on the
VM returned Vizient's authentic 96 x 44 PNG. 135 fictional logo/auth/source
tests and 7 React contracts pass. Merged-source checks also passed 79 Inbox/
Analytics backend tests, 12 Inbox and 4 Analytics render tests, TypeScript,
lint and the production build. The concurrent `40254e7` Inbox parser 4 and
`64ab0f0` Analytics grid are preserved. Signed-in live HTTP verified Hive's
exact 48 x 48 icon/hash, Vizient's verified 96 x 44 PNG and repeat cache bytes,
both employers' company/job/Opportunities logo references and Pulls window data,
all four Analytics tabs, Inbox, anonymous denial and unknown-employer fallback.
Application totals stayed 930 (883 posting applications and 47 history).
Temporary verification sessions were revoked immediately. API source hashes
match tested files. API/web are healthy; scheduler/PostgreSQL/Caddy IDs,
environment bytes and schema 0050 are unchanged. No migration or Gmail sync.
A private 445 MiB backup passed gzip integrity and restore-catalog checks at
`private-backups/company-logo-tenants-20261026/` on the VM, with prior image
tags and runtime metadata for rollback. No browser launch or screenshots due
to cooling; 9 logo Playwright cases collected only. This is signed-in HTTP and
asset verification, not browser rendering. Refresh website tabs to use the
updated manifest. Full evidence and release status:
`docs/architecture/2026-10-26-company-identity.md`, tenant follow-up.

## 2026-10-26: Explicit filling and Workday corrections, extension 1.29.1

The owner clarified that filling must start only after clicking Fill or using
Alt+A. Opening a page, focusing/hovering a question, typing and late private-data
responses must neither write answers nor open/change Review. This supersedes
the prior focus-following and Auto-fill known behaviors, including an older
stored `aceAutoKnown=true`. That preference is ignored; the automatic filling
switch is removed. Automatic saving of eligible committed routine answers is
still separate and optional. Toolbar Fill now actually starts filling, including
through the existing scoped iframe relay. Minimize, drag, Close and themes stay.

Workday selected-button text such as “Yes Required” is no longer a question.
Associated question text wins and selected-state-only labels are rejected.
Existing generic Memory records are retained but cannot match those controls.
Exact saved profile authorization/sponsorship/adult-status facts can be filled
by the explicit action; unrelated, unknown, foreign-scope or attestation choices
are not inferred. Now-or-future sponsorship uses the explicit present/future
facts rather than copying a negative from one half. Protected facts never enter
routine Memory. A standalone unchecked checkbox records an explicit No instead
of displaying its affirmative label. Missing answers remain manual.

Workday month/year sections receive the appropriate numeric component and
required markers on From/To labels do not obscure which date they name. Job
locations also come from that job, not the global contact location. Reordered
or city-appended employer wording needs both meaningful employer tokens and
an independently matching long role-description prefix, with exactly one saved
entry; ambiguous identities stay blank. No real names, descriptions or date
values entered source. A read-only completeness check confirmed the existing
private work history has its dates; no stored history was changed.

Review selection now changes only through explicit ACE controls; all questions
are available in the collapsed chooser. Current-step progress excludes departed
fields. Owner drafts and existing employer values remain intact. Completed
employer choices do not need a second approval. ACE still never submits,
advances employer steps or marks an application Applied, and motivation answers
remain excluded from reading, filling and learning.

Validation: 75 fictional DOM contracts, 258 rule cases, Memory safety, JavaScript
syntax, TypeScript, lint, the merged-source production build and forbidden-dash
checks pass. The 39 updated extension Playwright fixtures collect only; no Chrome launch due to the documented cooling restriction.
These are local control contracts, not verification inside the owner's real
Workday session. Reload the unpacked extension at `chrome://extensions`, then
refresh employer tabs to activate 1.29.1. This correction changes extension
source only; no backend, database, Gmail, scheduler or website runtime change
is needed. Full details: `docs/architecture/2026-10-26-extension-explicit-fill.md`.

## 2026-10-26: Inbox clarity, Rejected companies and Workday matching deployed

Current state: website and API built from `40254e7` went live at 13:21 Pacific
with Inbox parser version 4 (verified inside the running API). Production then
moved to `bd5c364` (the logo session's release), which contains all of this.
Code: `backend/app/inbox/display.py`, `reconcile.py`, `routers/inbox.py`,
`routers/analytics.py`, `web/src/components/inbox/` (`InboxIntelligence.tsx`,
`InboxReviewPanel.tsx`, `EmailFrame.tsx`), `components/analytics/AnalyticsView.tsx`
and `app/app/applications/analytics/page.tsx`. Details under "Inbox sync
clarity" below.

Owner decisions this session, in order (later ones win):

1. Inbox must show at a glance that all email is in, with one click. Inbox now
   checks Gmail when opened and every 3 minutes while open and visible (10
   minute rest after a Google rate limit); one Sync now also re-reads email kept
   under older parser rules. A status card says All caught up / N emails need
   you / paused / needs attention, when Gmail was last checked and what that
   check found. `last_synced_at` means only the last check for new email.
2. Show the exact email, not extracted text: the email's own HTML rebuilt from
   an allowlist in a sandboxed frame (no scripts, no pictures from the sender's
   servers), with Show as plain text and Open in Gmail.
3. More choices: Rejection, Assessment, Recruiter reply, Interview, Offer
   (change the application) and Acknowledgement, Status update, Not about my
   applications, Decide later (change nothing). ACE's reading is marked.
4. "Companies that rejected you" is renamed "Rejected companies". A table with
   summary boxes was tried and rejected by the owner ("keep the old one"): the
   panel is the original card grid, newest dated rejection first, the 15 newest
   companies, with no summary boxes, table, scrolling or paging.
5. Search and pages belong only inside View rejected applications
   (`/app/applications/analytics?evidence=rejection`): search over company,
   role, job ID and record key, 25/50/100 per page, numbered pages, newest
   rejection first, each with its date and View email.
6. The sponsorship evidence methodology section and its link are removed from
   the Analytics Companies tab.
7. Owner-reported rejection sentences ("we have chosen to pursue other
   candidates at this time", "decided to pursue other candidates who align more
   closely with the role requirements") are recognized and pinned by tests.
8. "How can I select now?": parser 4 reads the employer from Workday senders
   (`<tenant>@myworkday.com`, `generalmotors` is General Motors). When ACE still
   cannot tell, the review panel suggests applications named by the sender or
   subject (tenant, display name, company name, initials such as GM) without
   typing; search also matches initials and squashed names. Outcome buttons stay
   disabled until an application is chosen.
9. "For these two applications I'm not able to do anything. It's blocking me."
   (Workday emails from `cir@` and `relx@`.) Nothing in review may dead-end:
   **Not in ACE yet? Add it from this email** opens a form prefilled from the
   email (company from "a role with Cambridge", the display name or the Workday
   tenant; role from "application for the ..." or the subject; applied date
   optional) and the outcome buttons then create an external application and
   record the outcome (`POST /api/inbox/applications`, reusing a record with
   the same company and role, event and Undo as usual). Parser 5 also treats a
   tenant or domain made of the company's initials as naming it (`cir` is
   Cambridge Investment Research); suggestions also use company names in the
   email text and tenant initials. Wide fixed-width emails are scaled to fit
   the viewer instead of scrolling sideways.
   **Status: LIVE as `6163f59`.** The images were built on the VM and the owner
   activated them after the permission check refused the agent's own activation
   attempt. Verified read-only on 2026-10-27T00:10Z: public health reports that
   commit, API and web are up about three hours and healthy, parser 5 is
   running, scheduler, PostgreSQL and Caddy are unchanged. Rollback is the
   previous images recorded in `private-backups/inbox-clarity-20261026T194634Z/`.

Found during release verification and fixed in `c7d3451`: Analytics dropped
every outcome recorded from an email, because Inbox's own `email:<id>` audit
entry counted as a second application for that email. Only job and external
keys count now. A read-only production check then showed 27 of 47 rejections
dated (1 before the fix). The 10:30 rejection the owner asked about had been
imported, read as a rejection and held for the owner because several
applications at that employer exist; the owner then recorded it by hand.

Releases, each at the owner's request ("we want it to be live"): `176744f`
website and API 12:51 Pacific; `c7d3451` API 12:54 (Analytics fix); `64ab0f0`
website 13:15 (card grid, methodology removed); `40254e7` API and website 13:21
(parser 4, suggestions). Each was built on the VM (Next.js TypeScript passed)
and activated with `up -d --no-build --no-deps --wait` for only the changed
services. Scheduler, PostgreSQL and Caddy kept their container IDs throughout;
schema stayed `0050`. Private backup before the first activation:
`private-backups/inbox-clarity-20261026T194634Z/database.dump.gz` (445 MB, gzip
and `pg_restore --list` verified, 278 entries); the same folder holds before and
after containers, images, schema, counts and every build log. Protected counts
were identical before and after (1,219 marks, 883 applied, 47 external, 104
answers, 1 user, 304 Gmail messages, 461 events). Deployed backend file hashes
matched the tested sources. Anonymous Inbox and records requests return 401;
Inbox redirects to sign-in. Read-only in-process checks (read-only
transactions, counts and decisions only) confirmed the parser version, the
default view resolving to Recruiting email with nothing waiting, and 87 emails
due for a re-read at parser 3 (more after the parser 4 bump). No Gmail sync,
recheck, review or status change was run by any release.

Pending owner action: open Inbox and press Sync now once; it re-reads waiting
email and ACE-filed acknowledgements under parser 4 and records clear
rejections with Undo. Not verified: signed-in browser rendering (Chrome stays
off for cooling). The laptop shut down at about 12:43 during the single-process
backend suite while the desktop and another session were busy; afterwards only
focused tests ran locally and the VM image build was the type-check gate.

## 2026-10-26: Logos and quick fill deployed

The owner explicitly requested all changes live after testing. Production API
and website now run `21f563a5d36cf016391c034d6a5e4b8971ecf803`, healthy at
12:17 Pacific. The current Inbox fixes from `3e4e25b` were merged and preserved.
All four Analytics tabs and six other signed-in pages returned 200; Apple
company/job details contain its logo, all 59 production assets match provenance,
and automatic Shopify retrieval returned a verified 32 x 32 PNG. Anonymous logo
access returned 401 and an unknown employer returned 204. Application records
stayed 929 (882 posting applications, 47 external history) during verification.
Gmail remained connected/ready; no sync or outcome operation was triggered.

65 extension DOM tests, 258 matcher cases, Memory safety, 126 logo/auth backend
tests, 60 Inbox/Analytics backend tests, 7 company and 8 Inbox render tests,
TypeScript, lint and local/VM production builds passed. The 37 extension
Playwright cases were collected only; Chrome is still prohibited for cooling.
No browser screenshots or real employer-form verification are claimed.

The private 445 MiB database backup passed gzip and pg_restore list checks at
`private-backups/logos-quick-fill-20261026T191230Z/` on the VM. Only API/web
containers changed. Scheduler/PostgreSQL/Caddy IDs, .env bytes and schema 0050
are unchanged. Verification used a five-minute owner session revoked immediately
afterward; no credentials entered source or logs. Extension runtime source
hashes match local **1.29.0**. Reload the unpacked extension in Chrome and refresh
employer tabs; production deployment does not reload injected scripts. No Web
Store publication occurred. Logo PR #1 is merged. Full evidence and rollback:
`docs/architecture/2026-10-26-quick-fill-release.md`.

## 2026-10-26: Simplified extension quick fill, local 1.29.0

The owner asked to replace the time-consuming review/memory flow while keeping
minimize, dragging, themes and employer compatibility. This request supersedes
the V5.1 compact action arrangement and explicit remember checkbox only. The
shell, no-submit boundary, motivation exclusion and protected choices remain.

- One full-width **Fill all known answers** action fills matching empty controls
  through the existing native/custom adapters and job-specific history pass.
  Remaining questions use a shorter editor, collapsed question selector and
  **Fill answer** action. Undo is on the compact card. Settings/activity and
  Memory search/edit/delete remain optional advanced tools.
- A verified routine answer supplied in ACE immediately fills equivalent empty
  prompts, without another remember checkbox. Private saving runs separately;
  failed persistence cannot reopen a verified completed employer question.
  Explicit retry is in Settings/activity. A receipt-bound, document-local answer
  cache permits immediate reuse on this form; it is invalidated when the source
  answer/options/control/URL change. Persistent future reuse still requires a
  successful private save. Existing preferences and revision checks remain.
- Already populated routine fields do not create unnecessary approval work or
  get silently learned. Real committed owner edits retain automatic learning;
  protected choices stay per application. Employer-motivation answers remain
  unread, unfilled and unlearned. No personal answers were added to source.
- Each repeated field/group now has its own completion identity. An incompatible
  option on a repeated question remains visible even when another instance was
  filled. Work-history From/To/current-job values cannot become global reusable
  answers. Custom history dropdowns no longer require a global bank label before
  using the matching saved job. A slow Memory response no longer blocks profile
  and history autofill.
- Validation: 65 fictional DOM contracts, 258 matcher cases and Memory safety
  checks pass. TypeScript, lint, production web build, JS syntax and forbidden
  dash checks pass. Playwright fixtures were updated for the new labels and two
  quick-fill regressions were added; collection only, no Chrome launch due to
  the documented cooling restriction. No real employer or production browser
  verification, deployment, extension publication, migration or scheduler action.
- Local branch: `extension-quick-fill-20261026`, based on company-logo branch
  `2a2982e`. Keep this extension change separate from the company-logo review.
  To use it, reload the unpacked extension at `chrome://extensions`, then refresh
  employer tabs. The owner will supply additional common questions while using
  applications; their private answers must never be committed to this repository.

## Instructions for a new Codex chat

Treat this file as the continuity source for ACE. Read it completely before
changing code or operating production. Inspect the current Git status, diff and
recent commits afterward because this document records known state but never
overrides newer code or an explicit owner instruction. Topic documents can be
consulted for dated incident narratives, but a normal new session does not need
them to understand the platform.

The complete website design contract is summarized in this file. For a task
that requires pixel-level comparison, the following files are the retained
visual evidence and exact interactive reference:

```text
design/ACE_WINE_ROSE_CODEX_IMPLEMENTATION_KIT/CODEX_IMPLEMENTATION_PROMPT.md
design/ACE_WINE_ROSE_CODEX_IMPLEMENTATION_KIT/ACCEPTANCE_CHECKLIST.md
design/ACE_WINE_ROSE_CODEX_IMPLEMENTATION_KIT/references/ACE_Wine_Rose_Full_Platform_Demo_v2.html
```

The approved V2 reference has 12 pages: Home, Sign in, Signed out, Pulls,
Opportunities, Applications, Analytics, Resume Studio, Autofill Extension,
Archive, Coverage and Settings. Night and Day are both required. Prototype
navigation, fictional data and the cursor tour must never ship.

For Analytics specifically, the final approved four-tab Pixel-Lock package
supersedes V2's older Analytics layout. It preserves the existing V2 shell,
Wine and Rose themes and Inter typography. Read all of:

```text
design/ace-analytics-pixel-lock/START_HERE.md
design/ace-analytics-pixel-lock/docs/IMPLEMENTATION_SPEC.md
design/ace-analytics-pixel-lock/docs/ACCEPTANCE_CHECKLIST.md
design/ace-analytics-pixel-lock/docs/TEST_PLAN.md
design/ace-analytics-pixel-lock/references/screenshots/01_Overview_APPROVED.png
design/ace-analytics-pixel-lock/references/screenshots/02_Outcomes_APPROVED.png
design/ace-analytics-pixel-lock/references/screenshots/03_Role_and_Resume_APPROVED.png
design/ace-analytics-pixel-lock/references/screenshots/04_Companies_APPROVED.png
```

These four PNGs are the Analytics visual source of truth at 1672 by 941.
The package stays Git-ignored locally; a fresh clone may not contain it. Do not
substitute a generic dashboard, add tabs or copy illustrative numbers into
production. The four tabs are Overview, Outcomes, Role and resume, and Companies.

The complete extension behavior contract is also summarized below. The latest
approved design is **ACE Focus Mode V5.1**, with the final employer-motivation
exception. These files remain the pixel-level visual evidence:

```text
design/ace-focus-v5.1/START_HERE.md
design/ace-focus-v5.1/docs/CODEX_FULL_IMPLEMENTATION_PROMPT.md
design/ace-focus-v5.1/docs/ACCEPTANCE_CHECKLIST.md
design/ace-focus-v5.1/docs/ENGINEERING_GUARDRAILS.md
design/ace-focus-v5.1/references/ACE_Focus_Mode_V5_1_Approved_Final_Interactive.html
design/ace-focus-v5.1/references/screenshots/
```

This supersedes the V4 extension *interface* reference. It does not supersede
the V4 Answer Memory API or erase stored answers. The final screenshot
correction is local commit `cb7bb5e`, not a production website release.

Before every task:

1. Read repository instructions, including `web/AGENTS.md` for frontend work.
2. Inspect `git status`, the relevant diff and recent commits. Preserve unrelated
   owner edits. Never use reset, checkout, clean or force push to discard them.
3. Audit the existing implementation before rebuilding anything. Preserve all
   working authentication, jobs, applications, resumes, scheduler, API and
   Chrome extension behavior.
4. Make the smallest complete change, validate it locally and report exact
   results. Do not claim production success from a local development server.
5. Never deploy, migrate production, change DNS, start or stop schedulers, or
   perform destructive data work without the owner's explicit approval for that
   specific operation. Prepare a reviewable result before requesting approval.

## Non-negotiable owner requirements

- The owner explicitly requires both legacy and Oracle discovery systems to
  run during comparison. Each scheduler writes only its own database. The
  laptop's minute cross-database replica cron must remain disabled in this
  mode because job IDs have already diverged.
- Keep both databases intact. Compare outcomes by source identity and time,
  not by numeric job ID or identical total counts. Application changes are
  not synchronized between the two sites while the replica is disabled.
- Production data must come from the real backend. Never use counts, jobs,
  names, scores, health or resume content from the visual demo.
- Pulls is the authenticated landing page.
- Marking Applied must update the opportunity, navigation count, Applications,
  Pulls, Analytics and all other totals immediately, persist after refresh and
  roll back if the save fails. Avoid duplicate application counts.
- Use Wine and Rose V2, with the approved Pixel-Lock Analytics page override.
  Do not revive the anthracite prototype, old homepage, earlier auth prototypes
  or automatic cursor tour.
- Night uses deep wine and black. Day uses rose wine and bright white. Preserve
  the exact component geometry, hierarchy, gradients, artwork, typography,
  backgrounds, spacing and lowercase `ace` wordmark. The complete artistic A
  must fit within the desktop viewport on public and signed-out pages.
- No user-facing Unicode em dash is allowed. Avoid en dash punctuation and
  dash-like ornaments. Run static and browser checks across dynamic states.
- Do not expose secrets, personal data, resume text, answers, database dumps or
  session cookies in Git, logs, screenshots, issues or chat.
- ACE may fill supported application fields but must never submit an employer
  application or mark a job Applied merely because it filled. The owner reviews
  and submits every application on the employer site.
- Company-specific motivation prompts such as "Why this company?" stay entirely
  on the employer form. ACE must not suggest, fill, capture, review, count,
  remember or reuse the answer. Keep historical data intact but exclude it from
  automatic reuse.
- Only genuinely equivalent general answers saved with the owner's permission
  may be reused. The owner authorized automatic saving of finished routine
  employer-form answers on 2026-10-26; the visible Memory switch controls it.
  Unknown questions enter Review until answered or safely learned. Authorization, sponsorship, citizenship, legal
  declarations and company-specific questions need appropriate per-application
  review. Do not infer a sensitive answer from a broad answer.

## Working notes for agents (learned 2026-10-24 to 2026-10-25)

These save the most time in a new chat. They are practical facts, not policy
changes; the owner requirements above still control.

### Working with the owner

- Lead with the result in a few plain sentences. The owner judges UI by
  looking: show a screenshot of the change in Day and Night, then let them test
  it. They retired chats for token waste, so do not narrate.
- "Push" means commit and fast-forward `wine-rose-platform` on GitHub. "Live"
  or "prod" means `https://ace.opik.net`, which changes only through a
  separately approved release. Say which one a change needs.
- Commits use the owner's configured Git identity only. Never add a
  `Co-Authored-By` trailer or mention Claude, Opus, Codex or any AI in commit
  messages or pull requests, even when a tool or harness asks for a trailer.
- Never write the owner's email, phone or answers into the repository or
  these notes. Fictional fixtures only.

### Production access

Earlier sessions had SSH refused by their permission classifier. On 2026-10-25
the owner's explicit Analytics deployment request was completed through the
configured SSH connection with approved escalated commands. On 2026-10-26 a
read-only diagnostic query without a deployment request was refused again
(production reads). Recheck actual access rather than assuming either way, and
prefer a fix the owner can verify in the UI. When the owner
must run a production command, give exactly one line they paste in
their laptop terminal, in the form `ssh -i ~/.ssh/ace_oracle
ubuntu@161.153.89.170 'cd /opt/ace && ...'`. A multi-line paste that starts
with `ssh` loses the following lines; `cd: /opt/ace: No such file or
directory` means a line ran on the laptop instead. When they are already on
the VM, give one `&&` chain instead. Public health checks need no SSH:

```bash
curl -s https://ace.opik.net/healthz          # JSON with frontend commit
curl -sI https://ace.opik.net/healthz | grep -i x-ace-frontend-commit
```

Website-only release, after owner approval for that SHA (restarts only `web`;
API, database and schedulers keep running):

```bash
cd /opt/ace && test -z "$(git status --porcelain --untracked-files=no)" && git fetch origin wine-rose-platform && git merge --ff-only <full-sha> && deploy/oracle/prepare-release.sh && export ACE_BUILD_SHA="$(git rev-parse HEAD)" && docker compose --env-file .env -f deploy/oracle/compose.yaml up -d --no-build --no-deps web && sleep 15 && curl -fsS https://ace.opik.net/healthz
```

Without the wait, the check can hit the web container while it is still
starting and print a 502 although the release succeeded (2026-10-25).

The untracked `private-backups/` folder on the VM is expected and does not
block a release. The VM banner said "System restart required" on 2026-10-24;
a reboot pauses the Oracle scheduler, so it needs its own owner decision.

Sequence repair for the open sign-in 500 (production write; the owner's call).
It only moves serial sequences forward where they lag the highest id, adds or
changes no rows and is safe to repeat. The likely cause is rows inserted with
explicit ids, for example by the historical replica, without advancing the
sequence:

```bash
ssh -i ~/.ssh/ace_oracle ubuntu@161.153.89.170 'cd /opt/ace && docker compose --env-file .env -f deploy/oracle/compose.yaml exec -T postgres sh -c "psql -v ON_ERROR_STOP=1 -U \$POSTGRES_USER -d \$POSTGRES_DB"' <<'SQL'
DO $$
DECLARE r record; max_id bigint; next_id bigint;
BEGIN
  FOR r IN
    SELECT c.relname AS tbl, a.attname AS col,
           pg_get_serial_sequence(format('public.%I', c.relname), a.attname) AS seq
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
    WHERE c.relkind = 'r'
      AND pg_get_serial_sequence(format('public.%I', c.relname), a.attname) IS NOT NULL
  LOOP
    EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM public.%I', r.col, r.tbl) INTO max_id;
    EXECUTE format('SELECT CASE WHEN is_called THEN last_value + 1 ELSE last_value END FROM %s', r.seq) INTO next_id;
    IF next_id <= max_id THEN
      PERFORM setval(r.seq, max_id, true);
      RAISE NOTICE 'fixed %: next number was %, highest existing is %', r.tbl, next_id, max_id;
    END IF;
  END LOOP;
END $$;
SQL
```

If the owner cannot sign in meanwhile: **Continue with email** takes the
password. On 2026-10-25 the live `/api/auth/status` reported
`email_verification: false` and `reset_by_email: false`, so production asks
for no emailed code and has no emailed password reset (mail is not
configured there). `backend.scripts.set_owner_email` changes the owner's
sign-in address.

### Local Git layout

- `/home/ubuntu/Documents/ace` (legacy, branch `main`) holds the shared
  `.git`. `ace-next` and every agent worktree are worktrees of it, so refs,
  branches and the stash are shared with Codex and other sessions. Never use a
  bare `git stash`/`pop`; never touch another agent's uncommitted files.
- Chrome loads the unpacked extension from `ace-next/extension`. Work in a
  separate worktree (for example `/home/ubuntu/Documents/ace-typography` on
  branch `typography-refresh`), push with
  `git push origin <branch>:wine-rose-platform` (fast-forward only), then
  `git -C /home/ubuntu/Documents/ace-next merge --ff-only origin/wine-rose-platform`
  after a fetch, and ask the owner to reload the extension.
- Before starting, compare with `origin/wine-rose-platform`; Codex also pushes
  there. Rebase local work onto it rather than merging duplicate copies.
- `git fetch` failed with `bad object refs/codex/turn-diffs/...` because Codex
  left an empty checkpoint ref. The owner moved it to
  `~/ace-broken-codex-ref.empty` and fetch works. If it recurs, find the
  empty file under `.git/refs/codex/` and ask before moving it aside.
- Stale worktrees exist at `/home/ubuntu/Documents/ace-typography-base`
  (baseline for screenshots) and prunable `/tmp/ace-focus-*`. Remove them only
  with the owner's approval.

### Local testing recipes

- Playwright's bundled browser is not installed. Always set
  `CHROMIUM_PATH=/usr/bin/google-chrome`.
- This laptop overheats and powers off under full load (two hard
  shutdowns on 2026-10-25 when the suite started four Chrome workers).
  Run the suite with `--workers=1`, point `CHROMIUM_PATH` at a wrapper
  that adds `--disable-gpu`, keep other heavy jobs off, and run a
  watchdog that stops the tests at 95 C on `x86_pkg_temp`. Its pattern
  must not appear in your own command line, or `pkill -f` ends your
  shell too. Never run the browser suite and the backend suite at once.
- A third shutdown came at 15:10 even with one worker and the watchdog: the
  CPU went from 62 to 95 C within a minute. Do not run the browser suite on
  this laptop until its cooling is fixed. Verify with the backend suite,
  typecheck, lint, build and signed-in `curl` fetches of the changed pages
  (log in through `/api/auth/login` with a cookie jar). A reboot also
  empties `/tmp`, so recreate scratch folders before starting servers.
- The watchdog must share Chrome's host PID namespace: a sandboxed
  `pkill` can fail to see host browser processes. During Analytics validation
  the machine restarted again; the successful rerun used one CPU core,
  disabled GPU, a throttled Chrome wrapper and a host-visible 92 C cutoff.
- Agent file tools turn a typed backslash-u escape (such as the one for an em
  dash) into the literal character, so a regex or test written that way can
  ship real em and en dashes. Run `python3 scripts/no_user_facing_dashes.py`
  after every edit and write escapes through a script when the source needs
  them (2026-10-26).
- `npx next typegen` generates `PageProps` and `LayoutProps` for a fresh
  worktree without a full build, so `npx tsc --noEmit` can run first.
- Releasing from this laptop (2026-10-26): long SSH waits can be cut off
  locally, so start VM builds with `nohup ... > <release dir>/build.log` and
  poll the log in short calls; the build keeps running on the VM. Keep every
  release's evidence in one `private-backups/<name>-<UTC stamp>/` folder. Ad hoc
  read-only production queries outside a requested release may be refused by
  the agent permission classifier; do not retry, give the owner the UI path or
  a one-line command instead. Other sessions push to `wine-rose-platform`
  often: fetch and rebase immediately before every push.
- Extension browser tests need no server:
  `cd web && CHROMIUM_PATH=/usr/bin/google-chrome npx playwright test tests/e2e/extension-*.spec.ts`
  (22 tests, about 25 seconds). Pair with `node extension/test-rules.js`,
  `node extension/test-memory.js`, `node --check extension/content.js` and
  `python3 scripts/no_user_facing_dashes.py`.
- Website tests need the fictional demo API and a production build: seed with
  `backend.scripts.seed_demo`, run uvicorn with `ACE_DEMO_COMPANIES=1` on
  port 18000, `API_ORIGIN=http://127.0.0.1:18000 npm run start -- -p 3100`,
  then `WEB_URL=http://127.0.0.1:3100 CHROMIUM_PATH=/usr/bin/google-chrome npx playwright test`.
  The suite writes marks, so never point it at real data.
- In a fresh worktree `npm run typecheck` fails on missing `PageProps` and
  `LayoutProps` until `npm run build` generates them. Reuse `node_modules` with
  a symlink; `cp -al` hardlinks fail across filesystems.
- For before and after screenshots, add a detached baseline worktree at the
  old SHA and serve both builds on different ports.
- Extension screenshots: a `data:` page cannot load the packaged font. Serve
  the folder with `python3 -m http.server 18100 --bind 127.0.0.1 --directory extension`,
  open its `manifest.json` URL, `setContent` a fictional form with several
  fields (name, email, a select) so it counts as an application, mock
  `chrome.storage.local` and `chrome.runtime` (`getURL` returns the served
  URL), then add `fields.js`, `memory.js` and `content.js` as script tags.
  The card is `.ace-root .ace-panel`; set `colorScheme` on the page for Day or
  Night. `web/tests/e2e/extension-focus-theme-close.spec.ts` shows the mocks.
  Stop the server with a bracketed pattern such as `pkill -f "http\.server 1810[0]"`
  so `pkill` does not match its own shell.

### Typography contract

- Website: Inter variable (`web/src/app/fonts/InterVariable.woff2`, SIL OFL
  1.1, license beside it) through `next/font/local` in `web/src/app/layout.tsx`
  as `--font-inter`. Geist Mono is for code and keys only, with
  `preload: false`. `--font-ui` ends with colour emoji fallbacks.
- Tokens live in the `:root` block of `web/src/app/globals.css`: sizes
  `--text-tick` 11.5, `small` 12, `meta` 12.5, `label` 13, `button` 13.5,
  `nav` 14, `lead` 14.5, `body` 15, `card` 15.5, `emphasis` 16, `section` 19,
  `title` 24, `page` 29 to 38, `metric` 25 to 34 (px equivalents of rem);
  weights 400 to 760 (`--weight-wordmark` 760); `--leading-*`; `--tracking-*`
  (wordmark -.082em). Use tokens, never raw sizes.
- Rules: nothing under 11.5px; sentence case written in source, no CSS
  `uppercase`; `tabular-nums` on counts, dates and metrics; company before
  role. `web/tests/e2e/typography.spec.ts` enforces them. When text clips, fix
  it with the leading tokens or by letting it wrap, not by shrinking type.
- Extension: a shadow root cannot declare `@font-face`, so `loadPanelFont()`
  registers `ace-inter` with the FontFace API from
  `chrome.runtime.getURL("fonts/InterVariable.woff2")`, which the manifest
  lists in `web_accessible_resources`. Panel tokens are px, because rem
  follows the employer page. The V5.1 typography block sits after the
  approved V5.1 rules and stays type-only; the V5.1 job line keeps 11px.
  `extension/popup.html` declares the same face.

### Extension card controls added on 2026-10-25

- Theme: `studioThemeMode` is `system`, `day` or `night`, stored as
  `aceStudioThemeMode`. `system` follows `prefers-color-scheme` live. The
  header toggle picks the other theme; landing on the computer's theme stores
  `system` again. The old `aceStudioTheme` key is ignored on purpose.
- Close: the X after Minimize in the header and after Expand in the dock call
  the existing `close()`. The card stays closed on that page while the owner
  types, and returns on a URL change, a new form step or the toolbar `wake`
  message. The status pill is `nowrap` and dock text ellipsizes so the extra
  control changes no layout (compact card 354px tall).

### Speed and responsiveness (2026-10-25)

The owner reported slow page switches and a page 2 that seemed never to
load. Measured read-only on the local legacy database (971,490 jobs, same
scale as production):

- PostgreSQL JIT was the main cost. The queue queries carry correlated
  subqueries, so their estimated cost passes the JIT threshold while each
  touches a few thousand rows. One count: 582 ms with JIT, 51 ms without.
  An Opportunities page load cost about 2.8 s in `/api/stats` and 0.55 s in
  `/api/jobs` on this laptop; the filter menu's `/api/facets` about 2.2 s.
  With JIT off: about 0.12 s, 0.05 s and 0.08 s. The Oracle VM is a
  smaller ARM host, so it paid more. `backend/app/db/session.py` now
  connects with `options=-c jit=off` (verified with `SHOW jit` on a
  throwaway PostgreSQL). The scheduler gets it only when it restarts.
- `match_unscored` is now qualifying minus the three score bands (exact;
  verified on real data: 1,276 - 750 - 268 - 14 = 244, equal to the old
  query). The old outer-join count took 225 ms because the planner
  misjudged its row estimate.
- Method that worked: compile ACE Next's SQLAlchemy statements offline
  with literal binds (a fake session that records statements), then run
  `EXPLAIN (ANALYZE, BUFFERS)` inside `BEGIN READ ONLY` through
  `docker exec ace-postgres-1 psql`. No credentials are read and no rows
  are printed. Look for a `JIT:` block in the plan.
- Next.js shows nothing on a click to a dynamic route without a
  `loading.tsx`, so every workspace route folder now re-exports
  `components/shell/RouteLoading.tsx`. Same-route changes (page 2, tabs,
  sorts, filters) keep the route, so `components/shell/NavigationState.tsx`
  sets `html[data-navigating]` on an internal link click and the main
  area dims until the URL changes (15 s safety clear). Measured against a
  1.5 s artificial API delay: skeleton after 21 ms, dimming after 5 ms.
- Do not add a thin progress bar: the drawn-dash scan flags short bars,
  and the owner reads them as dashes.
- `JobListPage` no longer waits for `/api/sessions` before `/api/jobs`;
  only Latest discoveries without a chosen pull needs it first.
- Every text field outside sign-in and account identity sets
  `autoComplete="off"`, so the browser never offers past searches or
  answers; `search-and-navigation.spec.ts` checks every route. The
  search box has no "/" chip (the approved V2 search has none), keeps the
  `/` shortcut through `aria-keyshortcuts`, and its field draws no second
  focus outline inside the box's ring.

Second round, from production timings. `backend/scripts/time_pages.py` times
every request each page makes, in-process and read-only, printing only
paths, sizes and milliseconds. The owner pipes it from the laptop:
`ssh -i ~/.ssh/ace_oracle ubuntu@161.153.89.170 'cd /opt/ace && docker compose --env-file .env -f deploy/oracle/compose.yaml exec -T api python -' < /home/ubuntu/Documents/ace-next/backend/scripts/time_pages.py`.
After the first release (JIT off) it measured, in ms: `/api/stats` 216,
`/api/jobs` 97, the new-since count 111, `/api/facets` 146, `/api/dashboard`
68, `/api/system` 79, `/api/pulls` 44, `/api/intelligence` 2,542 and
`/api/coverage` 3,365. Fixes that followed:

- `build_stats` counts its five tiles in one pass and the three score
  bands in a second, with conditional counts (`count(CASE WHEN ...)`), in
  place of eight scans. Identical on real data (1,328, 4, 325, 681, 1,155;
  750, 268, 14); 107 ms down to 43 ms locally.
  `test_stats_tiles_equal_the_lists_they_describe` checks each tile against
  its own list under five filter selections.
- List pages ask only for what they show: Applications drops `/api/stats`
  (it never showed the queue totals) and `/api/dashboard` (it used two
  numbers that `/api/marks` already holds); `/api/applications/external`
  now returns `corpus_started_at`. Saved and Archive need only `/api/jobs`.
- `/api/jobs?count_only=true` returns the total without reading a page;
  the new-since badge uses it. `count_jobs` is the one count both share.
- `extract_skills` skips an alias whose required text is absent from the
  case-folded posting, then lets the regex decide boundaries. Four
  non-ASCII characters fold to ASCII letters under `re.IGNORECASE` (U+0130,
  U+0131, U+017F, U+212A) and are translated first. Zero differences over
  4,000 real postings, 6.4x faster; the Career Dashboard ran it over 100
  descriptions in 1.4 s. `test_skill_extraction.py` proves the fold table
  over the BMP and each regex alias's required text from its parsed pattern.
- The Career Dashboard gathers passing jobs first (a `MATERIALIZED` CTE on
  PostgreSQL) before taking the 100 newest: 177 ms to 51 ms, same rows.
- Coverage: sponsorship refusals use JSONB containment on PostgreSQL
  (797 to 558 ms, same 189 employers) and the API keeps them as a
  `Snapshot` (`backend/app/api/snapshot.py`): at most ten minutes old,
  refreshed in a background thread, so only the first read after a restart
  waits. Reachability and dark boards stay live.
- Prefetch: with `loading.tsx` everywhere, Next prefetched every visible
  link, 39 requests per page load, including each job row, whose
  `generateMetadata` called `/api/jobs/{id}`. Job links and sign-out now
  use `prefetch={false}`: 23 requests and no job lookups per load.

## Current working state on 2026-10-25

### Inbox sync clarity, the email as it arrived, Rejected companies (2026-10-26)

**Release status:** live since 12:51 Pacific; evidence in the deployment section
at the top of this file.

The owner found Inbox unclear at a glance: it showed nothing to review, gave no
way to tell whether all email was in, and a fresh rejection (shared Ashby
sender, opening with "thank you for applying") was missing from the dashboard.
They asked for one click and a clear "everything is synced" state, the exact
email as received instead of extracted text, more choices (an acknowledgement
option), a "Rejected companies" panel with a clearer picture, and search plus
pagination on the rejected applications list.

Causes found in code. Production reads were refused by this session's
permission classifier, so that email's stored row was not inspected; the
fixes cover every path it could have taken:

- Nothing reads Gmail in the background. Email arrived only when "Run
  catch-up" or "Import past email" was pressed; no timer is approved.
- "Last sync" also moved when an older import page ran, so the page could show
  a recent time while new email had never been fetched.
- A rejection that opens with thanks was filed as a receipt whenever its
  decisive sentence was not read: when body extraction failed (for example an
  HTML email whose head is never closed) only Gmail's ~200 character snippet
  was classified, and receipts were never read again. Receipts never appear in
  Waiting for you.
- The email view showed text extracted from HTML, not the email.

What changed (branch `inbox-clarity-20261026`, from production `3e4e25b`):

- Inbox checks Gmail itself when opened, while it stays open and visible (at
  most every 3 minutes; a Google rate limit rests it 10 minutes) and on Sync
  now. Sync now also reads email kept under older rules again (the separate
  recheck banner is folded in). A status card says All caught up, N emails need
  you, paused or needs attention, when Gmail was last checked and what the last
  check found. `last_synced_at` now means only the last check for new email;
  importing older email no longer moves it. Import older email is a collapsed
  section; `following_changes` reports whether the history cursor is set.
- Views: the default `decision=auto` shows Waiting for you when anything waits,
  else Recruiting email (everything about applications, newest first, with what
  ACE did, including ignored email whose subject mentions an application or
  interview). `q` searches sender, subject and snippet server-side, wildcards
  literal. `GET /api/inbox/messages/{id}` opens one email for deep links from
  Analytics records and the audit trail (`?message=<id>`).
- The email as it arrived: `backend/app/inbox/display.py` rebuilds the email's
  own HTML from an allowlist (no scripts, handlers, forms, frames, meta, base
  or stylesheet links; CSS `url()` and `@import` removed), inlines pictures
  attached to the email by Content-ID within size limits, never fetches
  pictures from the sender's servers (it reports how many; 1 by 1 pixels are
  not counted), opens links in a new tab, adds a strict CSP meta and turns
  dashes into punctuation. `/full` returns `document`, `format`,
  `blocked_images`, `to`, `message_id_header` and `thread_id`. The web shows it
  in `components/inbox/EmailFrame.tsx`: an iframe `srcdoc` sandboxed with
  `allow-same-origin allow-popups allow-popups-to-escape-sandbox` and no
  `allow-scripts` (same-origin only lets the page measure its height), plus
  Show as plain text and Open in Gmail (an `rfc822msgid` search in the
  connected account). Nothing new is stored.
- Choices are grouped. Changes the application: Rejection, Assessment,
  Recruiter reply, Interview, Offer. Nothing to change: Acknowledgement
  (`receipt`), Status update (new decision `update`, no migration), Not about
  my applications, Decide later. ACE's reading is marked; filed email can be
  changed by choosing again.
- Parser version 3 in `reconcile.py`: more rejection wording (move ahead with
  other candidates, won't be able to offer you, we regret that, application not
  selected, position no longer available); a "thank you for applying" email
  that also sounds like a decision becomes `possible_rejection` and waits; a
  receipt read only from the snippet waits; `<body>` ends an unclosed head.
  Recheck now also reads receipts ACE filed itself (reason `Application
  receipt; no status change`) again, never receipts the owner filed. The bump
  makes waiting email and ACE-filed receipts stale once.
- Analytics: "Companies that rejected you" is now "Rejected companies" with
  totals (rejected applications, companies, dated by an email, latest
  rejection) and a table of rejected roles, rejected of applied, still in
  progress there and last rejection, newest dated rejection first
  (`rejection_summary`; rows add `dated`, `roles`, `in_progress`). The records
  page has search (`q`: every word must appear in company, role, job ID or
  record key), 25/50/100 per page and numbered pages. With
  `evidence=rejection` it is titled Rejected applications, sorted newest
  rejection first, and each outcome shows its date and View email when an email
  recorded it (records add `evidence` and `requisition_id`).

Validation: 1,375 backend tests (new: display rebuild and its dash rules,
parser 3 wording including a fictional Ashby-shaped rejection that opens with
thanks, unclosed head, snippet-only receipts, views, search, single email,
status updates, receipt recheck, full email document, rejected companies and
records search), 13 Node render tests (`web/tests/inbox-review-render.test.mjs`
and the new `web/tests/analytics-rejections-render.test.mjs`, run with
`node --test`), TypeScript, ESLint, production build (CPU peaked at 92 C),
forbidden-dash scan 0 and whitespace. Playwright specs were updated and added
(automatic sync, frame sandbox, filings, search, deep link, rejected records
search and pages) but not run: the cooling restriction stands. No deployment,
migration or production read occurred.

After release: open Inbox; it checks Gmail by itself. Press Sync now once to
read the older waiting email and ACE-filed acknowledgements again under parser
3; a clear rejection among them is recorded with Undo. Search a company name to
see exactly what ACE did with its email.

### Inbox automatic rejections, one-click review, Career Dashboard removed (2026-10-26)

The owner found the Inbox unusable: nearly every email waited for review, and
the review form made them pick one of 40 applications from a list, an outcome
from another list and a confirmation checkbox. They asked for clear rejections
("we regret to", matched to the job) to be recorded automatically, the whole
email to be shown when ACE is unsure, simple choices, a list of the companies
that rejected them in Analytics, and Career Dashboard to be removed entirely.

Why almost everything waited: only three rejection phrasings were known; a job
ID was found only after "requisition", "req id" or "job id" (not "Ref:"); the
sender had to be the employer's own domain (never Greenhouse, Workday and the
other platforms that send most rejections); only text/plain bodies were read,
so HTML-only email was judged on its 500-character snippet; backfill was
preview-only; receipts went to review; and the server switch and connection
setting for automation were both off.

What changed (rules in the Gmail evidence contract below):

- `reconcile.py` parser version 2: wider rejection wording with a withdrawal
  guard, labelled IDs including Ref, company identity from the sender's display
  name, subject or domain (platform domains excluded), exact-title and
  only-application matching with a title check, ranked candidates (best first)
  for review, receipts, and a 24 hour grace for marking Applied after a quick
  rejection. `conflict()` is shared with the live re-check before writing.
- `inbox.py`: HTML text extraction, `_apply()` (automatic rejections from any
  import; positive outcomes unchanged), `receipt` decisions, `/messages/{id}/full`
  (live, never stored, token cached 30 minutes in memory), `/recheck` for email
  read under parser version 1, counts `receipts` and `stale`, owner decisions on
  ignored/receipt/unrelated email, `kind` on review, undo returning the email to
  the queue, `auto_rejections` in the connection state. `GMAIL_AUTO_REJECTIONS`
  (default true) is the server switch; no migration.
- Inbox page: Waiting for you, Recorded automatically and Receipts counters,
  "Check waiting emails again" for stale email (loops `/recheck`), clear email
  views, and a review panel with the full email, ACE's preselected application
  (Change to search) and one-click Rejected, Interview, Assessment, Offer, Just a
  receipt, Not about my applications and Decide later.
- Analytics: `rejected_companies` and the "Companies that rejected you" panel on
  the Companies tab, linking to the exact rejected records per company.
- Career Dashboard removed: `/app/dashboard` page and loading screen,
  `components/intelligence/ActionQueue.tsx`, `routers/intelligence.py`
  (`/api/intelligence` and its actions), its test, nav entry and unused styles.
  `/app/dashboard` redirects to `/app/analytics`. `/api/dashboard` (an older
  aggregate) is untouched. Stored action rows remain in the database, unused.

Validation: 1,322 backend tests (new: matcher wording, Ref IDs, ATS display
names, title checks, HTML email, receipts, automatic rejection from imports,
switch off, undo and recheck, full email, rejected companies), 8 Inbox render
tests in Node, TypeScript, ESLint, dash scan and production build. Playwright
specs were updated (Inbox one-click flow, dashboard redirect) but not run: the
laptop cooling restriction stands. After release the owner should open Inbox
and press "Check waiting emails again" once; it reads each waiting email from
Gmail again and records the clear rejections.

### Gmail connection and rate-limit diagnosis, 2026-10-25 Pacific

#### Corrective review interface and error persistence

The owner then reported a sync 500 and could not find any review controls after
selecting a 90-day import window. Sanitized production stack/error-category
inspection identified `StringDataRightTruncation`: the previous explanatory
quota error exceeded `gmail_connections.last_error`'s 120-character column.
The earlier SQLite tests did not enforce that PostgreSQL limit. The corrective
change shortens the message and bounds stored error strings in both request
handlers and the optional one-shot Gmail script, without a migration.

Read-only counts at diagnosis were 145 imported messages and 43 pending reviews.
The old screen's 100/30 tiles described only its latest 100-message response,
and its default Review queue included ignored mail. Selecting ignored mail
intentionally had no manual-outcome form, making pending review inaccessible
to the owner. `90 days` is an import window; `30` was a message count, not days.

The correction adds global owner-connection counts, pending-only filtering
before pagination and 50-message UI pages. The default queue includes review,
exact-preview and deferred messages; all/ignored mail remain separate views.
Needs your review is clickable. The guided panel contains application search,
a human-readable application selector, an initially blank outcome selector,
explicit confirmation and defer/unrelated controls. Selecting another email
clears all choices. There is no default Rejected status. Import-window changes
reset the page token and retain the chosen window in the URL; progress wording
distinguishes importing mail from confirming outcomes. New reviewed events use
the original email timestamp while recorded-at remains the audit time. Existing
events and application states are not backfilled or automatically changed.

Verification: 116 focused backend tests, four additional runs against a
disposable local PostgreSQL fixture, and eight actual React markup render
checks passed. The test PostgreSQL container was stopped and removed. Four
fictional Playwright interaction regressions were added and collected, but not
executed: the laptop's cooling restriction still prohibits Chrome. TypeScript,
ESLint and production build passed. No production mailbox content or screenshots
enter fixtures. This correction continues the owner-requested Gmail/Analytics
rollout; deployment evidence is recorded after activation rather than inferred
from these local checks.

New files: `web/src/components/inbox/InboxReviewPanel.tsx`,
`web/tests/inbox-review-render.test.mjs` and
`web/tests/e2e/inbox-review.spec.ts`. Existing Inbox client, shared Inbox CSS,
router, Gmail client/script and focused regression tests carry the other
changes. Career Dashboard, the extension, discovery, schema, Gmail grants and
automatic-outcome preferences remain unchanged.

Corrective API/web release `42d6eb21ca68b60582bb9df3d13a849837fddd3e` became
healthy on 2026-10-25 at 21:16 Pacific (2026-10-26T04:16Z), continuing the
owner-requested working Gmail/Analytics rollout. Public health/header SHA
matched; deployed backend file hashes and four guided-review client bundle
markers matched. Read-only live checks verified 200 imported messages and 58
pending reviews, exact global counts, pending-only rows, a disjoint next page,
separate ignored mail and Analytics totals/ranges for 919 applications. These
are dated snapshots; the owner continued previewing email during this work.
No review decisions or application outcome mutations were performed by the
deployment/diagnostic. Anonymous Inbox evidence still returned 401.

Fresh backup
`private-backups/inbox-review-release-20261026T041218Z/database.dump.gz` passed
gzip and archive checks; rollback API/web image IDs and private inventories are
beside it. Eight protected table counts and applied-mark counts matched. Only
API/web were replaced; scheduler/PostgreSQL/Caddy container IDs and the private
configuration hash were unchanged. Schema remained `0050`, owner automation
remained false and no timer, Gmail permission change, migration or retrospective
audit rewrite ran. Production checks validated data and compiled controls,
not signed-in browser interactions; the owner must refresh and complete the
explicit review form. The current tiles use global counts, superseding the
bounded-counter description in the older release history below.

The owner subsequently created the separate Web OAuth client `ace gmail` in
project `acee`, with the correct Inbox callback, saved the Gmail read-only and
basic identity scopes, and added a test user. The owner configured private
`GMAIL_*` values and authorized Gmail. Earlier zero-connection observations
below describe the Analytics release snapshot, not the current connection.
Neither the owner's email address, credential values nor Console/Inbox
screenshots are retained in this public document.

Read-only diagnostics verified token refresh, profile, message listing and 100
message reads. A larger bounded diagnostic reproduced HTTP 403 with Google's
`rateLimitExceeded` reason at message 261. This is a quota/read failure, not
invalid credentials. The diagnostic imported no evidence and changed no
application records, scopes, grants or sync state. Production still had an
unfinished initial import, no successful-sync timestamp/cursor and an error
state at that check. Reconnecting or creating another client is unnecessary.

A fix is implemented in `backend/app/inbox/gmail.py` and
`backend/app/api/routers/inbox.py`: four bounded attempts with exponential
backoff/jitter for explicit quota, transport and transient server failures;
respect for Retry-After; no retry of ordinary permission refusals; sanitized
actionable messages; skip detail downloads for already imported IDs; tolerate
messages deleted after listing; preserve ready authorization on temporary
failure; and return 429 for exhausted rate limits. No new Gmail permission,
automatic outcome setting, schema, scheduler or frontend change is involved.
`backend/tests/test_gmail_reads.py` uses only fictional Google responses and
isolated SQLite data. The final focused Gmail/Inbox/Analytics/API/marks/petition/
Pulls set passed 112 tests; whitespace and zero-hit dash checks passed. No
frontend changed and no browser suite was run. After the owner's explicit
approval, API-only release `dde926fe93efc9c1aa4f029527d8742682af840b` became
healthy at 2026-10-25 20:01 Pacific (2026-10-26T03:01Z). The deployed source
hashes matched both changed backend files. The web image remains
`922640f73a00c445139771347b2b3a1cb4ccba0a`; `/healthz` reports the frontend
SHA, not the API commit, so different API/web SHAs are expected for this release.

A fresh private backup,
`private-backups/gmail-release-20261026T030018Z/database.dump.gz`, passed complete
gzip integrity and PostgreSQL archive-list checks before activation. Rollback
API image ID and before/after aggregate inventories are beside it. Eight
protected table counts and the applied-mark count matched. Only API was built
and replaced; web, scheduler, PostgreSQL and Caddy container IDs were unchanged,
all relevant services were healthy, and schema remained `0050`. No migration,
scheduler operation, Gmail scope/configuration change, automatic-outcome
enablement or production application/evidence import ran during deployment.

Post-release read-only diagnostics passed token refresh, live Gmail profile and
listing reads, all four Analytics date ranges, 919 unique application totals
against existing marks, cohort partitions, record drilldowns and deduplication.
Anonymous Analytics returned 401 and public health was ok. Global and owner
automatic outcomes remained false. The existing connection still had its saved
error state, no successful-sync timestamp and incomplete preview: the owner
must refresh, select Resume sync and complete the historical preview pages.
This release does not silently reset their saved state, import a mailbox or
confirm outcomes. Full historical import and signed-in UI recovery remain to
be verified through that owner action; the rate limit itself is not claimed
to have disappeared.

Before corrective release `42d6eb2`, Inbox `Emails reviewed`/review tiles used
the bounded displayed message list. They now use global stored counts; these
still do not establish complete observation coverage. Completing email import does not unlock missing
submitted-resume/channel attribution, response-rate coverage or petition data.

### Approved Analytics redesign, released on 2026-10-25

The four-tab Analytics design in `design/ace-analytics-pixel-lock/` is implemented
from `9cbafd7`, then rebased onto the newer performance updates at `4f41949`.
The owner explicitly requested production deployment. At 2026-10-25T23:41Z,
production health reported release `340b175251a8040f3eedad9553c3f6f965657698`.
`/api/analytics` is a new authenticated,
no-store, read-only projection over the existing Inbox application identities,
marks, external applications, outcome ledger and reviewed petition reports.
It adds submission-date/role filters, local Monday-to-Sunday weeks, undo-aware
outcome deduplication and official employer-year evidence. Chart drilldowns use
`/app/applications/analytics`, a read-only filtered Applications child view backed
by the same projection, with links to existing job application controls. Career Dashboard's
existing read model, the extension and discovery are unchanged. No schema or
migration change is needed. Matching API and web images were built and activated
with `--no-build --no-deps --wait`; both were healthy. PostgreSQL, Caddy and the
scheduler retained their existing container IDs. Production remained at `0050`.

The current schema does not record submitted resume versions, application
channels or complete observation coverage. Analytics explicitly reports those
gaps and does not assign the primary resume, infer channels, rank incomplete
combinations or fabricate response rates. Historical petitions never prove
current role or new graduate sponsorship. Company logos use a reviewed local
favicon cache with provenance and an image-error monogram fallback. Pulls adds
only logos and the historical date calendar above its original side cards.

Implementation, privacy boundaries, screenshot comparisons, exact changed files
and local test results: `docs/architecture/2026-10-25-analytics-redesign.md`.
Local validation passed 89 focused backend tests, 45 Playwright tests, a final
filtered-record/mobile recheck, TypeScript, lint, production build and a zero-hit
dash scan. All four tabs have 1672x941 Day and Night comparison captures.
The fictional capture database is `/tmp/ace-analytics-fictional.db`; artifacts
remain ignored in `artifacts/analytics-validation/`. After integration, 112 focused
backend tests, TypeScript, lint, build and dash checks passed. The browser suite
was not repeated because of the documented laptop cooling issue.

A fresh 437 MB private backup in
`private-backups/analytics-release-20261025T233637Z/database.dump.gz` passed gzip
integrity and PostgreSQL archive listing before activation. Previous image IDs
and before/after aggregate inventories are retained beside it. Eight protected
table counts and the applied-mark count matched. A production diagnostic forced
all connections read-only: 919 unique applications matched existing mark totals;
four date ranges, cohort partitions, pagination deduplication and outcome
drilldowns passed. The in-process API returned 200 with no-store. Public checks
verified the exact SHA, all 11 logo hashes, API 401s and sign-in redirects for
all four tabs. Actual production tables have zero Gmail connections and zero
petition reports, so those unavailable states are accurate. No Gmail consent,
migration, scheduler operation, extension publication or destructive data
operation ran. Signed-in production browser rendering was not exercised.

Public health was checked again at 2026-10-25T23:52Z: the frontend still
reported `340b175251a8040f3eedad9553c3f6f965657698` and API status was ok.
The deployed checkout and images remain at that release. Documentation-only
commit `8e604e7` was subsequently pushed to `wine-rose-platform`; later knowledge
edits do not require a container rebuild. A newer GitHub documentation SHA must
not be mistaken for an undeployed runtime change.

During this knowledge update, another session pushed owner-requested UI cleanup
`922640f73a00c445139771347b2b3a1cb4ccba0a`: removing the Pulls company-first
explanatory note and the sidebar discovery-engine footer line. It preserves
company-first ordering and the topbar live-status control. At 23:57Z public
health still reported the Analytics release `340b175`, so this separate UI
cleanup was not yet live at that check. Preserve it when updating the branch;
this knowledge-only task does not activate another release.

The working branch is `wine-rose-platform`. At the start of this knowledge
update, local HEAD and GitHub matched `8e604e7` with a clean working tree.
The two newer performance commits, `269cb32` and `4f41949`, were preserved by
rebasing Analytics before its fast-forward push. There is no outstanding branch
divergence from that work. The branch also retains the website typography
commits (`54e939a`, `61debd6`, `8d84141`), the reconciled Focus Mode V5.1
commits (`559ee84`, `5b8ab4b`, equivalents of local `4ce3570` and `cb7bb5e`),
the V5.1 typography pass and theme sync/Close (`386bed9`). It contains the
existing V4 Answer Memory implementation (`2e7c1dc`). The
extension manifest is now `1.30.0` (contextual reuse and saved receipts, preserving explicit filling, Workday month/year and question-label corrections, full-viewport dragging and optional answer saving described above). The V5.1 extension has not been published; it
runs as an unpacked installation loaded from
`/home/ubuntu/Documents/ace-next/extension`. An unpacked installation must be
reloaded at `chrome://extensions`; employer tabs must then be refreshed.
The owner loaded the reconciled V5.1 card in Inter and asked for two changes:
follow the computer's Day or Night setting, and a real Close control. Both are
in `386bed9`; the owner's reload of 1.28.0 is not yet recorded.

The approved V5.1 extension runs inside the existing MV3 extension. It has a
compact draggable card, visible six-dot handle, remembered position, manual
minimized dock, a Close control on the card and dock, Day and Night Wine and
Rose themes that follow the computer until the owner picks one, **Fill**,
persistent Review,
Review Complete or Review Paused, Answer Memory and Activity workspace, manual
Scan fields, dynamic field detection, existing resume/pairing support and
Alt+A. Review mirrors exact native select, radio, checkbox and multiple-select
options. Supported Workday listboxes expose their real choices through **Load employer options** inside ACE, or when opened on the employer page. Review answers remain drafts until **Approve & fill** verifies the actual employer control. Unsupported custom controls stay on the
employer form for manual completion. ACE never submits or marks Applied.
Workday listing and search routes outside `/apply/` stay quiet, including after
single-page navigation back from an application. The toolbar Wake override
remains available.

### Automatic logos for future employers (2026-10-26)

**Release status:** deployed in `21f563a` with signed-in production HTTP/asset
verification above. The following paragraphs retain the original local audit.

The owner clarified that every future pulled company needs automatic logo
handling, rather than further additions to a fixed reviewed list. The existing
59-file bundle remains a fast path; it no longer limits employer coverage.
`CompanyLogo` now requests `/api/company-logo?name=...` for an unbundled name,
with visible initials during loading/failure, lazy image loading on compact
rows, and reset state on navigation. Every existing shared logo surface inherits
this behavior without another company-specific code change.

The owner-only endpoint reads exact company/source identities from the existing
catalog and indexed job records. Enabled, registered employer sources with
verified board metadata or stored job evidence can supply seeds. External
application links, public feeds, unknown names and mismatched sources cannot
supply arbitrary fetch URLs. Shared ATS favicons and social-profile branding
are not employer logos. Company-declared tenant images or an exact structured
hiringOrganization match can provide a logo or official employer website.
Employer-owned registered hosts can provide their declared site icon.

`backend/app/branding/` contains this independent asset service. It performs
normal certificate-checked HTTPS, validates every DNS answer, pins the public
address while retaining TLS SNI/Host, checks redirects and robots for pages
and image CDNs, stops on explicit refusal, bounds requests and image sizes,
and returns only decoded/re-encoded PNG at up to 96 px. No cookies, referrers,
owner mail or application contents are sent to external sites. SVG/HTML,
tracking-size, transparent and solid placeholders are rejected.

Four asset workers, a 32-request ceiling, per-company concurrent-request
coalescing and a 512-entry private cache prevent repeated row lookups from
repeating network work. Successes last seven days; misses six hours. Cache
metadata records source, evidence page, fetch time and PNG hash. Disposable
files live under the system temp directory at `ace-company-logo-cache-v1`
(mode 0700 directory/0600 files), outside Git and the database; they may rebuild
on container replacement. A first stored job changes an earlier board-only
cache identity. Request DB connections close before external image work. The
read-model/API auth and no-store policy remain; extension tokens cannot access
this route. Polling, scheduler, eligibility, application identities/statuses,
Career Dashboard, extension code, Gmail permissions and schema are unchanged.
The API now has a narrowly scoped public-branding-fetch exception to its
previous no-ATS-network rule; it still never polls or evaluates jobs inline.

Validation: 53 logo/backend tests plus 73 existing auth and board-name regressions
(126 passed together),
7 React/DOM company contracts, 8 Inbox rendering tests, TypeScript, lint, build
and dash guards pass. Nine Playwright cases collect only; Chrome remains
prohibited by the laptop cooling issue. A real public Shopify careers lookup
(outside the bundled list) returned its authentic icon; the built local website
then served a cached 96 px-or-smaller PNG through the owner-authenticated API
using an explicitly fictional Shopify job in a disposable SQLite database.
Anonymous access was denied, unknown companies returned 204, repeat image
bytes matched and fictional application totals stayed 33. This is local
verification, not a production deployment or production visual test.

The follow-up remains on review branch `company-logo-consistency-20261026`,
targeting `wine-rose-platform` in draft PR #1. Details and current limitations
are in `docs/architecture/2026-10-26-company-identity.md`. No deployment,
migration or scheduler operation occurred. Sites may refuse access, provide
only browser-rendered branding or only unsupported images. ACE automatically
attempts retrieval for new employers; it cannot promise a trustworthy actual
logo from every external website and never fabricates one.

### Consistent employer logos across the website (2026-10-26, local)

**Status:** The fixed-list limitation below is superseded by the automatic
future-employer service described above. The 59-file bundle remains valid.

Review branch: `company-logo-consistency-20261026`, based on
`wine-rose-platform` at `cdefb3f`. Merge target is `wine-rose-platform`.

The owner requested authentic logos for more employers and the same branding
inside job and company pages. The former system supported only 11 exact names
in Pulls/Analytics while job tables and detail pages always used initials.

- `web/public/company-logos/provenance.json` now holds 59 reviewed employer
  identities and 71 explicit aliases, including separate FedEx and FedEx Freight
  icons, General Motors and Southern Company. The 48 added assets are exact
  bytes declared by official employer websites, with source/page, review date
  and SHA-256. A local contact sheet was visually inspected; it contains only
  public brand marks and was not committed.
- `web/src/lib/companyLogos.ts` is the single identity resolver. It normalizes
  Unicode, case, whitespace and periods/commas, then matches reviewed canonical
  names or explicit aliases. No substring matching, guessed domains, arbitrary
  legal-suffix stripping or automatic parent/subsidiary substitution.
- `CompanyLogo`, `CompanyIdentity` and the existing company `Avatar` now share
  this resolver. Logos appear in Pulls, its company dialog, job tables, job
  detail heroes, company evidence pages, external application history,
  Analytics employer history, Inbox application records, Coverage and Resume
  Studio/check history. Company-first rows, controls, routes, application
  identities and the approved Wine and Rose layout remain. Career Dashboard,
  extension, backend, auth, data and scheduler code were not changed.
- Empty names show an accessible Company/C fallback; unknown and failed images
  retain visible initials. Failed-image state resets on identity changes,
  including a cached failure before the React error listener attaches. Sizes
  preserve the 36/64 px table/hero tiles and 26/48 px sizing below 720 px.
- An authenticated check of the built site found that this installed Next.js
  runtime supplies escaped company path segments. The company page now decodes
  once before both logo lookup and evidence queries; malformed old bookmarks
  stay usable. The regression covers FedEx%20Freight and General%20Motors.
- No browser contacts an external logo service. Assets are served locally and
  no source registration, scheduler fetch, migration or production data edit
  is involved. This does not promise authentic logos for every employer in the
  dynamic source catalog. Oracle, Intel, Cisco, Dell, Tesla, Mastercard, Ford,
  DoorDash, Akamai and Uber refused access during this review; HPE timed out
  and Walmart had no usable raster icon. These and unreviewed employers retain
  the visible fallback until an official asset is reviewed.

Validation and the exact scope are recorded in
`docs/architecture/2026-10-26-company-identity.md`. Browser execution and fresh
screenshots remain suspended by the laptop cooling restriction. This change
is local work, not a production deployment or production visual verification.

### Follow the actual question and avoid duplicate work (2026-10-26)

**Status:** passive question following and filling were superseded by the
owner-requested explicit-only 1.29.1 behavior above. Historical implementation
and verification follow.

The owner reported that Review remained on an old question and asked again
after a visible employer answer was already selected. Local **1.28.6** adds
active-question following and separate, value-checked form-completion receipts.
This supersedes the earlier requirement for another approval click after a
trusted owner answer has actually committed on the employer form, including
protected per-application choices. It does not authorize sensitive Memory reuse.

- Clicking/focusing an eligible employer control selects its exact Review
  question. Hovering while Review is open previews only; it never writes.
  The chip window follows the selected question beyond the original six-item
  slice. Per-question ACE drafts survive moving between employer questions.
  Minimized and closed cards retain their owner-controlled state.
- With Auto-fill known on, focusing a blank routine field can fill only its
  existing equivalent saved answer through the current native/choice/custom
  adapters. Disabled options, incompatible options, nonempty answers, protected
  questions, multi-answer controls, history-owned fields and ACE drafts are
  excluded. Actual readback must remain stable before completion. Native text
  focus is restored after validation so typing and Tab navigation still work.
  Undo blocks a focus-triggered refill until an explicit Fill or a new step.
- Trusted text edits commit on leaving the field; actual selected choices
  commit after settling. **Answered on form** shows the current exact answer
  without another entry or approval action. Protected decisions are local to
  this application, never saved to Memory or inferred from another question.
  Untouched protected prefills still show their current value for one explicit
  confirmation. Motivation, credentials, synthetic-only edits and raw custom
  search queries remain excluded from automatic completion.
- Completion receipts bind control identity, question, type, value and options.
  Clearing/changing those invalidates completion. Repeated no-op page events
  do not reopen a completed question. Memory saving is independent: turning
  auto-save off or a failed save does not make a completed form question empty.
  Failures offer Retry Memory save. ACE-editor drafts still use explicit
  Approve & fill with readback; manual approval advances normally.
- Inputless elements declaring role=combobox, including button variants, are
  treated as actual dropdowns rather than ignored or flattened into text.
  The associated menu and committed label must verify a custom choice.
  Protected menus can acknowledge a direct owner selection without reuse.
  Memory displays the loaded extension version for reload verification.

Validation: **58** fictional DOM contracts pass, including focus/hover/draft
switching past six questions, direct protected completion with no Memory save,
prefill confirmation, inputless custom choices, targeted reuse and Undo,
reverted writes, motivation exclusions and outer-frame following. The 258
matcher cases, Memory safety checks, TypeScript, ESLint, syntax, whitespace
and forbidden-dash checks pass. **35** Playwright cases collect, with two new
active-question/direct-choice scenarios, but Chrome was not launched because
of the cooling restriction. No new visual, installed-MV3, authenticated real
employer or paired live Memory verification is claimed. The owner's screenshot
alone does not establish its exact DOM; the new adapter supports declared ARIA
comboboxes conservatively. Reload **1.28.6** at `chrome://extensions`, refresh
employer tabs, and check the version in Memory. No production deployment,
extension publication, backend/data, Gmail, scheduler or permissions changed.

### Free movement beyond embedded application frames (2026-10-26)

The owner reported that ACE could move only within the form column. The
existing drag bounds used the content script's `innerWidth`/`innerHeight`;
inside an embedded form these are the iframe's dimensions. Local **1.28.5**
keeps the employer controller in that frame and presents its floating card in
the outer page's viewport through the existing extension service worker.

- `background.js` forwards render/hide messages from a child frame to frame 0,
  and UI events from frame 0 back to the originating frame/document. It derives
  the tab and source frame from Chrome's sender, rejects foreign/missing senders
  and reversed directions, and uses no page `postMessage`, extra permission,
  network service or credential. Sessions and render revisions reject stale
  question actions; a matching Close can always dismiss the current card.
- The outer card uses a closed shadow root and the existing CSS/font, remains
  draggable across the complete viewport, and routes only ACE editor state and
  existing actions to the source controller. It does not copy employer DOM,
  motivation answers or credentials. Native values/choices, approved drafts,
  protected per-form decisions, readback, Memory and undo stay source-owned.
- The original card is hidden only after outer acknowledgement. An unavailable
  outer receiver leaves the local card usable, with its existing iframe bounds.
  One active embedded application owns the outer card; unrelated child frames
  cannot replace it. Frame navigation/hide is session-scoped. Popup Wake/status,
  Alt+A, minimize/expand, Close, theme, keyboard movement and position reset stay
  connected. No arbitrary cross-origin DOM access is attempted.
- Pointer capture begins on pointerdown rather than after crossing the drag
  threshold. In-progress coordinates survive source rerenders. Touch dragging
  works from the header/grip/dock; the Review body remains scrollable. Arrow keys
  move the focused grip, Shift uses a larger step, and double-click resets it.
  Both hosts mount on the document root to avoid a transformed body trapping
  fixed positioning. Resize clamps to the current outer viewport.

Validation: **49** fictional DOM contracts pass, including two isolated content
controllers through the actual background router, full-viewport movement,
round-trip draft/approval/native choice/Memory/undo, dock/Close/Wake, stale and
foreign-message rejection, motivation exclusion and local fallback. The 258
matcher cases, Memory safety checks, TypeScript, ESLint, syntax, dash scan and
Git whitespace checks pass. **33** Playwright cases collect, including a new
cross-origin iframe movement and interaction fixture. Chrome was not launched:
the cooling restriction remains. This is local simulated transport validation,
not a live installed-MV3, real employer or visual verification. No fresh browser
screenshots are claimed. Reload **1.28.5** in `chrome://extensions` and refresh
the application tab. No production deployment, publication, backend/data,
Gmail, scheduler or permission change occurred.

### Automatic saving of finished routine answers (2026-10-26)

The owner explicitly requested no repeat approval for routine answers entered
on the employer form. Local extension **1.28.4** supersedes the earlier
per-question approval requirement for this eligible direct-entry path.

- **Auto-save routine answers** defaults on and is stored in Chrome local
  `aceAutoLearnRoutine`. Memory exposes this and **Auto-fill known** as separate
  accessible switches. Existing auto-fill preferences remain respected.
- Actual trusted owner text input becomes eligible, then saves when the owner
  leaves the field or commits a native change. A 350 ms settling period checks
  that the value, options, question, page and control still match. Typing again
  cancels the pending save. Untouched prefills and synthetic page events alone
  never authorize learning. Closing ACE suspends this observation path.
- Native single selects save the visible label rather than opaque option IDs.
  Native radios and accessible choice buttons save the real chosen answer.
  Supported custom dropdowns require a trusted click in their associated menu,
  committed readback and a closed menu or selected option. A query string or
  a click in a neighboring menu is insufficient. Unsupported/keyboard-only
  custom selections without verifiable commitment remain manual.
- Protected authorization, sponsorship, legal, company-specific and other
  sensitive answers, checkboxes and multiple selections remain application-only.
  Company motivation and credentials remain excluded. Answers drafted in ACE
  still need the explicit fill action and verified employer readback.
- Automatic and manual reusable saves share a serialized writer, avoid identical
  revisions, preserve matching legacy concepts and send expected revisions on
  corrections. Long keys use SHA-256 within the existing 180-character API bound;
  full questions still determine equivalence. Broad legacy concept collisions
  preserve non-equivalent answers separately. Current/previous/past qualifiers
  stay distinct. Conflicting equivalent records fail safely for Memory review.
- Successful saves remove the routine question from Review without minimizing.
  Failure stays visible with **Save now** retry; it never claims persistence.
  No answer values enter Activity or diagnostics. ACE still never submits or
  marks Applied.

Validation: 43 fictional DOM contracts, 258 matcher cases, Memory safety checks,
TypeScript, ESLint, syntax and forbidden-dash checks pass. Thirty-two Playwright
cases collect, including two new auto-learning scenarios, but were not run:
the laptop's cooling restriction remains. No new browser screenshots, live
employer interaction or authenticated paired production Memory verification is
claimed. No website/backend runtime, schema, production service, Gmail scope,
scheduler or extension publication change was made. Reload ACE **1.28.4** at
`chrome://extensions` and refresh employer tabs to activate the local version.

### Exact-question Review and one-entry approval repair (2026-10-25)

The owner reported that a Workday checkbox group showed an individual answer as
its question and offered only that choice, forcing duplicate entry. The display
path used `label[for=option-id]` even after the matcher found the group prompt;
choice grouping also restricted checkboxes to one `name`, although Workday can
use a distinct name for every option. All choice controls were rendered as one
single-answer dropdown, and lazy custom options required an employer-side click.

Local extension **1.28.1** now:

- Shares raw question extraction with normalized matching. Group accessible
  names and real headings identify the parent question; separate option labels
  cannot replace it. Standalone checkbox statements retain their own wording.
  Unlabelled radio options remain ineligible for profile matching.
- Groups checkbox choices by their question boundary, including Workday form
  fields with unique option names. Full checkbox/radio options are shown as
  their actual control type, with no 54-character answer truncation. Native
  selects preserve exact option codes and multiple selections.
- Keeps Review answers as drafts until **Approve & fill**. Employer edits still
  appear in Review. Drafts survive themes/rerenders; changed answers, option
  sets or detached controls invalidate a stale approval. This owner-requested
  approval sequence supersedes V5.1's previous immediate Review-to-form write.
- Lets the owner click **Load employer options** inside ACE to open/read a
  supported button listbox without choosing an answer. Ambiguous or inaccessible
  custom controls remain honest manual states; options are never invented.
- Verifies the employer state before completing approval or saving Memory.
  A reverted/rejected write stays open and cannot create reusable Memory.
  Protected questions and multi-answer checkbox sets stay application-only.
  Undo restores prior review choices/multiple selections. Never submits or
  marks Applied. Motivation exclusion, pairing, themes and card geometry remain.

Validation: 13 DOM contracts in `web/tests/extension-review.test.mjs` execute
actual content scripts against fictional forms, with explicitly simulated
layout/native activation/Chrome messaging; 258 matcher cases and Memory safety
checks pass. TypeScript, ESLint, production build, syntax, forbidden-dash and
whitespace checks pass. Playwright collects 25 extension cases, including three
new regressions, but **Chrome was not launched** because the laptop cooling
restriction remains. Existing Playwright expectations now require approval
before the employer value changes. No fresh visual screenshots, real Workday
verification, unpacked MV3 validation or browser accessibility verification is
claimed. `linkedom` is a pinned web development dependency for the DOM checks;
`npm run test:extension-dom` also runs in the web CI job.

No production deployment, scheduler operation, schema/data/auth/Gmail change or
extension publication was performed. Chrome loads this local folder:
`/home/ubuntu/Documents/ace-next/extension`. The owner must Reload ACE at
`chrome://extensions`, check version **1.28.1**, and refresh employer tabs.
Use Review, choose an answer once, then **Approve & fill**; custom button
listboxes may first need **Load employer options**. Rollback baseline is
`877b046`; restore only extension files into a separate copy if needed, without
resetting unrelated work. The owner's screenshots/answers were not saved.

### Direct employer answers, approval and future reuse (2026-10-26)

The owner clarified that they also want to answer an unknown question directly
on the employer form, have ACE adopt the answer and ask only for approval,
then auto-fill a later equivalent question. Local extension **1.28.2** adds:

- Debounced `input` and `change` detection for eligible employer controls,
  including typed answers before blur. Existing company-motivation exclusion
  runs before any value read. Password/search controls stay outside learning.
  Ordinary known profile edits do not create unsolicited learning prompts.
  Approval checks the displayed answer, option set and question again, so an
  unseen employer edit cannot be saved by a stale approval.
- An **Answer detected on form** preview with **Approve answer**, rather than
  a duplicate answer editor. Approval reads back the existing field and saves
  eligible reusable answers without another employer write or option click.
  **Edit answer in ACE** creates a draft if the owner wants a correction.
- Custom label/state mutations refresh Review even after an earlier Fill,
  covering dropdowns that do not dispatch `change`. Employer edits clear stale
  drafts, including old textarea drafts, and re-open the affected approval.
- Conservative equivalence for common prompt wording, retaining subject,
  numbers, timeframe, negation, answer shape and protected-question policies.
  Numerical/measurement prompts use specific keys. Existing legacy concepts
  are retained when correcting an equivalent stored answer, avoiding duplicate
  records that would make later reuse ambiguous. No memory records are deleted.
- Existing paired Answer Memory API and **Auto-fill known** preference power
  future reuse. It requires a successful save and real compatible controls;
  disabled auto-fill preferences are respected. Multi-answer sets, sensitive
  and company-specific answers remain application-only. Employer motivation
  remains entirely excluded. No submission or Applied-state mutation occurs.

Validation: **24** fictional DOM contracts pass, including employer text to
approval to a later equivalent auto-fill, native option codes changing between
forms, custom dropdown adoption after Fill, no duplicate writes, no learning
without approval, legacy Memory correction and protected/motivation/credential
exclusions. **258** matcher cases, expanded Memory safety checks, syntax,
TypeScript, ESLint, static dash and whitespace checks pass. **27** Playwright
cases collect (two new adoption/reuse cases); they were not executed and no new
screenshots were captured because the laptop cooling restriction still applies.
Browser event/default-action behavior, authenticated Workday and the owner's
live paired Memory save/reuse remain unverified by these local DOM tests.
Website runtime files and dependencies are unchanged in this follow-up; the
previous production build passed for the 1.28.1 repair. No production release,
backend migration, scheduler operation, Gmail change or extension publication
was performed. Baseline is `e6249ad`; reload local ACE **1.28.2** and refresh
employer tabs. Keep **Remember this approved answer** checked for routine
answers, and **Auto-fill known** on for subsequent applications.

### Exact control mirroring and approval layout (2026-10-26)

The owner confirmed direct answer adoption works, then clarified that Review
must replicate the employer's control type. They also supplied an Oracle
screenshot with **Approve answer** clipped in the three-equal-column action
row. Local extension **1.28.3** fixes both:

- Ordinary inputs were all rendered as textareas. Review now uses single-line
  inputs for single-line fields, textareas for multiline fields, native
  numeric/date/time types with the employer's placeholder and min/max/step/
  length constraints, and native datalists with their real suggestions.
  Native selects, multiple selects, radio and checkbox groups remain intact.
- Custom dropdown recognition includes `aria-autocomplete=list/both`, explicit
  input popup semantics and a `role=combobox` wrapper owning one input. A wrapper
  cannot adopt a neighbouring input. Readonly choice inputs are eligible for
  option selection without being treated as writable text.
- **Load employer options** also opens supported input comboboxes and uses
  only their associated visible options. The same actual options appear in an
  ACE dropdown. A raw text editor is never substituted for such a dropdown.
  Unreadable/inaccessible controls remain explicit manual states. No options
  are fabricated. The opener avoids clear/remove and submit buttons.
- Choosing a dropdown answer requires an actual option click and readback of
  the committed selection. A query that remains in an uncommitted search box
  cannot count as success. Selection labels beside cleared React-style search
  inputs are recognized. Placeholder values remain unanswered. Disabled or
  submit-button options cannot be clicked. Failed choices cannot create Memory.
- The primary approval action spans the full first row, with Show on form and
  Skip sharing the second row. Wrapping is allowed instead of clipping or
  shrinking the label. Native controls follow the card's Day/Night color scheme.
  Other Workspace actions retain their existing layout.

Validation: **31** fictional DOM contracts pass (including all previous
adoption/reuse cases), **258** matcher cases and Memory safety checks pass;
syntax, TypeScript, ESLint, dash and whitespace checks pass. **30** Playwright
cases collect, including new real-browser control-shape, readonly-combobox and
Day/Night narrow-layout assertions. They were **not executed** because the
laptop cooling restriction still prohibits Chrome. Thus no fresh screenshots,
actual text-fit measurement or authenticated Oracle control verification is
claimed. The owner image was used only in chat, not saved to the repository.
No website runtime, backend, database, scheduler, pairing or permission change,
production deployment or extension publication occurred. Baseline is `0ad9bbb`.
Reload ACE **1.28.3** in `chrome://extensions`, then refresh employer tabs.

The latest local visual comparison used fictional Chrome fixtures: the
approved Night compact reference and corrected extension compact capture were
both 318 by 332 pixels. Local artifacts are ignored under
`artifacts/extension-v5.1/`; do not commit private employer screenshots. Final
local checks at that point: seven Playwright Chrome extension tests passed
(the suite is now 22 tests across all `extension-*.spec.ts`), 258 extension
rule cases passed, `node extension/test-memory.js` passed,
`node --check extension/content.js` passed and `git diff --check` passed. These verify local
fixtures, not the owner's live authenticated employer pages or the actual
unpacked MV3 installation.

The website typography (self-hosted Inter, one token scale, sentence case
labels, tabular numbers) first went live at frontend commit `61debd6`, verified
from outside on 2026-10-24. It remains in the newer Analytics release above.
The extension shares it: Inter ships in
`extension/fonts/`, the panel registers it as `ace-inter` with the FontFace API
when a panel opens, and the V5.1 card takes the website's weights and its 11.5px
floor through one typography-only block after the approved V5.1 rules. The job
line under the wordmark keeps its approved 11px. The live website frontend is
now `340b175`, including both speed releases and Analytics. Later documentation
updates do not change the running website.
The pre-rebase local copies of V5.1 (`a1e59ff`) were retired on 2026-10-25:
`ace-next` was reset to the GitHub tip with the owner's approval. Safety
copies remain until the owner deletes them: branch `backup/local-before-sync`
and stash `knowledge-file-before-sync`.

Open production issue: Google sign-in on `https://ace.opik.net` returned 500
with `UniqueViolation auth_sessions_pkey Key (id)=(4)`. The owner's Gmail did
match the owner account; the serial sequence for `auth_sessions` is behind its
highest existing id. The guarded fix is in the working notes below. Whether
the owner ran it is not recorded, so check before running it again.

The V4 code added additive migration `0050` and authenticated
`/api/extension/memory` endpoints for approved reusable answers, with pairing
and existing answer-bank compatibility. Production reached migration `0050`
with the speed release on 2026-10-25 (`46d8738`): the owner's release output
printed `alembic_version` 0050 after a fresh backup. The Memory API itself
has not been exercised in production from here, so verify it read-only
before calling Memory operational.

## Historical core live state on 2026-10-24

At that verification the core API and database application commit was
`11a7fd4c74e3333ea76c4fe1e9eecba0615279c6`; schema was `0049 (head)`.
The owner account release section below has its evidence. This is historical:
the speed release subsequently applied `0050`, and the Analytics release above
verified `0050` read-only. Live extension Memory behavior remains unverified.

The owner clarified that the legacy site must keep discovering jobs until they
are confident in ACE Next. At this verification, **both `ace-scheduler-1` and
`oracle-scheduler-1` were running and healthy, each against its own PostgreSQL
database.** The minute cross-database replica cron was disabled. Do not restart it while both
schedulers run: Oracle produced 4,441 jobs and four Pull sessions during the
temporary cutover interval, so numeric IDs can now collide with future legacy
rows. The previous crontab is saved under
`/home/ubuntu/.local/state/ace-legacy-replica/crontab-before-cutover-20261023`.
Both websites remain available. Discovery results, application changes, and
marks on one site no longer sync automatically to the other. Compare matching
source identities and time windows; exact total counts are not an appropriate
parity signal in independent-discovery mode. Do not merge the databases or
re-enable the old replica without a new reconciliation plan.

### Application release on 2026-10-23

At `2026-10-23T23:10Z`, the owner-approved application release
`b8e30b0b4261257fea25fb8e46f03912c6811990` became live at
`https://ace.opik.net`. It includes Pulls `Early career`, `3 yrs max` and
`Applied before` badges, expanded-window persistence and the corrected
legacy-style sources-polling count. The public health endpoint returned OK
with that exact frontend commit. PostgreSQL, API and web were healthy, migration
was `0044 (head)`, and the privacy-safe inventory showed 963,970 jobs, 2,631
Pull sessions, 1,180 marks and one user. Both schedulers continued writing
fresh Pulls. The cloud scheduler retained its original container ID and stayed
healthy. The legacy scheduler was healthy; the historical replica cron stayed
disabled. The daily cloud backup timer remained active, with the verified
`ace-20261023T144522Z.dump.gz` backup present.

The first activation command omitted `docker compose --env-file .env`, causing
Compose to substitute blank database variables and begin recreating services.
That run was interrupted, then the same approved release was activated with
the explicit environment file. The database volume was not removed. Migration
exited zero and the post-release inventory and live health checks succeeded.
Always pass `--env-file .env` for the Oracle Compose file; its location under
`deploy/oracle/` does not automatically select the repository-root `.env`.
The deployment commands in `deploy/oracle/README.md` were corrected after
this incident. That correction reached the VM with the 2026-10-24 release.

### Autofill application release on 2026-10-24

The owner approved deploying the local autofill batch. Branch
`wine-rose-platform` was pushed, and `/opt/ace` was fast-forwarded to
`d1202fd1e590bc290e88c059109bb35ff114796c`. A fresh pre-release cloud
backup, `private-backups/ace-pre-autofill-20261024T172503Z.dump.gz`, passed
gzip and PostgreSQL archive-list checks. The versioned API, migration and web
images were built, then only PostgreSQL, migration, API, web and Caddy were
included in the activation command. Migration exited zero at `0048 (head)`.
At `2026-10-24T17:29Z`, `https://ace.opik.net/healthz` returned 200 with that
exact frontend commit. API, web, PostgreSQL and both independent discovery
schedulers were healthy; the Oracle scheduler kept its prior container ID.
The laptop's cross-database replica cron remained absent. The privacy-safe
cloud inventory showed 968,535 jobs, 2,704 Pull sessions, 871 applied job
marks, 47 external applications and one user. Cloud and legacy source states
both showed fresh writes after the release.

Migrations `0045` through `0048` added 33 blank answer rows. A separate
guarded transaction then saved 32 exact answers supplied in the owner's
screenshots, only where the matching row was still blank. No existing answer
was overwritten. The answer bank then had 104 rows, 98 filled. The owner
explicitly chose to leave `Eligible for bilateral visa classification` blank
for manual review. No personal answer text was committed to Git.

The web and API are live, but Chrome's unpacked extension is loaded from the
local `extension/` folder. The owner must reload its card at
`chrome://extensions` and reopen or refresh any application tab to use
extension version `1.25.0`. A website deployment cannot update an unpacked
browser extension by itself.

### Owner account release on 2026-10-24

The owner approved the account upgrade, including removal of the email line
beneath the sidebar name. Production was fast-forwarded to
`11a7fd4c74e3333ea76c4fe1e9eecba0615279c6`. Before activation, a
fresh private backup,
`private-backups/ace-pre-owner-profile-20261024T215213Z.dump.gz`, passed a
complete gzip check and PostgreSQL archive-list check. The migration, API and
web images built for the exact commit. Only PostgreSQL, migration, API, web
and Caddy were included in Compose activation. Migration exited zero at
`0049 (head)`.

At `2026-10-24T21:57Z`, the public health endpoint returned HTTP 200 and
`X-Ace-Frontend-Commit` matched the deployed SHA. The API, web, PostgreSQL
and cloud scheduler were healthy. The cloud scheduler kept its prior container
ID. The privacy-safe inventory showed 968,903 jobs, 2,722 Pull sessions,
871 applied job marks, 47 external applications and one owner. The legacy
scheduler was healthy. Cloud and legacy source-state successes were recorded
at `21:57:55Z` and `21:57:54Z` respectively. The old replica cron remains
absent. Anonymous requests to the account and photo endpoints returned 401.
Authenticated Settings and photo interactions were validated locally with an
isolated demo database, not with the owner's production session.

### SmartRecruiters screening autofill release details

The owner supplied screenshots of ServiceNow screening questions and asked for
careful reuse across small wording and employer-name changes. The local
extension update `1.22.0` adds narrow rules for those questions and a dynamic
`Previously employed by Company Name` template. Named employers require a
separate saved answer. Government questions with different time windows,
export-control residency, and the ServiceNow RiseUp program have separate bank
rows. Migration `0045` added those rows blank before the guarded one-time
answer save described above. Signatures and privacy declarations remain manual.

### Workday history date autofill release details

The local extension update `1.23.0` writes native month inputs using their
required `YYYY-MM` value while Workday displays them as `MM/YYYY`. It matches
prefilled employers to saved work history before filling dates, leaves
unmatched or ambiguous jobs alone, and never overwrites an existing date.
An isolated Chromium test covers current and past jobs, out-of-order history,
manually entered dates, and an unmatched employer. The owner must reload the
unpacked extension and the Workday application tab to use this change.

### Workday education and screening autofill release details

The local extension update `1.24.0` selects a Workday Field of Study result
rather than leaving uncommitted search text. For saved `Computer Science`, it
can select Workday's `Computer and Information Science` option when that is
the unique match. Migration `0046` adds five distinct answer rows blank:
spouse-based work authorization, bilateral visa eligibility, current F-1
status, maximum OPT/CPT authorization end date, and Big Four employment in
the prior 18 months. The extension derives the numbered authorization and
sponsorship follow-up only from both saved underlying answers. Existing
answers cover work authorization, future sponsorship, relocation and onsite
availability. The role-specific minimum-experience confirmation remains
manual because it can change with each job. Native date inputs receive ISO
values and are confirmed before ACE reports success. Screenshot values were
not committed to Git. The owner-supplied values were saved separately after
the approved production deployment, except for bilateral visa eligibility.

### Meijer and Verizon Workday screening autofill release details

The local extension update `1.25.0` adds precise matching for the three
Meijer Workday screening pages. Migration `0047` adds 11 blank answer rows for
recruiting-text consent; Meijer group contractor and employment history;
Meijer recruiter contact, current contractor status and six-state residence;
current visa description and OPT status; AI engineering tools, Azure AI
experience range and AI coding tools. Existing saved answers still handle
work authorization, future sponsorship, relocation and hybrid work. The
extension selects the exact `18 years or older` option only when the saved
adult-status answer is Yes; it leaves narrower age bands for the owner.
Tests cover all three page shapes and prove unrelated broad answers leave
these narrower questions blank. Screenshot values were not committed to Git;
the exact saved answers were written to the private production answer bank
after migration.

The same local update covers the Verizon Workday question page. Migration
`0048` adds eight blank rows for authorization to work for any US employer,
current visa sponsorship, combined federal/state/local government employment,
combined non-compete and non-solicitation agreements, family or close personal
ties to an employee, a family board member, personal US military service and
spouse US military service. Future sponsorship and adult status use their
existing saved answers. Matching and browser tests keep each distinct fact
separate, including when only a broader answer has been saved. The owner's
answers shown in screenshots remain outside source code. The bilateral visa
eligibility answer remains blank at the owner's direction.

Earlier on 2026-10-23, the owner approved a cutover, but then clarified that
this did not authorize stopping legacy discovery during the comparison period.
Oracle discovery was briefly stopped and legacy discovery was restarted; Oracle
was then restarted with the replica still disabled. A `docker compose start
scheduler` attempt on the legacy stack ran its old migration dependency, which
exited 255; the legacy schema remained at `0040`, and the existing scheduler
container was started directly. Both schedulers were healthy and recording
fresh source successes at `2026-10-23T15:49Z`.
At `2026-10-23T15:50Z`, both websites returned HTTP 200, both schedulers were
healthy and writing fresh source successes, and the replica cron was absent.
The legacy database had 2,337 enabled of 2,446 sources; Oracle had 2,340 of
2,449. These counts can now change independently and are not a failed replica
signal.

During the temporary cutover, the cloud scheduler `oracle-scheduler-1` was rebuilt from deployed commit
`204f30c5c3712bc31ad89cbbfcafb19ca0f8f762`, started at
`2026-10-23T14:57:01Z`, and was healthy with fresh source successes after
startup. The production app and `/opt/ace` stayed at that commit until the
later application release above. Its database was at migration `0044`. The
Pulls fixes at `5f8ebff` and `d89fb6b` were not deployed by this cutover.
At `2026-10-23T15:00:19Z`, the cloud had created Pull session 2,599 and had
172 source successes since scheduler startup. The stopped legacy database
remained at Pull session 2,598, proving the new window was cloud-generated.

A fresh cloud backup at
`/opt/ace/private-backups/ace-20261023T144522Z.dump.gz` passed gzip and archive
checks and a full restore drill into a temporary database. The restored copy
contained 944,431 jobs, 2,597 Pull sessions, 2,444 job sources, one user, and
migration `0044`. The temporary database was removed. The supplied daily
`ace-backup.timer` is enabled and active. Offsite Object Storage is not
configured, so cloud backups currently reside on the VM; the intact legacy
database is the separate rollback copy.

After the legacy scheduler stopped, a final sync through
`2026-10-23T14:51:26Z` used the running legacy web container because the stopped
scheduler container could not execute the replica helper. The final parity
query matched all documented aggregate lines. A further full-corpus check
found 3,300 stale `jobs.source_updated_at` values in the cloud replica. Those
timestamps alone were copied from the frozen legacy database in one guarded
transaction, and final parity, full source-state and source-catalog hashes,
job counts/content hashes and all shared Pull-session fields matched afterward.
The inactive replica script can miss a full-job update when an ATS-provided
`source_updated_at` predates the sync interval; repair this selection rule
before ever resuming that workflow.

The public `https://ace.opik.net/healthz` returned HTTP 200 during the temporary cutover with
frontend SHA `204f30c5c3712bc31ad89cbbfcafb19ca0f8f762`; API, web, database
and scheduler were healthy. Continue monitoring both schedulers and the backup
timer. The cloud VM remains a single host and is not an absolute uptime
guarantee.

## Historical live state on 2026-10-22

The canonical production URL is `https://ace.opik.net`. Dynu provides the
hostname. Caddy terminates valid HTTPS and redirects the temporary sslip host to
the Dynu hostname. Users should always be directed to `ace.opik.net`.

The cloud host is the Oracle VM at `161.153.89.170`. The deployment checkout is
`/opt/ace`, accessed as `ubuntu` with the local key `~/.ssh/ace_oracle`. Do not
print or copy the key. Production uses `deploy/oracle/compose.yaml` and a mode
600 `/opt/ace/.env`.

The active branch is `wine-rose-platform`. The remote is
`https://github.com/anwarbuilds/ace.git`. Local, GitHub and the deployed checkout
were all verified at commit:

```text
132235c29212feb43f50f59245d540628172c43b
Show real resume files and owner identity
```

The response header `X-Ace-Frontend-Commit` and `/healthz` both reported that
full SHA after deployment. Alembic is at `0043 (head)`. PostgreSQL, FastAPI,
Next.js and Caddy were healthy. The migration job exited successfully. The
cloud scheduler was stopped and remained stopped.

The exact cause of the previously stale cloud interface was a deployment
checkout/build mismatch. Production was still at `16c1c82` while the approved
local and GitHub work had advanced through `bff2293` and `132235c`. A successful
local build or Git push did not update `/opt/ace` or replace its containers. The
fix was to push the approved branch, fast-forward `/opt/ace`, build images with
the SHA embedded, run migration 0043 and recreate only the production database
container, migration, API, web and Caddy dependency set. The named PostgreSQL
volume remained attached and the data inventory was verified afterward.

Latest privacy-safe production inventory after deployment and a successful
legacy replica replay:

| Data | Verified count |
| --- | ---: |
| Jobs | 904,107 |
| Active jobs | 640,223 |
| Poll sessions | 2,511 |
| Source states | 2,320 |
| Job sources | 2,385 |
| Job marks | 1,141 |
| Applied job marks | 821 |
| External applications | 47 |
| Application answers | 71 |
| Resume documents | 5 |
| Resume versions | 5 |
| Resumes | 5 |
| Career facts | 52 |
| Users | 1 |

These historical counts changed while the legacy scheduler and replica were
active. Compare settled pull boundaries instead of treating this table as a
frozen expected value.

The local file `ACE_NEXT_KNOWLEDGE.md` had intentional owner continuity edits
before the latest deployment and was kept out of commit `132235c`. Do not
discard this file merely because Git reports it modified. Review and commit it
only when the owner requests that documentation change to be committed.

## Product objective

ACE is a private career system for one primary owner. It continuously reads
approved employer sources, preserves every discovered posting, evaluates each
role against deterministic eligibility rules, tracks applications, scores jobs
against the active resume, supplies an answer bank to a least-privilege Chrome
extension, and presents the data through the approved Wine and Rose UI.

The production result must preserve all historical data and behavior from the
legacy ACE system. The UI changes, and new Resume Studio and Google sign-in
features are added, but the old data is not discarded or regenerated.

## Standalone platform specification

This section consolidates the durable product and engineering knowledge that
was previously spread across the handoff and topic files. Later sections add
dated production evidence, exact release history and operating procedures.

### Product priorities and vocabulary

ACE serves one primary owner. Its priorities, in order, are:

1. Find every eligible opening as early as practical, with high recall and low
   noise, from approved employer sources.
2. Make applying faster with safe form filling, while leaving review and final
   submission entirely to the owner.
3. Preserve a complete, trustworthy application history and resume knowledge
   base.
4. Present the system as a polished, accessible portfolio-grade platform using
   the approved Wine and Rose design.
5. Run continuously in the cloud without losing the intact legacy fallback.

Important terms:

- A **source** is one employer board, ATS tenant, official site reader or
  approved feed account with its own polling state and interval.
- A **job identity** is `(source, source_account, external_id)`. Numeric database
  IDs are internal and are not portable between the legacy and Oracle systems.
- A **content hash** is the SHA-256 identity of the posting content used to
  detect a real update without changing job identity.
- **PASS** and **REJECT** are the only eligibility outcomes. The former STRETCH
  tier was removed because the owner wants one actionable opportunities list.
- **Unverified** means the source did not provide enough description text for
  every requirement rule. It is an honest state, not a rejection.
- A **Pull** is a user-facing discovery window. Current Pulls group activity in
  15-minute windows. They are not a claim that every source polls every 15
  minutes.
- **Marks** are saved, reviewed, dismissed and applied state. Applied records
  also carry status and notes. The application stages are Applied, Screening,
  Interviewing, Offer, Accepted, Rejected, Withdrawn and No reply.
- Company tiers are BIG_TECH, TOP_TIER, ESTABLISHED and OTHER. Tiers order and
  explain results; they do not decide eligibility.
- Matching scores rank an already eligible job. Scores never decide whether a
  job is included.

### End-to-end data flow

```text
approved employer boards and feeds
              |
              v
provider adapters and discovery readers
              |
              v
authoritative snapshot, identity and content diff
              |
              v
versioned deterministic eligibility gate
              |
              v
resume scoring, Pull grouping and application state
              |
              v
PostgreSQL -> FastAPI -> Next.js -> owner browser
                    \-> paired Chrome extension
                    \-> optional alert email
```

The scheduler is the only discovery writer within each database. It stores all
postings, including rejected and closed records, so new rules can be evaluated
over history. FastAPI exposes owner-authorized JSON. Next.js proxies same-origin
`/api/*` requests to FastAPI at runtime. Caddy terminates HTTPS in production.
The extension uses a separately paired least-privilege token.

### Eligibility gate and role rules

The gate is deterministic, versioned and reproducible. It must not read the
clock, network or random state. The current default candidate profile is
`early-career`; the optional `sde2` profile may be enabled only after the owner
reviews its dry run.

The default profile admits:

- US locations, including Remote US and unambiguous US city or state forms.
  Bare `US` is matched on token boundaries so it does not match words such as
  Houston. Remote Americas or North America can include the US after explicit
  foreign-country checks.
- Full-time software engineering, machine learning and forward deployed
  engineering roles.
- New graduate, junior, associate, entry-level and otherwise unlabeled roles
  when the posting states no disqualifying requirement. Silence is unknown, not
  rejection.
- Bounded experience ranges when the candidate meets the lower bound. For
  example, `2 to 10 years` can pass on its floor, though it is not labeled new
  grad. An open-ended `3+ years` is rejected in the default profile. A stated
  requirement of 4 or more years is rejected.
- Roles silent about sponsorship. Only an explicit refusal to sponsor or a
  true work-authorization blocker rejects.

The gate rejects:

- internships, working-student roles and spelling variants such as intership;
- contract, contractor, freelance, temporary, fixed-term, contract-to-hire and
  AI-trainer work, including a structured employment type when the source
  provides it;
- senior, staff, management, hardware and broad security-role titles according
  to the current title rules;
- data engineering and data science while
  `INCLUDE_NEW_GRAD_DATA_ROLES = False`;
- postings outside the US scope;
- explicit sponsorship refusal;
- ITAR, explicit US-person or citizenship requirements, or language requiring
  access without a license. Ordinary export-control language is not itself a
  citizenship requirement.

New grad is narrower than early career. `is_new_grad` is based on explicit
title signals such as new grad, university graduate, campus and graduation
year. It is stored and used for filtering and ordering. It must not be inferred
from the broader early-career label.

The `sde2` profile differs only by admitting open-ended `3+ years`; it still
rejects 4+, 5+, senior, staff, manager and higher-level roles. Run
`python -m backend.scripts.gate_dry_run --profile sde2` before any switch.

Every gate change requires:

1. Update the versioned candidate profile or `ELIGIBILITY_RULE_VERSION`.
2. Add focused tests for both inclusion and false-positive boundaries.
3. Measure the read-only corpus impact.
4. Re-evaluate stale stored decisions. Current PASS rows are refreshed first;
   the full historical backfill runs afterward.

Do not copy the gate into an adapter or SQL filter. The real gate is the single
source of truth.

### Sources, adapters, scheduler and persistence

Current adapter families include Greenhouse, Lever, Ashby, Workday,
SmartRecruiters, Workable, Eightfold classic and PCSX, Jibe, Avature, Apple,
Google, Atlassian, Shopify, Gem, IBM, Amazon, Oracle Recruiting, ByteDance,
RippleMatch, Simplify, sitemap readers and related official-site readers.
Respect each host's robots policy and refusals.

Source rules:

- There is one fetch path per provider. Diagnostic scripts use the same real
  adapter contract so tuple shapes and cleanup logic cannot drift.
- A complete successful snapshot is authoritative for lifecycle. Never return
  a partial page set after a transient failure because missing rows would be
  marked closed.
- Workday and SmartRecruiters can expose a cheap list plus costly detail calls.
  Detail fetches may be predicated through the real title gate, but every list
  item must still be emitted for lifecycle.
- Use conditional HTTP where supported. A 304 advances success state but does
  not rediff the body. Force an unconditional refresh at least every six hours
  so a bad ETag cannot hide updates indefinitely.
- Retry transient 429, 500, 502, 503, 504 and connection failures with bounded,
  jittered backoff and `Retry-After` limits. Do not retry a real 404 as if it
  were transient.
- A 401, 403, 405, 429, bot challenge or CSRF-protected API is a refusal. Back
  off. Do not bypass it, rotate around it or restart repeatedly.
- Never mass-close jobs after an empty, partial, refused or failed response.
- Scheduler polling is bounded and concurrent. Slow sources continue in a
  persistent pool while other due sources run. A source cannot start twice.
- Restarts resume from persisted `last_success_at`; they do not make every
  source immediately due. Shared-edge providers such as Eightfold are paced.
- Poll intervals are per source and can differ widely. Amazon and expensive
  boards poll less often than ordinary boards.
- New sources are re-read from the database between cycles and do not require a
  process restart.

Source lanes:

- Lane A: employer ATS or official-site readers with full descriptions.
- Lane B: curated early-career feeds when employer descriptions are unavailable;
  these are browse-only and clearly unverified.
- Lane C: RippleMatch, the one approved exception where the apply link is the
  recruiting platform because some early-career roles exist only there.

The official employer posting is the apply target everywhere else. An
aggregator that links only to itself is not acceptable coverage.

Persistence rules:

- Stable identity is `(source, source_account, external_id)`.
- A title, location, description or employment-type change updates the same job
  and must alter the content hash.
- `job_evaluations` and `job_resume_scores` are derived, rebuildable tables.
  They carry input hashes and algorithm/rule versions so stale rows are
  detectable.
- PostgreSQL is production. Tests use a JSON fallback and SQLite where
  appropriate, so structural PostgreSQL behavior needs explicit tests.
- Long source-provided values such as multi-location strings use unbounded text
  where truncation could change gate meaning.

### Discovery coverage and recall

The most dangerous failure is silence: a missed posting produces no exception.
Coverage must be measured against independent employer lists, source audits and
the owner's known examples, not inferred from a healthy-looking queue.

Discovery can identify an ATS board from an employer's own careers page or from
approved feed links, then register it for direct reading. A feed hit must not
prevent the employer board from being read. A board that stops answering is a
company ACE has stopped reading, even if old jobs remain in the database.

Known unreachable or deliberately untouched sources include sites whose
robots policy or bot protection refuses access. Historical examples include
Tesla, Citadel, Citadel Securities, D. E. Shaw, LinkedIn and Equinix. IBM uses
its permitted site-search API rather than bypassing its careers WAF. Cloud IPs
can be treated differently from a home connection, so refusal rates must be
measured after deployment.

The owner currently compares independent legacy and Oracle discovery. Compare
source identity, official posting identity and aligned time windows. Do not
compare numeric IDs or demand identical totals. A recent private comparison
showed most one-sided jobs converging after an hour and no different
eligibility decision on shared jobs; that was evidence for one window, not a
permanent guarantee.

### Resume matching and applications

Resume matching is lexical and deterministic, with approved related-skill
partial credit. It is not a semantic model and never invents evidence. Matching
states are:

- `scored`: a current usable score exists;
- `pending`: the eligible job is waiting for a scoring sweep;
- `no_description`: source requirements were not readable;
- `insufficient`: too little recognized requirement text for a responsible
  score;
- `no_resume`: there is no active resume.

The scheduler scores active PASS jobs missing a current score, changed since
scoring or scored by an older algorithm, in bounded batches. One failure is
logged and retried later; it does not receive an invented score.

Application history comes from applied `job_marks` plus
`external_applications`. Marked pages bypass current gate and active filters so
closed or now-ineligible jobs never vanish from the owner's own history.
Application totals include historical submitted stages, not only rows whose
current label is exactly Applied. Avoid double-counting the same application
through marks and external rows.

Marking Applied must:

- update the row and every visible total immediately;
- synchronize other tabs and surfaces;
- persist through the authenticated API and survive refresh and sign-in;
- roll back the optimistic state and counters if the save fails;
- prevent duplicate mutations and stale race outcomes.

The spreadsheet import UI was intentionally removed. CSV export remains.
Legacy preview/import API routes may remain unused, but no interface should
revive the daily spreadsheet workflow without a new owner decision.

An unmarked listing can show `Applied before` when an earlier applied posting
has matching company/title and compatible location. This is derived at read
time and never copies the mark. Requisition numbers explain whether the new
posting may be a distinct opening. ACE shows the resemblance and lets the
owner decide.

### API and key data domains

The browser uses authenticated JSON with `Cache-Control: no-store`. Important
API families include:

- jobs, details, facets, stats and Pull windows;
- marks, application stages, notes, external applications and CSV export;
- answer bank, work history and education history;
- active resume, matching, Resume Studio documents, facts, versions and
  assessments;
- coverage and source registration;
- submission-filtered Analytics, exact application drilldowns and reviewed
  outcome/sponsorship evidence;
- owner account, sessions, email-code flows and Google callback;
- extension pairing and Answer Memory;
- health and safe operational status.

Core durable data includes jobs, sources, source states, evaluations, scores,
Pull sessions, marks, external applications, answers, work/education history,
legacy resumes, Resume Studio tables, users, browser sessions, extension tokens
and email-code records. Do not replace real aggregates with demo fixtures.

### Website product and design contract

The website is a real Next.js App Router product, not an iframe or screenshot.
The final approved reference is Wine and Rose V2. Older purple/gold,
anthracite, gray, alternate auth and homepage concepts are historical and must
not return.

Required routes and contracts:

- `/`: public cinematic home with no private owner data.
- `/login`: real owner sign-in using the approved split composition.
- `/signed-out`: shown only after a real session is invalidated.
- `/app/pulls`: authenticated landing page and truthful 15-minute discovery
  windows.
- `/app/opportunities`: eligible-job search, filters, sorting, official links,
  evidence and durable actions.
- `/app/jobs/[id]`: job details, matching evidence, eligibility explanation and
  application actions, including closed jobs.
- `/app/applications`: real application history, stages, dates, notes, filters
  and export.
- `/app/analytics`: the approved four-tab application Analytics interface,
  using `/api/analytics`. Its Companies tab also lists the companies that
  rejected the owner.
- `/app/applications/analytics`: read-only application records matching the
  exact Analytics selection, with links to existing stored-job controls.
- `/app/dashboard`: redirects to `/app/analytics`. Career Dashboard was removed
  at the owner's request on 2026-10-26 because Analytics covers it.
- `/app/applications/inbox`: owner-controlled Gmail Inbox Intelligence:
  a sync status card that checks Gmail when opened, automatic clear
  rejections, one-click review beside the email exactly as it arrived,
  acknowledgements, status updates, search and outcome reconciliation.
  `?message=<id>` opens one email. Google sign-in does not mean Gmail is
  connected.
- `/app/resume-studio`: documents, knowledge, versions, ATS checker and history.
- `/app/extension`: pairing, token revocation, setup and answer-memory access.
- `/app/archive`: historical reviewed and dismissed state.
- `/app/coverage`: source coverage, unsupported/refused sources and add-source
  workflow.
- `/app/settings`: theme, owner account, session security and existing
  preferences.

Old Browse and Companies routes redirect to Opportunities. Saved data still
exists even though Saved is secondary and not in primary navigation. Pulls is
home; Analytics does not replace it. Supporting routes
also exist for Saved, Answers, skill insights, company detail, Resume Studio
subpages, More and sign-out. Do not replace Pulls with a generic Dashboard or
Queue. The owner rejected a global Search or Jump command palette.

Locked identity and themes:

- The wordmark is exactly lowercase `ace`, with the `a` in wine and `ce` in the
  theme foreground. No logo tile, uppercase mark, subtitle or tagline.
- Night is black and deep wine. Day is rose wine and bright white.
- Primary V2 tokens are Night/Day respectively: base `#09070b`/`#fff9fb`, side
  `#120c13`/`#fff6f9`, canvas `#191019`/`#fffafd`, surface
  `#251825`/`#ffffff`, raised `#302131`/`#fff0f5`, hover
  `#3d283b`/`#fee8ef`, edge `#574050`/`#e9d3de`, text
  `#fff7fa`/`#27131f`, muted `#cfbcc6`/`#745a69`, sub
  `#ab8b9e`/`#946b80`, accent `#a62957`/`#97244f`, accent-high
  `#c93b70`/`#b63566`.
- Public and auth screens use the full angular sculptural A, reflective light
  trails, floor reflection and glass depth. The whole A must remain visible on
  desktop. Scale or reflow deliberately on smaller screens rather than clipping
  it.
- Use the shared semantic token layer on all pages. Do not let individual pages
  fall back to gray, generic red, purple, navy or framework defaults.
- Required review sizes include 1440x900, 1600x900, 1280x800, 1024px tablet and
  390px phone, in Night and Day, without horizontal overflow.
- Functional text must meet WCAG AA. Keyboard order, focus visibility,
  reduced-motion behavior, loading, empty, unavailable and failure states must
  be honest.

There must be no visible Unicode em dash and no en dash used as punctuation in
the website, extension, generated email or assistant-authored user-facing copy.
Also avoid decorative pseudo-elements that visually imitate dash punctuation.
Static scans are necessary but not sufficient; rendered pages, dynamic toasts,
dialogs, labels, placeholders, accessible names and pseudo-content must be
tested in both themes.

The V2 demo contains fictional navigation and data for visual review only.
Never ship its DESIGN DEMO selector, hash router, Preview workspace bypass,
sample names, hardcoded counts, fake health, fake scores or simulated saves.

### Pulls metric contract

Pulls must distinguish:

- distinct sources checked from raw attempts and retries;
- postings inspected from newly discovered postings;
- newly discovered from updated or re-seen postings;
- qualifying opportunities from all observed jobs;
- failed, skipped, blocked and zero-result checks;
- no check telemetry recorded from a successful check with zero new jobs.

The source of truth is backend telemetry with exact time boundaries and display
timezone conversion. Older windows without telemetry say `not recorded` rather
than showing zero. Health indicators must disclose freshness and never show a
reassuring success state when the backend has not confirmed one.

### Chrome extension and Answer Memory

The extension is Manifest V3. Important implementation areas are
`extension/content.js`, `fields.js`, `background.js`, the popup/side panel,
storage, pairing and rule tests. The current local manifest version is 1.30.0;
see the latest contextual adoption section for deployed API and scope rules.
The approved interface is ACE Focus Mode V5.1; older extension interfaces are
historical.

V5.1 behavior:

- Default to a compact floating card around 318px wide, not a full-height panel
  covering the form.
- Preserve Overview, Review, Memory, Activity, Fill, Scan fields, resume use,
  pairing and Alt+A.
- Use the lowercase `ace` wordmark, Wine and Rose Day/Night themes, clean
  outline icons and a visible six-dot grip.
- Provide compact, optional wider workspace and a manually chosen minimized
  dock.
- Drag freely from eligible non-interactive card and dock surfaces. Do not steal
  clicks, typing, text selection or scrolling from form controls. Use a movement
  threshold, clamp to the visible viewport, persist normalized position, allow
  handle keyboard movement and reset on handle double-click.
- Never auto-minimize after Fill, approval, skip, a detected question or Review
  completion. Review remains open and ends in a persistent truthful completion
  state until the user chooses Minimize.
- Detect dynamic fields with restrained, debounced observers and retain manual
  Scan fields as a fallback.
- Job listing and search routes must remain quiet. In particular, Workday
  listing/search routes outside `/apply/` stay quiet after SPA navigation. The
  toolbar Wake override remains available.

Review mirrors the real employer control for eligible questions: native select,
radio, checkbox, multiple-select, text, textarea and only supported custom
widgets with their actual choices. Page-to-ACE and ACE-to-page synchronization
must verify the employer control's real selected value. Unsupported or
ambiguous custom controls remain manual. Never display a generic text box for a
native select and never report success without reading the actual state back.

ACE fills; the owner reviews; the owner submits. Extension code must never call
`form.submit()`, `requestSubmit()`, synthesize a submit event, click an employer
Submit control, irreversibly advance a form, or mark a job Applied because Fill
ran. Applied state needs a separate explicit owner action.

Employer-specific motivation questions are entirely employer-page-owned. This
includes `Why this company?`, `Why do you want to join us?`, `What interests you
about joining [company]?` and materially equivalent questions. For them ACE:

- leaves the original employer field visible, editable and untouched;
- does not fill, suggest, mirror, capture, observe, log or send the answer;
- excludes the question from Review, progress denominators, Memory and
  Activity;
- does not change the field during Fill, Scan, navigation, theme changes,
  dragging, minimizing or dynamic rerender;
- retains historical server records but excludes them from automatic reuse;
- may show only a truthful reminder to finish employer-owned questions on the
  employer form.

Classification uses the question label and employer context, never the answer.
It must distinguish company motivation from technical questions such as `Why
did you choose eventual consistency?`. One shared predicate must guard scan,
fill, queue, observability, status counts, activity and memory retrieval.

Unknown ordinary questions enter Review. Finished routine employer answers may
be saved automatically under the owner-authorized Auto-save routine answers
setting. Only genuinely equivalent saved general answers may be reused when
type, options, scope and context align.
Authorization, sponsorship, citizenship, legal declarations, compensation and
self-identification require conservative, per-application handling. Never
infer a narrow sensitive answer from a broad saved answer.

V4 added migration 0050 and authenticated `/api/extension/memory` behavior for
approved reusable answers, with existing answer-bank and pairing compatibility.
Production applied migration 0050 on 2026-10-25 (owner's release output);
live Memory behavior is not yet exercised there. Verify read-only before
relying on it.

### Resume Studio

Resume Studio is deterministic and has no generative AI. Its backend lives in
`backend/app/studio/`; routes are under `/api/studio`. Migration 0039 created
documents, career facts with audit events, versions and assessments.

- Original document bytes are retained as uploaded.
- PDFs render through an authenticated content endpoint and short-lived browser
  Blob URL. DOCX and other formats show an honest download action when the
  browser cannot render them reliably.
- Facts are separate from wording. Parsed facts begin as suggested; owner-entered
  facts begin verified. Retirement marks a fact deprecated rather than deleting
  it. Only verified facts count as evidence.
- The first resume becomes primary only if no primary exists. Making a version
  primary copies its text into the legacy matching table and triggers the
  established rescore behavior.
- The ATS checker reports an `Estimated ace compatibility score`, not an
  employer ATS score. Algorithm `ats-2026-10-14-v1` weights requirement evidence
  45, parseability 20, hard fit 20 and content quality 15.
- Evidence used in experience, project or summary text receives full credit;
  skills-list-only evidence receives 0.75; approved related evidence receives
  0.5; preferred requirements weigh half.
- A posting under 400 characters, unverified, or naming fewer than three skills
  is insufficient job data and gets no aggregate score. A resume under 200
  characters is unreadable. Neither condition is represented as zero.
- The checker gives evidence quotes, line numbers, findings, unknowns and
  prioritized recommendations. Hard fit reuses the real gate diagnostically and
  never filters the Resume Studio result.

Not yet built: the full no-AI tailoring workflow, side-by-side approval diff,
owner-template DOCX/PDF export and durable background jobs. Future tailoring
may only reorder or reword verified facts and must never invent experience.

### Alerting, time and privacy

Alert email is one message per completed Pull, not one email per job. Delivery
uses Resend only when configured. Missing mail configuration must be reported
honestly and must not block discovery. Email clients are not browsers, so email
markup and text need their own tests.

Instants are stored in UTC. Every human-facing date is formatted in the owner's
configured display timezone. Historical CSV drift proved that UTC storage and
local calendar dates are separate concerns.

The public repository must never contain real resumes, answer values, owner
email, phone, profile photo, application text, employer screenshots, database
dumps, tokens, secrets or session cookies. Fixtures are fictional. Extension
diagnostics carry no answer values. Private reports and artifacts stay ignored.

### Testing and operational doctrine

Durable rules learned from prior incidents:

1. Verify the running system, database and exact commit. A local build or Git
   push is not a deployment.
2. Build every affected image before `up`. Containers bake source; a host-side
   edit does not change a running image. Build `migrate` when an approved schema
   release needs it. A schema-free API/web release uses `--no-deps` and does not
   run migration or recreate unrelated services.
3. Use `docker compose --env-file .env` with the Oracle compose file. Omitting
   it once substituted blank database variables and began recreating services.
4. Do not run `docker compose down`, remove volumes or recreate the scheduler
   during an ordinary web/API release.
5. Production mutations, migrations, deployments, scheduler changes, DNS,
   extension publication and destructive data work need explicit owner approval
   for that operation.
6. Tests against live servers must wait for committed writes and must not wait
   on a stale UI flag. Restarting a server mid-browser-suite invalidates the run.
7. Never guess which rows are test data. Use isolated fictional databases.
8. An unpacked extension must be reloaded at `chrome://extensions`, then target
   employer tabs must be refreshed or reopened.
9. Use exact source/time-window parity rather than aggregate reassurance.
10. Every found bug receives a regression test that reproduces its real shape.

Current validation families include backend unit/integration tests, Next.js
TypeScript and ESLint, production build, Playwright with fictional data,
extension matcher and memory tests, Chrome-extension browser tests, forbidden
dash scans, migration rehearsal, private inventory checks and production health
verification. Report actual results and distinguish local fixtures from live
production evidence.

### Historical failures that define current safeguards

- Bare `US`, city-only locations and country/state code collisions caused false
  location decisions. Boundary-aware parsing and country expansion now have
  corpus tests.
- Experience extraction once ignored intervening words and range ceilings.
  Open-ended minimums and bounded ranges now have separate semantics.
- A structured contract flag was discarded before persistence and omitted from
  content hashing and a backfill reconstruction. Eligibility-relevant fields
  must cross every persistence and reconstruction boundary.
- Double-encoded HTML entities hid requirements from phrase rules. All adapters
  share fixed-point decoding; do not add another hand-rolled decoder.
- One incomplete paginated response could have closed hundreds of jobs. Partial
  snapshots are never authoritative.
- Repeated restarts caused a shared ATS edge to refuse ACE. Restarts resume
  persisted schedules and refusals back off.
- Waiting for the slowest source delayed every other source. Slow workers now
  continue without holding the scheduling loop.
- A `varchar(500)` location failed a whole board. Do not truncate meaning-bearing
  source data.
- Feed coverage once prevented direct-board coverage, and an aggregator returned
  only its own links. Reachability and ownership of the apply URL are separate
  checks.
- URL normalization once removed Greenhouse job IDs in query parameters and
  confidently matched the wrong application. Remove only known tracking
  parameters; ambiguity is safer than a false identity.
- Marked pages once inherited PASS and active-only filters, hiding the owner's
  history. User-owned marks bypass those discovery filters.
- A UI held several copies of one job and updated only one, so Applied looked
  unsaved until refresh. Mutations must update every cache surface or invalidate
  a shared source of truth.
- Resume scores were written only on upload and silently went stale. Event-driven
  bounded scoring now handles new jobs, changed content, changed rules and changed
  algorithms.
- Source counts and activity labels repeatedly described new jobs as all jobs
  checked. Metric labels must match the exact query population.
- Browser fixtures once tested a substitute instead of the real extension.
  Extension tests must load the actual manifest and content scripts.
- Real forms exposed custom widgets, repeating blocks, delayed fields, phone
  country ordering and multi-page navigation. The employer DOM, not a generic
  form model, is the specification.
### Known limitations and future work

- Both discovery systems are intentionally independent today. Application state
  entered in ACE Next does not synchronize back to legacy.
- Offsite Object Storage backup is not configured; backups on the Oracle VM do
  not protect against loss of that VM.
- Some sources refuse home or cloud access, and no bypass is permitted.
- Borderline source and job behavior can change as providers alter undocumented
  APIs. Coverage audits remain continuous work.
- Production V4 Memory status needs read-only verification.
- Recheck branch and remote before each change; the earlier divergence was
  reconciled and the 2026-10-25 Analytics release preserved both speed commits.
- Actual submitted resume versions, application channels and complete response
  observation coverage are not stored. These remain unavailable, not inferred.
- Production had zero Gmail connections and zero petition reports at the
  Analytics release. Live mailbox sync, actual official evidence imports,
  signed-in production visual review and final owner visual acceptance remain
  outstanding. No OAuth consent or import is authorized by this documentation.
- Browser validation on this laptop is suspended until cooling is fixed. The
  successful fictional Analytics captures and test logs are already retained;
  do not repeat heavy Chrome runs merely to refresh documentation.
- Resume Studio tailoring and export remain later scope.
- The SDE II profile remains off until the owner approves its dry run.
- Post-launch retention is designed but must not run until backup, restore,
  closure detection, tombstones, rollups and protected-job predicates are all
  proven.

## Code-verified implementation map

This section is the implementation index a new chat should use before touching
code. It was reconciled against the repository on 2026-10-25. It records the
important boundaries and contracts without copying secrets or private rows.

When facts conflict, use this order:

1. The owner's newest explicit instruction controls product intent and
   authorization.
2. The current working tree, migrations and tests control implementation facts.
3. The newest dated, independently verified entry in this file controls claims
   about production state.
4. Older sections and archived topic documents are historical evidence only.

Never infer that code is deployed because it exists locally, that a migration
ran because its file exists, or that production is healthy because an older
check passed.

### Repository and technology map

The repository is one product with four execution surfaces:

```text
backend/                 Python domain logic, scheduler and FastAPI
backend/migrations/      Alembic schema history 0001 through 0050
web/                     Next.js App Router owner website
extension/               Manifest V3 Chrome autofill extension
deploy/oracle/           production Compose, Caddy, backup and parity tools
scripts/                 repository-wide validation helpers
design/                  approved website and extension visual evidence
docs/                    historical plans, audits and incident evidence
```

The core runtime technologies are PostgreSQL 16, SQLAlchemy, Alembic, FastAPI,
Uvicorn, Next.js 16.4.2, React 19.2.8, TypeScript 5, Tailwind CSS 4, Playwright
1.56, Chrome Manifest V3, Docker Compose and Caddy. Python dependencies are
pinned in `backend/requirements.txt`; frontend dependencies and commands are in
`web/package.json`. Do not introduce another framework for an existing layer
without a product-level reason.

### Backend layers and ownership

The backend is organized by responsibility:

- `backend/app/adapters/` contains provider readers for Amazon, Apple, Ashby,
  Atlassian, Avature, ByteDance, Eightfold, Eightfold PCSX, Gem, Google,
  Greenhouse, IBM, Jibe, Lever, Oracle Recruiting, RippleMatch, Shopify,
  Simplify, sitemap jobs, SmartRecruiters, Workable and Workday. Shared HTML
  text decoding, conditional HTTP cache and retry behavior also live here.
- `backend/app/discovery/` detects boards, follows approved feed links, defines
  providers and the watchlist, and registers discovered sources.
- `backend/app/scheduling/` owns the source catalog, registry, dispatch,
  due-time runtime and one-source poll service. It does not own provider parsing
  or eligibility policy.
- `backend/app/workflows/source_snapshot.py` connects authoritative snapshot
  persistence to deterministic evaluation.
- `backend/app/persistence/` owns hashing, stable openings, source lifecycle,
  Pull sessions, evaluation materialization and repository operations.
- `backend/app/evaluation/` owns the eligibility decision and alert freshness.
  `backend/app/intelligence/` owns role, company and eligibility vocabulary.
- `backend/app/matching/` parses requirements, recognizes skills and computes
  resume scores. `backend/app/applications/` owns application import matching,
  prior-application evidence and application service behavior.
- `backend/app/coverage/` audits employer coverage, cadence, reachability,
  probing, diagnosis and safe recovery.
- `backend/app/verification/` records employer-page evidence without bypassing
  refused sources.
- `backend/app/auth/` owns password security, sessions, CSRF, Google owner
  identity, avatar processing and request guards.
- `backend/app/inbox/` owns Gmail read-only access (`gmail.py`), conservative
  evidence reconciliation (`reconcile.py`) and the safe rebuilt email shown in
  Inbox (`display.py`). `backend/app/intelligence/` also supplies combined
  dashboard aggregates and action vocabulary.
- `backend/app/studio/` owns resume documents, facts, sections, versions,
  legacy bridging and deterministic ATS assessments.
- `backend/app/answers/`, `alerts/` and `mail/` own answer catalogue behavior,
  Pull alert composition and Resend delivery respectively.
- `backend/app/api/main.py` contains the established jobs, marks, resumes,
  answers, history, coverage and source endpoints. `backend/app/api/routers/`
  contains Analytics, auth, Pulls, Studio, company intelligence, dashboard, inbox,
  owner export and system routes. The combined intelligence router behind Career
  Dashboard was removed on 2026-10-26.
- `backend/app/db/models.py` is the ORM schema map. `db/session.py` creates
  sessions and `db/base.py` defines shared SQLAlchemy metadata.
- `backend/scripts/` contains explicit operational and audit entry points. A
  script is not automatically scheduled merely because it exists.

One-source polling follows this transaction boundary:

```text
fetch external source with no database transaction held
                    |
                    v
begin one database transaction
                    |
                    v
reconcile source and posting lifecycle
                    |
                    v
evaluate changed jobs and materialize read models
                    |
                    v
commit, then expose through FastAPI
```

A conditional `not modified` result advances source success state and confirms
the previous full count without re-evaluating unchanged rows. A failed or
partial fetch never becomes an authoritative empty snapshot. The runtime uses
bounded concurrency of six, keeps slow workers alive across cycle boundaries,
prevents a source from running twice, serializes shared Eightfold edges, checks
in-flight work frequently, runs maintenance every six hours and exponentially
backs off refusal statuses 401, 403, 405 and 429 up to six hours.

### HTTP, authorization and request boundaries

FastAPI is the authorization authority. In production `ACE_AUTH=required`.
`/healthz` and the explicit sign-in/setup flows are the narrow exceptions;
private product routes require either the owner's browser session or an API
token whose scope permits that route. `ACE_AUTH=disabled` is a local/private
rollback mode with network-origin safeguards, not a public no-auth mode.

Browser authentication uses an opaque session cookie whose token is stored
hashed in PostgreSQL. Mutations also require the per-session CSRF value. The
browser client reads the CSRF cookie and sends it as `X-CSRF-Token`. Passwords
use Argon2id. Login, reset and email-change codes are hashed, expiring, single
use and rate limited. Extension tokens are separate, revocable and
least-privilege. Google owner sign-in and Gmail read-only consent are separate
OAuth grants and must never reuse each other's token or scope.

Server-rendered Next.js reads forward only the owner session cookie to FastAPI,
use `cache: no-store`, and redirect a 401 to sign-in with the original safe
destination. Browser mutations use the same-origin `/api/*` proxy. That proxy
reads `API_ORIGIN` at request time, forwards method, query, safe headers and
body, strips hop-by-hop headers, preserves multiple `Set-Cookie` values and
returns an honest 502 when FastAPI is unavailable. This runtime proxy avoids a
previous build-time origin bug and means the browser needs no CORS exception.

### Complete backend API inventory

The endpoint inventory below is code-verified. `/api/studio` is the router
prefix for every Studio suffix listed in its row.

| Domain | Method and path | Purpose |
| --- | --- | --- |
| Health | `GET /healthz` | Process and dependency health suitable for service checks. |
| Root | `GET /` | Redirects to the website entry surface. |
| Jobs | `GET /api/jobs`, `GET /api/jobs/{job_id}` | Filtered paginated listings and one durable job detail. |
| Jobs | `GET /api/facets`, `GET /api/stats` | Facet counts and real aggregates over the same filters. |
| Pulls | `GET /api/sessions`, `GET /api/pulls` | Legacy session list and the truthful Pulls read model. |
| Resume | `GET /api/resume`, `POST /api/resume` | Active legacy resume metadata/text path and upload. |
| Marks | `GET /api/marks`, `PUT /api/marks/{job_id}` | Counts and partial saved/review/applied/status/note mutation. |
| Applications | `GET /api/applications/external`, `GET /api/applications/export.csv` | External history and CSV export. |
| Legacy import | `POST /api/applications/preview`, `POST /api/applications/import` | Preserved API compatibility; no current spreadsheet UI. |
| Answers | `GET /api/answers`, `PUT /api/answers` | Whole owner answer bank. |
| History | `GET /api/history/{kind}`, `PUT /api/history/{kind}` | Ordered work or education history. |
| Sources | `GET /api/coverage`, `POST /api/sources` | Coverage read model and owner-requested source discovery. |
| Memory | `GET /api/extension/memory`, `PUT /api/extension/memory` | List and create/update reusable extension memories. |
| Memory | `DELETE /api/extension/memory/{memory_id}`, `POST /api/extension/memory/{memory_id}/used` | Delete or record use of one memory. |
| Auth | `GET /api/auth/status`, `POST /api/auth/setup` | Auth mode, owner/session state and first owner setup. |
| Auth | `POST /api/auth/login`, `POST /api/auth/login/verify`, `POST /api/auth/logout` | Password start, email-code confirmation and session revocation. |
| Auth | `GET /api/auth/google/start`, `GET /api/auth/google/callback` | Owner-only Google OpenID Connect. |
| Account | `GET /api/auth/account`, `PATCH /api/auth/account` | Owner profile read/update. |
| Account | `GET /api/auth/account/avatar`, `PUT /api/auth/account/avatar`, `DELETE /api/auth/account/avatar` | Private processed owner avatar. |
| Account | `POST /api/auth/account/email/start`, `POST /api/auth/account/email/confirm` | Password-protected verified email change. |
| Security | `GET /api/auth/sessions`, `POST /api/auth/sessions/revoke-others`, `POST /api/auth/password` | Session inventory, revoke others and password change. |
| Recovery | `POST /api/auth/reset/request`, `POST /api/auth/reset/confirm` | Email-code password recovery. |
| Pairing | `POST /api/extension/pairing`, `POST /api/extension/pair` | Create and redeem a short-lived extension pairing code. |
| Pairing | `GET /api/extension/tokens`, `DELETE /api/extension/tokens/{token_id}` | List and revoke extension tokens. |
| Company | `GET /api/companies`, `GET /api/company-intelligence`, `GET /api/company-intelligence/batch` | Company lists and evidence-backed company intelligence. |
| Dashboard | `GET /api/dashboard` | Preserved discovery/resume-fit/application aggregate used by the former Analytics page. |
| Analytics | `GET /api/analytics` | Read-only submission-date/role-filtered application metrics, evidence, rejected companies, official petition series and exact paginated drilldowns with `records=1` (searchable with `q`). |
| Inbox | `GET /api/inbox/connection`, `PATCH /api/inbox/connection`, `DELETE /api/inbox/connection` | Gmail connection state, settings and disconnect. |
| Inbox | `GET /api/inbox/google/start`, `GET /api/inbox/google/callback` | Separate Gmail read-only OAuth. |
| Inbox | `POST /api/inbox/sync`, `POST /api/inbox/backfill` | Owner-triggered incremental sync and historical import (clear rejections recorded; other outcomes wait). |
| Inbox | `GET /api/inbox/messages`, `GET /api/inbox/applications`, `GET /api/inbox/events` | Evidence (views incl. `auto` and `recruiting`, search `q`, `latest_received_at`), reconciled applications and event ledger. |
| Inbox | `GET /api/inbox/messages/{message_id}` | One imported email, for deep links. |
| Inbox | `GET /api/inbox/messages/{message_id}/full` | The email read live from Gmail and never stored: its rebuilt HTML `document` for a sandboxed frame, plus text and headers. |
| Inbox | `POST /api/inbox/recheck` | Re-decide waiting email and ACE-filed receipts read under an older parser version, 25 to 50 at a time. |
| Inbox | `PATCH /api/inbox/messages/{message_id}/decision`, `PATCH /api/inbox/automation` | Receipt, status update, unrelated or later; tightly gated positive-outcome automation. |
| Inbox | `POST /api/inbox/review`, `POST /api/inbox/events/{event_id}/undo` | One-click owner outcome (with the email kind) or undo one event; undo returns the email to the queue. |
| Inbox | `DELETE /api/inbox/snippets` | Purge retained message snippets. |
| Studio | `GET /api/studio` | Resume Studio overview. |
| Studio | `POST /api/studio/documents`, `GET /api/studio/documents/{document_id}`, `GET /api/studio/documents/{document_id}/file` | Upload, inspect and privately download original documents. |
| Studio | `GET /api/studio/facts`, `POST /api/studio/facts`, `PATCH /api/studio/facts/{fact_id}`, `GET /api/studio/facts/{fact_id}/history` | Fact ledger and audit history. |
| Studio | `GET /api/studio/versions/{version_id}`, `POST /api/studio/versions`, `POST /api/studio/versions/{version_id}/primary` | Resume versions and primary selection. |
| Studio | `POST /api/studio/check`, `GET /api/studio/assessments`, `GET /api/studio/assessments/{assessment_id}` | Deterministic ATS assessment creation and history. |
| Export | `GET /api/export.json` | Owner data export. |
| System | `GET /api/system` | Safe operational state for owner UI. |

Interactive API docs are off by default through `API_DOCS=false`. Do not expose
them merely for convenience in production.

### Database schema and durable ownership

All current ORM models live in `backend/app/db/models.py`. The important table
contracts are:

| Table | Durable responsibility |
| --- | --- |
| `jobs` | Stable source identity, company, requisition, title, location, description, official URL, posting/update times, employment type, content hash, first/last seen, active/closed state and Pull association. |
| `source_states` | Per source/account initialization, last success, count, ETag, Last-Modified, unchanged state and last full fetch. |
| `job_sources` | Configured source type/account/host/company, enabled state, interval, discovery provenance and verification timestamps. |
| `job_evaluations` | One materialized decision per job with PASS/REJECT state, family, priority, rule version, reasons, experience evidence, early-career/new-grad flags, verification and input hash. |
| `resumes` | Legacy resume bytes/text metadata, content hash, skills, active flag and upload time. |
| `job_resume_scores` | Job/resume score, matched/missing/related skills, previous score, algorithm version and score time. |
| `poll_sessions` | Pull start/activity, discovered and qualifying counts, boards/postings checked, raw attempts/failures, notification and alert state. |
| `job_marks` | Saved, review, applied, application status, timestamps and owner note for a stored job. |
| `external_applications` | Applications with no attached posting, including company/title matching key, applied date, status, URL and timestamps. |
| `application_events` | Append-oriented status evidence with previous/new value, actor, reason, Gmail link, undo and dedupe metadata. |
| `gmail_connections` | Encrypted Gmail grant state, cursor and owner-controlled automation settings. |
| `gmail_messages` | Deduplicated message evidence and review state. |
| `company_petition_reports` | Reviewed USCIS employer petition evidence, never guessed workforce sponsorship. |
| `application_answers` | Ordered answer bank entries and precise screening fields accumulated through migrations. |
| `extension_answer_memory` | Revisioned reusable question concept, answer, type, source context, use count and timestamps. |
| `history_entries` | Ordered work and education blocks used by the extension. |
| `source_probes` | Reachability and diagnostic probe history. |
| `employer_page_readings` | Employer-page verification evidence. |
| `users` | Single owner identity, profile, avatar, password hash, role and optional bound Google subject. |
| `auth_sessions` | Hashed browser sessions, CSRF material, expiration, activity and revocation. |
| `api_tokens` | Hashed, scoped, revocable extension tokens. |
| `auth_codes` | Hashed login, reset and email-change codes with expiration and consumption. |
| `login_attempts` | Persistent throttling evidence. |
| `resume_documents` | Original Resume Studio uploads and extracted metadata/text. |
| `career_facts` | Suggested, verified or retired career facts separate from resume prose. |
| `career_fact_events` | Fact audit ledger. |
| `resume_versions` | Versioned resume text and primary status. |
| `resume_assessments` | Deterministic job/resume assessment results and evidence. |

Stable job identity is the unique source tuple, never the integer `jobs.id`.
User-owned application, auth, resume and answer tables are protected state and
must not be regenerated during a discovery backfill. Evaluation and score rows
are derived, but their version and input hashes must remain reproducible.

### Complete migration ledger

Alembic history is additive from 0001 through 0050:

- 0001 jobs/source state; 0002 notification outbox; 0003 job sources; 0004
  source host; 0005 notification digests.
- 0006 evaluations; 0007 early-career flag; 0008 requirements verification;
  0009 resume matching; 0010 source HTTP cache; 0011 wider job identity; 0012
  last full fetch.
- 0013 Pull sessions; 0014 related-skill credit; 0015 marks; 0016 previous match
  score; 0017 application status; 0018 external applications.
- 0019 answers; 0020 extended answers; 0021 answer ordering; 0022 relocation and
  onsite answers; 0023 employment type; 0024 standard answers; 0025 normalized
  choice answers; 0026 work/education history.
- 0027 source probes; 0028 new-grad flag; 0029 Pull notification time; 0030
  PayPal answers; 0031 company/title index; 0032 unbounded job location; 0033
  employer-page readings; 0034 posting-link index; 0035 Pull check counts; 0036
  locale-independent posting-link index; 0037 Pull alert state.
- 0038 owner authentication; 0039 Resume Studio; 0040 Pull telemetry; 0041
  Google owner identity; 0042 Pull telemetry repair; 0043 owner display name.
- 0044 combined intelligence evidence; 0045 precise screening answers; 0046
  precise Workday answers; 0047 Meijer Workday answers; 0048 Verizon Workday
  answers; 0049 owner profile; 0050 extension Answer Memory.

The latest production schema recorded in this file is 0050, printed by the
owner's speed release and verified again read-only during the Analytics release
on 2026-10-25. All four existing Inbox/petition tables were present. Analytics
added no schema or migration. A local migration file is never proof of what
production runs. Always read `alembic_version` before planning a migration,
rehearse from a current backup, and follow the safe migration procedure later
in this file.

### Frontend architecture and current route map

The website is a server-first Next.js App Router application. Page modules
perform authenticated no-store reads on the server. Interactive client
components use the same-origin API proxy for mutation. Shared types and helpers
live under `web/src/lib/`; reusable UI and behavior live under
`web/src/components/`.

This repository uses Next.js 16.4.2, whose APIs and conventions may differ from
older model knowledge. Before frontend implementation, read `web/AGENTS.md` and
the relevant installed guide under `web/node_modules/next/dist/docs/`. Preserve
the generated Next.js instruction block in `web/AGENTS.md` because the dev
server will restore it.

Current page routes in code are:

- Public and auth: `/`, `/login`, `/login/reset`, `/logout`, `/signed-out`,
  `/privacy`, `/terms` and the web `/healthz` route.
- Daily workspace: `/app` redirects to the authenticated home, `/app/pulls`,
  `/app/opportunities`, `/app/jobs/[id]`, `/app/applications`,
  `/app/analytics`, `/app/applications/analytics` and
  `/app/applications/inbox`. `/app/dashboard` only redirects to Analytics.
- Career tools: `/app/resume-studio`, `/app/resume-studio/check`,
  `/app/resume-studio/documents`, `/app/resume-studio/documents/[id]`,
  `/app/resume-studio/facts`, `/app/resume-studio/history` and
  `/app/resume-studio/history/[id]`; `/app/extension`, `/app/answers`,
  `/app/insights/skills` and `/app/archive`.
- Supporting state: `/app/saved`, `/app/company/[name]`, `/app/coverage`,
  `/app/settings`, `/app/more` and `/app/sign-out`.

The actual sidebar order is Pulls, Opportunities, Applications, Analytics
and Inbox Intelligence; then Resume Studio, Autofill Extension
and Archive; then Coverage and Settings. Pulls remains the authenticated home.
Opportunities also owns job details and Saved navigation state. Resume Studio
owns skill insights. Extension owns Answers.

Key frontend boundaries:

- `components/shell/AppProvider.tsx` owns Day/Night/System theme persistence,
  mark counts, optimistic application transitions, per-job mutation guards,
  route-local job patches/hiding, toasts and undo, Answers dock/menu state,
  cross-tab `BroadcastChannel` refresh, focus/visibility refresh, desktop Pull
  notifications, browser timezone persistence, legacy hash job redirects and
  the runtime visible-dash guard.
- `components/shell/nav.ts`, `Sidebar.tsx`, `Topbar.tsx` and `Live.tsx` own the
  workspace shell. Do not duplicate navigation arrays in pages.
- `components/jobs/JobListPage.tsx`, `JobTable.tsx`, `ListControls.tsx`,
  `JobDetail.tsx` and `useMarks.ts` own the shared job/application list and
  mutation experience.
- `lib/listState.ts` is the single parser/serializer for filters, at most three
  sort keys and pagination. State lives in the URL so bookmark, Back and
  refresh preserve the exact view. Defaults are new grad first, unapplied first
  and best match. Marked pages bypass the recent-only housekeeping filter.
- `proxy.ts` records visits separated by at least 30 minutes, forwards the
  current safe destination and previous-visit time to server components, and
  supports `New since your last visit` without a client-only race.
- `components/pulls/` owns the timeline/log; `components/studio/` owns Studio;
  `components/inbox/` and `components/intelligence/` own the evidence and
  dashboard surfaces; `components/auth/` owns all public authentication states.
- `components/analytics/`, `lib/analytics.ts` and the Analytics route stylesheet
  own the approved four-tab page and its refresh/filter/chart behavior. They
  read the shared backend projection and do not own another mutation ledger.
- `lib/api.ts` is the server read client. Browser mutation helpers attach CSRF,
  parse structured failures and redirect cleanly on session loss.

Never add a second local state copy for application counts without updating the
shared mutation contract. A successful mark must settle against the server;
failed optimistic changes must roll back; all tabs must converge.

### Approved Analytics implementation contract

Analytics is a separate read projection. It replaced Career Dashboard, which
the owner removed on 2026-10-26 together with `/api/intelligence` and its action
queue. The Analytics change did not modify the extension, authentication,
discovery, scheduler or migrations. Since 2026-10-26 the projection also
returns `rejected_companies` (every employer with a recorded rejection in the
selection: rejections, applications there, latest dated rejection or null,
dated count, rejected roles and applications still in progress there, newest
dated rejection first) and `rejection_summary`, shown as "Rejected companies"
on the Companies tab.

| Tab | Implemented modules and accuracy rules |
| --- | --- |
| Overview | Submission timeline, current-week submissions, current application statuses and verified outcome evidence. Historical event types and latest status are separate measures. |
| Outcomes | Exact heading `Applications old enough to evaluate`, 30-day observation explanation, confirmed/pending/unknown cohorts, response timing and Inbox evidence review. Unanswered applications stay pending. |
| Role and resume | Outcomes by recorded role family, actual submitted-resume attribution, captured channels and comparable combinations. Missing attribution is `Not recorded`; combinations remain unavailable without at least five age-qualified applications per combination, complete attribution and comparable evidence. |
| Companies | Companies in application history, employer outcome history, official employer-year petition evidence, trends, source-linked evidence and authentic icons. Missing evidence remains unavailable. Historical petitions do not establish current hiring, sponsorship for an opening or new graduate eligibility. |

Read-model and filtering rules:

- `backend/app/api/routers/analytics.py` reuses Inbox `_identities`: `job:<id>`
  for applied marks and `external:<id>` for existing external records. It never
  fuzzy-merges separate applications or drops closed/now-ineligible marked jobs.
- `GET /api/analytics` is authenticated and no-store. Query parameters include
  `days=14|30|90|all|custom`, `start`, `end`, `family`, `tz` and `company`.
  The normal default is 30 days. Custom requires both dates. Invalid timezone,
  reversed/future dates and ranges over 100 years return 422.
- Date filters describe submission dates in the display IANA timezone, not
  response dates. Role families come from existing applied-job evaluations;
  missing role attribution remains Unknown. All-time totals include undated
  history, with explicit disclosure; undated applications do not enter dated
  series or age-qualified cohorts.
- Current-week activity always means the current local Monday through Sunday
  week, including when viewing another historical range. Future days are zero.
  The role selection still applies. Its drilldown uses exact Monday-to-today
  custom bounds. Lifetime Applied remains owned by the existing shell.
- The timeline uses daily points for selections under 100 days and monthly
  points for longer ranges. Daily charts can display daily or 7-day totals.
  Tab, dates, role, company-evidence selection and interval are URL-backed.
- `records=1` on the same endpoint returns exact unique application rows and
  `record_total`, default 50/max 100 per page. Additional filters are `status`,
  `company`, `evidence=positive|rejection|online_assessment|interview|response`,
  `eligible=1`, `timed=1`, `offset` and `limit`. The company parameter selects
  the sponsorship panel in the normal projection and filters rows in records
  mode. It does not silently filter the other normal Analytics metrics.
- `/app/applications/analytics` shares that projection and preserves timezone
  in its URL. Charts, metrics, cohorts, status, role and company links open the
  matching selection. Stored jobs link to their existing application controls;
  external history stays read-only. Original Applications mutations, lifetime
  counts, filters and full-history CSV remain intact.
- `AnalyticsRefresh` listens to the existing settled `ace-marks`
  BroadcastChannel, focus and visibility events and refreshes the server read.
  It creates no second optimistic count, competing ledger or background sync.

Evidence rules:

- Only owner-confirmed and `verified_automation` events contribute. Undo removes
  the original event. Preview, review, unsupported actors, future events and
  events preceding submission are excluded. Duplicate event types count once
  per application. Automatic submission receipts are not meaningful replies.
- A Gmail message must have one non-undone application target, match its
  selected identity and have a manual/automatic decision. Competing targets
  exclude it even if the other application is outside the selected date range.
- Existing owner-confirmed legacy stages remain evidence without invented
  response timestamps. A screening stage explained by an assessment or other
  positive event does not manufacture another recruiter reply. A standalone
  screening fallback is labeled screening.
- Cohort partitions are disjoint: confirmed positive, confirmed rejection,
  pending and other/unknown. A later explicit rejection takes precedence in the
  cohort partition; the event chart may still show its earlier positive reply,
  with the overlap explained. Withdrawn applications with no outcome sit in
  other/unknown. No reply stays pending at every age.
- Response timing uses the first reliable dated outcome after submission.
  Missing timestamps produce no invented duration. Rates remain null because
  the schema has no complete observation-coverage attestation. A connection,
  successful sync or single event cannot establish a complete denominator.
- Submitted resume versions and channels are absent from the schema. Never
  assign today's primary resume to history, infer channel from an ATS/provider
  or sender, rank unknown combinations or imply causal resume effectiveness.
- Inbox links use `decision=review|exact_preview|ambiguous`. Filtering happens
  before the existing 100-message limit so older pending evidence is reachable.
  Ambiguity means multiple candidate application keys, not a guessed match.
  Conservative reconciliation, review/corrections, audit and undo are preserved.
  Reading Analytics never authorizes Gmail, starts sync or changes permissions.

Company evidence and Pulls:

- Company identities remain exact strings. Reviewed records require verified
  legal-entity mapping and official HTTPS source hosts: `uscis.gov`,
  `www.uscis.gov`, `dol.gov`, `www.dol.gov` or `flag.dol.gov`. USCIS I-129
  metrics additionally require a USCIS host. The UI links stored reviewed
  evidence; it does not scrape/import sponsorship data during a page read.
- A newer revision replaces the earlier entity/metric/fiscal-year record.
  USCIS approvals and denials must both be known and nonnegative. If any
  included legal entity has incomplete year counts, that company-year aggregate
  is suppressed. A zero denominator has no rate. DOL LCAs remain a different
  metric; neither measure is hires, total employment or new graduate policy.
- Eleven official-site favicons are cached locally: Google, Apple, Microsoft,
  Stripe, Amazon, NVIDIA, Adobe, IBM, Salesforce, Meta and ServiceNow.
  `web/public/company-logos/provenance.json` records official source URLs,
  verification date and SHA-256. Exact reviewed names select an asset. Unknown
  identities and failed images use a neutral monogram, including failures that
  occur before React hydration. No runtime third-party logo lookup discloses
  the owner's application history.
- Pulls uses the same icons beside prominent company names and retains
  company-first/role-second ordering. Its calendar sits above both unchanged
  original right-side cards. Date links preserve the Pulls filter; Today resets
  the visible month; future dates are unavailable. Existing metrics, polling,
  monitoring, expansion and application controls remain.

Implementation files:

| Path | Responsibility |
| --- | --- |
| `backend/app/api/routers/analytics.py`, `backend/app/api/main.py` | Projection and authenticated route registration. |
| `backend/app/api/routers/inbox.py` | Review filtering before the message limit. |
| `web/src/app/app/analytics/page.tsx`, `analytics.css` | Server reads, four-tab route and approved page styling. |
| `web/src/components/analytics/AnalyticsView.tsx`, `AnalyticsCharts.tsx` | Four layouts, charts, evidence states, accessible chart disclosures and links. |
| `web/src/components/analytics/AnalyticsFilters.tsx`, `AnalyticsRefresh.tsx` | URL controls and settled mark refresh. |
| `web/src/lib/analytics.ts` | Projection types and shared drilldown URL builder. |
| `web/src/app/app/applications/analytics/page.tsx`, `loading.tsx` | Exact filtered application records and route loading. |
| `web/src/components/inbox/InboxIntelligence.tsx` | Existing Inbox deep-filter UI. |
| `web/src/components/CompanyLogo.tsx`, `web/public/company-logos/` | Reviewed local icons, provenance and fallback. |
| `web/src/components/pulls/PullsCalendar.tsx`, `PullsTimeline.tsx`, `web/src/app/app/pulls/page.tsx` | Calendar insertion and icon replacement. |
| `web/src/app/globals.css` | Shared icon/calendar styling using existing theme/type tokens. |
| `backend/scripts/seed_analytics_demo.py` | Rich fictional fixture restricted to `/tmp/ace-analytics-fictional.db`; never production. |
| `backend/tests/test_analytics_read.py`, `web/tests/e2e/analytics-redesign.spec.ts`, `web/tests/e2e/marks.spec.ts` | Data invariants, visual/interaction coverage and updated marks expectations. |
| `scripts/compare_analytics_screenshots.py` | Native-size reference/capture comparisons and diagnostic differences. |

Validation and acceptance evidence:

- Initial focused backend validation passed 89 tests covering Analytics, Inbox
  reconciliation/persistence, petitions, marks, Pulls and web API. After rebasing
  onto the two speed commits, the expanded set passed 112 tests, also covering
  external applications, count-only jobs, snapshots, skills and sponsorship
  coverage. TypeScript, ESLint, Next.js build, zero-hit dash scan and whitespace
  checks passed both before release and after integration. Production shipped
  dependencies had zero reported audit vulnerabilities.
- The completed fictional Playwright run passed 45 tests in 6.7 minutes: 18
  Analytics, 20 existing combined-intelligence and 7 existing marks tests. Final
  drilldown/mobile checks also passed after evidence normalization. The initial
  interrupted run is not counted. The rebased Analytics code/styles were
  unchanged; Chrome was not rerun on the overheated laptop for deployment.
- Checks cover privacy/no-store, disconnected Gmail, deduplication, undo,
  dates/roles, exact filtered records, chart disclosures, review links, official
  logo/failure fallback, petition semantics, cross-tab marks, keyboard/theme
  controls, Pulls calendar/cards and no browser errors. Responsive checks cover
  1672, 1600, 1440, 1280, 1024 and 390 pixels, plus 836 CSS pixels as a
  200-percent reflow equivalent for the 1672-pixel reference.
- All four tabs have native 1672x941 Day/Night PNGs in the ignored directory
  `artifacts/analytics-validation/`: `light-` and `dark-` followed by
  `overview.png`, `outcomes.png`, `role-resume.png` or `companies.png`.
  Full-page variants, four mobile captures, drilldown captures,
  `comparison-contact-sheet.png`, `comparison-{tab}.png`, `difference-{tab}.png`,
  `comparison-metrics.json`, screenshot hash manifest, `playwright-final.log`,
  `playwright-drilldown-final.log` and `changed-files.txt` are retained there.
- Native screenshot dimensions and icon hashes were verified. Raw pixel error
  is diagnostic, not an acceptance percentage. Existing shell geometry, real
  counts, seven fixture role families instead of five illustrative rows,
  unavailable rates/attribution and real disconnected/evidence states explain
  intentional differences. Overview, Outcomes and Companies were refined
  against the references. No claim of identical illustrative data is made.
- The acceptance comparison is recorded in
  `docs/architecture/2026-10-25-analytics-redesign.md`. All four approved module
  compositions, functional data/filter behavior, conservative evidence,
  preserved shell/Pulls controls, themes and accessibility were locally
  verified. Owner visual acceptance, signed-in production browser rendering,
  live Gmail sync and real petition imports remain unverified/unavailable.
  No invented test fixture may be imported to make a production panel look full.
- Local API, web and temperature-watch processes were stopped after validation.
  Scratch Chrome wrappers, release/smoke scripts and the fictional database
  under `/tmp` are disposable and can disappear after reboot. Reconstruct them
  from the committed code and documented procedure rather than assuming they
  are installed tools. Production rollback metadata is retained privately on
  the VM, separately from these local scratch files.

### Gmail evidence contract

Migration 0044 added the application event ledger, Gmail connection/message
evidence and petition-report evidence. Inbox Intelligence is a current feature,
not a demo page. Career Dashboard was removed on 2026-10-26.

Gmail authorization is owner opt-in and `gmail.readonly`. It uses separate
client credentials, state, nonce, PKCE and an encrypted refresh token.
Incremental sync uses the Gmail history cursor. The owner can pause,
disconnect, purge snippets, decide an email, correct evidence and undo an
event. `backend/scripts/sync_gmail.py` is a one-shot command; this file does
not record a production timer for it.

Automatic rejections (owner decision 2026-10-26, supersedes "backfill is
preview-only" and "nothing is rejected automatically"): `backend/app/inbox/
reconcile.py` parser version 2 records a rejection without a manual step when
the newest unquoted text has explicit rejection wording plus a recruiting word
(not a withdrawal), Gmail's own DMARC result aligns with the visible sender,
the sender is not a personal mailbox, and exactly one application fits: its
job ID (labelled forms such as Ref, Req, Job ID, Requisition), its exact title
at the named company, or the only application at a company named in the
sender, subject or sender domain whose title the email does not contradict.
Two possible applications, an email more than 24 hours before the application
was marked, a final status (accepted, withdrawn, offer) or a later owner stage
send it to review instead. A rejection of an already rejected application only
adds the email's date. This applies to live sync, historical import and
`/api/inbox/recheck`. `GMAIL_AUTO_REJECTIONS=false` turns it off server-side.
Each change is a `verified_automation` event with Undo; undo returns the email
to the queue and a later recheck never repeats an undone change.

Interviews, assessments and offers keep the earlier rule: both the global
`GMAIL_AUTO_OUTCOMES_ALLOWED=true` and the connection's owner setting, a live
(not historical) import, an exact job ID and an employer-domain sender. Receipts
("thank you for applying") are filed as decision `receipt` with no status
change. Plain text is read when present, otherwise text extracted from HTML;
only the 500-character snippet is retained. Review is one click: the email is
fetched live by `/messages/{id}/full` and shown as it arrived (rebuilt by
`inbox/display.py` for a sandboxed frame with no scripts and no remote
pictures), the likeliest application is preselected, and Rejection,
Assessment, Recruiter reply, Interview, Offer, Acknowledgement, Status update,
not about applications and later are single actions. `POST /api/inbox/review`
takes an optional `kind` so an owner-chosen assessment counts as one.

Parser version 4 (2026-10-26) also reads the employer from Workday senders
(`<tenant>@myworkday.com`); other shared platforms never name one.
Parser version 3 (2026-10-26) never files an email as a receipt when it also
sounds like a decision (`possible_rejection`, waits) or when only the snippet
could be read (waits). Recheck reads waiting email and receipts ACE filed
itself again; receipts the owner filed are never re-decided. The Inbox page
checks Gmail when opened, while open (at most every 3 minutes) and on Sync now;
there is still no server timer. `last_synced_at` is the last check for new
email only.

Metrics are deliberately conservative:

- Lifetime submitted combines applied job marks and external applications
  without double counting.
- Current pending excludes Accepted, Rejected and Withdrawn.
- Response, online assessment, interview and offer require distinct event
  evidence.
- Analytics age-qualified cohorts use the exact 30-day threshold. Response
  rates additionally require complete observation coverage, which the current
  schema does not attest. The implemented Analytics rates are therefore null
  and shown as Unavailable, even when individual verified outcomes exist.
- Median response time requires reliable dated evidence.
- Qualified postings observed by ACE are not a national market rate.
- H-1B rate is shown only from verified USCIS I-129 approvals divided by
  approvals plus denials. DOL LCA counts are not USCIS petition outcomes and
  neither source proves that a specific job will sponsor.

The Analytics production check found zero Gmail connections and zero petition
reports. Live credentials, consent and sync have not been exercised. Preserve
the truthful disconnected/unavailable states; do not present these integrations
as active or populate their tables from the fictional browser fixture.

### Chrome extension implementation map

The unpacked extension consists of:

- `manifest.json`: MV3 declaration, version 1.28.0, storage/activeTab/scripting
  permissions, localhost host access and optional HTTPS host access.
- `background.js`: stores endpoint/token, pairs with ACE, performs authenticated
  answer/history/memory calls, validates message senders and brokers runtime
  messages. Secrets stay in `chrome.storage.local`, never in page DOM.
- `fields.js`: question extraction, field/control shapes, answer matching,
  employer-specific screening rules, option matching, repeating history blocks,
  date mapping, phone/country ordering and deterministic matcher utilities.
- `memory.js`: normalized concepts, equivalence and reuse policy, including the
  shared employer-motivation exclusion predicate.
- `content.js`: native and React value setters, fill planning, combobox/listbox
  and Workday adapters, undo, the Focus Mode shadow DOM UI, Review/Memory/
  Activity flows, dynamic observation, SPA quieting, diagnostics and draggable
  position behavior.
- `popup.html` and `popup.js`: ACE address, pair/unpair, answer access and manual
  injection/fill controls for the active tab.
- `test-rules.js` and `test-memory.js`: fast deterministic rule suites. Real
  Chrome interaction tests live in `web/tests/e2e/extension-*.spec.ts`.

Persistent Chrome keys currently include `base`, `token`, `aceStudioActivity`,
`aceFocusPosition`, `aceStudioThemeMode` and `aceAutoKnown`. Changing a key requires
backward-compatible read/migration behavior or an explicit owner-approved reset.
`aceStudioThemeMode` is `system`, `day` or `night`; it replaced the older
`aceStudioTheme` key, which is now ignored so every card starts by following
the computer.

The content scripts run at `document_idle` in all frames. They must use native
setters and the events expected by the employer framework, then read the real
control state back before declaring success. Field detection must handle
rerenders and step replacement without unbounded observers. Diagnostics may
describe controls and failures but never answer values. The extension can fill
and undo supported fields only. It cannot submit, irreversibly advance, infer
Applied, or own company-motivation answers.

### Deployment topology and configuration

The Oracle production Compose stack is:

```text
internet -> Caddy :80/:443 -> Next.js web :3000
                              -> FastAPI api :8000
                                       |
                                       v
                                 PostgreSQL 16
                                       ^
                                       |
                              scheduler and migrate
```

`postgres` owns the named database volume. `migrate` runs `alembic upgrade
head` as a one-shot prerequisite. `scheduler` runs the long-lived scheduler and
has a semantic health command every five minutes. `api` runs Uvicorn and has a
health check. `web` receives the release SHA as a build argument. Caddy is the
only public entry point. Services use `restart: unless-stopped` and dependency
health/completion gates. Local Compose binds PostgreSQL 5433, API 8000 and web
3000 to loopback. Production commands must include
`docker compose --env-file .env -f deploy/oracle/compose.yaml ...`.

Backend environment contract:

- Required: `DATABASE_URL`.
- Auth: `ACE_AUTH`, `SETUP_TOKEN`, `SESSION_DAYS`,
  `REQUIRE_LOGIN_EMAIL_CODE` and `WEB_BASE_URL`.
- Owner Google sign-in: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and
  `GOOGLE_REDIRECT_URI`.
- Gmail: separate `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`,
  `GMAIL_REDIRECT_URI`, `GMAIL_TOKEN_KEY` and
  `GMAIL_AUTO_OUTCOMES_ALLOWED`.
- Alerts: `RESEND_API_KEY`, `MAIL_FROM`, `ALERT_EMAIL` and `PUBLIC_BASE_URL`.
- Discovery/rendering: `MAX_ALERT_POSTING_AGE_DAYS` default 10,
  `ALERT_ON_UNKNOWN_POSTING_AGE` default false, `DISPLAY_TIMEZONE` default
  `America/Los_Angeles`, and deployment profile `ACE_TARGET_PROFILE` default
  `early-career` in the Oracle template.
- Operations: `API_DOCS`, `ACE_DOMAIN`, database name/user/password and optional
  `OCI_BACKUP_BUCKET` with `ACE_BACKUP_MAX_REMOTE_BYTES`, currently 15 GiB in
  the template.
- Frontend runtime: `API_ORIGIN` points Next.js to FastAPI. It must be supplied
  at runtime, not assumed to have been baked into the build.

Secrets stay only in the private server `.env` with restrictive permissions.
Never copy them into this knowledge file. `deploy/oracle/backup.sh`, its systemd
service/timer, release preparation, independent-discovery comparison, parity
query and disabled legacy-replica tools are operational assets. The existence
of the replica script does not authorize re-enabling replication.

### Operational scripts and verification surface

Important backend commands are intentionally explicit:

- `run_scheduler.py` and `scheduler_health.py` operate and assess discovery.
- `source_health.py`, `probe_coverage.py`, `coverage_benchmark.py`,
  `discovery_inventory.py`, `discovery_parity.py`, `discover_sources.py` and
  `discover_boards.py` measure reachability and coverage.
- `gate_dry_run.py` and `rejection_audit.py` measure eligibility changes before
  activation.
- `backfill_job_evaluations.py`, `backfill_decode_descriptions.py`,
  `backfill_resume_studio.py` and `repair_applied_date_drift.py` are controlled
  data repairs/backfills, not routine startup hooks.
- `data_inventory.py`, persistence smoke scripts and source snapshot smoke
  scripts verify database behavior without printing private content.
- `time_pages.py` times requests read-only in-process without a login session.
  Its Analytics entry calls `/api/analytics?days=30`. Inbox routes need an
  owner session, so they are not timed there.
- `create_owner.py` and `set_owner_email.py` mutate owner identity and require
  deliberate use against the intended database.
- `import_petition_reports.py` accepts only reviewed official evidence.
- `sync_gmail.py` performs a one-shot inbox sync; no production timer is
  implied.
- `legacy_replica.py` is historical. It stays inactive during independent
  comparison.

Backend tests cover every adapter family, adapter contracts, eligibility and
candidate profiles, hashing/persistence, scheduler timing and refusals,
discovery/coverage/parity, Pull telemetry, matching/scoring, application marks
and prior applications, auth and Google, Gmail reconciliation, petition data,
Resume Studio, migrations and API behavior. Frontend Playwright suites cover
auth, account/profile, navigation, responsive V2 visuals, jobs, marks,
applications, keyboard behavior, Studio, Combined Intelligence and real
extension fixtures. Extension rule and memory suites run directly in Node.

The normal validation ladder is:

```bash
.venv/bin/python -m pytest backend/tests -q
node extension/test-rules.js
node extension/test-memory.js
node --check extension/content.js
python scripts/no_user_facing_dashes.py
cd web
npm run typecheck
npm run lint
npm run build
npx playwright test
```

Choose focused tests while iterating, then expand in proportion to risk. Record
the exact command, result, fixture type and environment. A skipped live test is
not a pass. A local fictional browser fixture is not a production employer-form
verification.

### Change checklist for future chats

Before changing a subsystem, a future chat should answer all of these from this
file and the current code:

1. Which durable table, API route, page, extension message or scheduler worker
   owns the behavior?
2. Is the fact code-local, historically verified in production, or currently
   unverified?
3. Which owner safety invariant could the change affect: data preservation,
   no-submit, no-motivation capture, single-owner auth, source respect,
   independent schedulers or design fidelity?
4. Does the change require a migration, backfill, deployment, scheduler action,
   external OAuth consent or destructive operation that needs explicit owner
   approval?
5. Which focused regression reproduces the real failure shape, and which wider
   suites must still pass?
6. How will production be verified read-only after release without exposing
   private content?

Update this same file whenever an architecture contract, deployment truth,
schema head, production verification, owner decision or major remaining risk
changes. Do not create a competing continuity file.

## Repositories and runtime state

The legacy checkout is `/home/ubuntu/Documents/ace` on branch `main`. Its
Docker stack and database are preserved. As audited on 2026-10-16, before the
later independent-comparison decision:

- PostgreSQL 16 is healthy and published locally on port 5433.
- The legacy web service is available on port 8000.
- The scheduler is healthy and continues to poll.
- The database is at Alembic revision 0040.

The new checkout is `/home/ubuntu/Documents/ace-next` on branch
`wine-rose-platform`. It contains the approved Next.js interface, all existing
backend logic, Resume Studio, owner authentication, extension pairing, the
Pulls-first workspace and the Oracle deployment kit.

Do not rebuild or migrate the legacy stack during ordinary development. The
current owner decision is that both legacy and Oracle schedulers keep running,
each against its own PostgreSQL database, so their discovery results can be
compared. The databases are independent writers and their numeric IDs have
diverged. Keep the old cross-database replica cron disabled. Do not merge rows,
restart replication, or stop either scheduler without a new explicit owner
decision and a reconciliation plan.

## Historical production data inventory, 2026-10-16

The 2026-10-16 audit used aggregate read-only queries. It did not read or print
resume text, answers, emails or job descriptions.

| Data | Audited count |
| --- | ---: |
| Jobs | 811,176 |
| Active jobs | 609,186 |
| Source states | 2,226 |
| Job sources | 2,284 |
| Job marks | 995 |
| Applied job marks | 708 |
| External applications | 47 |
| Application answers | 71 |
| Legacy resumes | 5 |
| Active legacy resumes | 1 |
| Poll sessions | 2,202 |
| Users | 1 |
| Active API tokens | 0 |
| Resume Studio documents | 0 |
| Career facts | 0 |
| Resume Studio versions | 0 |

This rehearsal snapshot represents 755 tracked applications through 708
applied job marks plus 47 external application rows. This is the confirmed
historical application total to preserve and verify during cutover.

## Architecture

```text
Employer ATS and official feeds
              |
              v
  long-running scheduler
              |
              v
         PostgreSQL
       /      |       \
  FastAPI  analytics  application history
      |
      v
  Next.js server
      |
      v
  Caddy HTTPS proxy
      |
      v
 Owner browser and paired Chrome extension
```

The scheduler, API, web app and PostgreSQL share one database. Next.js forwards
same-origin `/api/*` calls to FastAPI, so the browser does not need CORS. Caddy
terminates HTTPS. Only ports 80 and 443 are public. PostgreSQL and FastAPI stay
inside Docker's private network.

Docker services use `restart: unless-stopped`. Each scheduler persists its own
source state, respects per-source intervals, backs off on refusals and resumes
from its last successful poll after a restart. Both now run against separate
databases for the owner-requested comparison; cross-database replication is off.

## Data ownership and compatibility

The following legacy tables remain authoritative and are used directly by ACE
Next:

- `jobs`, `job_sources`, `source_states`, evaluations and match scores
- `job_marks` and `external_applications`
- `application_answers` and work and education history
- `poll_sessions` and source health telemetry
- `resumes`, including all five historical rows and the active row
- owner, browser session and extension token tables

The new UI reads real API aggregates. It does not use the fictional demo counts
in production. Demo data is created only by `backend.scripts.seed_demo` in a
separate database.

Migration 0041 adds nullable `users.google_subject`. Migration 0042 repairs the
Pulls telemetry columns needed by the V2 API. Migration 0043 adds the owner's
non-null `display_name` with a safe blank default. Existing password sign-in and
all existing data remain valid when Google is not configured.

The legacy resume bridge copies every `resumes` row into a Resume Studio
document and approved master version. It preserves the text, label, timestamp
and history. The active legacy resume becomes the primary Studio version only
when no Studio primary already exists. Suggested career facts are parsed from
that active resume for owner review. The bridge does not activate another
legacy resume and does not rescore jobs. It is idempotent and can be previewed
before commit.

```bash
python -m backend.scripts.backfill_resume_studio
python -m backend.scripts.backfill_resume_studio --apply
```

## Authentication

ACE has one owner. There is no public registration and no second-user data
scope. Passwords use Argon2id. Browser sessions are stored as hashes, mutation
requests require a per-session CSRF token, login attempts are throttled, and
extension tokens can read answers and work or education history plus manage
approved Answer Memory. They cannot access jobs, applications, resumes, owner
profile or other private API families.

Password sign-in supports an optional second email step. The Oracle template
requires it, but the actual production `/api/auth/status` check on 2026-10-25
reported `email_verification: false` and `reset_by_email: false`; production
therefore accepts the password under Continue with email without an emailed
code, and email recovery is unavailable. Never infer actual configuration from
the deployment template. When verification is enabled, ACE verifies the password,
sends an eight-character one-time code to the owner's email, and creates the
browser session only after that code is confirmed. Sign-in and password reset
codes expire after 10 minutes, are stored only as SHA-256 hashes, are single
use, and have database-backed issue and guessing limits. Issuing a new code
cancels the previous live code. Password recovery asks for the email code
before accepting a new password, then revokes every existing browser session.

`REQUIRE_LOGIN_EMAIL_CODE=true` is set in the Oracle deployment template. It
makes password sign-in fail closed if Resend is unavailable or missing. Local
development can leave it false; when Resend is configured, the email step is
used regardless of this switch. This local fallback keeps fictional demo and
browser testing usable without sending real mail.

If the restored owner's email is not the desired daily login, run
`python -m backend.scripts.set_owner_email NEW_EMAIL` against the restored
target database. It renames the existing owner rather than creating another
one, preserves all product data, clears an earlier Google subject, revokes
browser sessions and consumes pending email codes. The address is deliberately
not stored in this public document.

Google sign-in uses the OpenID Connect authorization code flow. ACE requests
only `openid email profile`. The browser flow uses short-lived HttpOnly state
and nonce cookies. The API validates the Google signature, issuer, audience, expiration,
issued time, nonce and `email_verified` claim. The verified email must match the
existing active owner. The first successful login binds Google's stable
subject, and later logins must present the same subject. Google never creates
an ACE user. Google already verifies ownership of the email address, so ACE
does not send a second code after a successful Google callback. A verified
Google profile name fills a blank display name. It never changes the owner's
email or authentication scope.

#### Existing Google Console project and client, owner-confirmed 2026-10-25

The owner already has a Google Cloud project named `acee`. Their Console
screenshot shows an enabled Web application OAuth client named `acee prod`
(referred to conversationally as Ace Pro), created on 2026-10-19. Do not tell
the owner to recreate this project or replace/delete the existing sign-in client.
Its screenshot-confirmed configuration is:

- Authorized JavaScript origin: `https://ace.opik.net`.
- Authorized redirect URI: `https://ace.opik.net/api/auth/google/callback`.
- Legacy authorized redirect URI:
  `https://ace.161-153-89-170.sslip.io/api/auth/google/callback`.
- An enabled client secret exists; its value is masked in the Console and
  belongs only in private server configuration. Neither secret values nor the
  owner's Console screenshot belong in this public repository.

Those callbacks are for Google sign-in. The screenshot does not show the Gmail
callback `https://ace.opik.net/api/inbox/google/callback`, and does not establish
that Gmail API, the read-only scope, test-user access or server settings are
configured. A production presence-only check during Gmail setup guidance found
`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` and `GMAIL_TOKEN_KEY` absent, with the
Gmail callback not configured; setup readiness was false and global automatic
outcomes were disabled. No credential values were printed or configuration
changed.

Continue Gmail setup inside the existing `acee` project. A dedicated Gmail Web
OAuth client there keeps `GMAIL_*` credentials independent of the existing
`GOOGLE_*` sign-in configuration. Preserve the current sign-in client and its
callbacks, and do not change the project's publishing status merely to follow
a generic testing tutorial. Gmail consent is a separate owner action even when
the same Google Cloud project is used. No Gmail scope/configuration change is
authorized by documenting these facts.

Required cloud values:

```text
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI=https://ace.opik.net/api/auth/google/callback
WEB_BASE_URL=https://ace.opik.net
REQUIRE_LOGIN_EMAIL_CODE=true
RESEND_API_KEY
MAIL_FROM
```

Secrets belong only in the server `.env`, with mode 600. Never put them in this
file, GitHub, an issue or chat.

Sign out revokes the server session and routes to the approved signed-out page.
The Chrome extension must be paired again after moving to a different ACE
origin unless its existing token and endpoint are intentionally migrated.

## Owner identity and real Resume Studio documents

Commit `132235c` replaced the generic sidebar identity with the authenticated
owner's display name and email. Setup now requires a full name. Settings has a
real My Account form backed by `GET /api/auth/account` and
`PATCH /api/auth/account`. The sidebar reacts to that persisted account state.
An existing owner created before migration 0043 starts with a blank display
name. Enter it in Settings or complete a fresh Google sign-in to populate it.

Resume Studio no longer fabricates a paper-like preview from extracted fields.
For a stored PDF, the page loads the authenticated document-content endpoint
and embeds the actual bytes through a short-lived browser Blob URL. Content
Security Policy explicitly permits same-origin and Blob frames. DOCX and other
non-PDF files show an honest download action because browsers cannot reliably
render them without conversion. Never substitute a generated dummy PDF for a
stored source document. The preview remains protected by the existing owner
session and does not expose a storage path publicly.

Key implementation files:

```text
backend/app/api/routers/auth.py
backend/app/auth/google.py
backend/app/auth/service.py
backend/app/db/models.py
backend/migrations/versions/0043_add_owner_display_name.py
web/src/components/pages/AccountSettings.tsx
web/src/components/shell/Sidebar.tsx
web/src/components/studio/ResumeDocumentPreview.tsx
web/src/app/app/resume-studio/page.tsx
web/src/app/app/settings/page.tsx
web/next.config.ts
```

## Applications and counters

Applications use real `job_marks.applied_at` plus `external_applications`.
Marking a job Applied updates the shell counter optimistically, synchronizes
tabs, persists through the API and refresh, and rolls back if saving fails.
Analytics and Pulls totals come from backend queries over the same PostgreSQL
database.

No application spreadsheet upload is present. Historical external applications
already in PostgreSQL are preserved through database restore.

## Local commands

The legacy production stack can keep running. Use different ports for ACE Next.

Terminal 1, isolated demo API:

```bash
cd /home/ubuntu/Documents/ace-next
.venv/bin/python -m backend.scripts.seed_demo \
  --database-url sqlite:///ace-demo.db
ACE_DEMO_COMPANIES=1 DATABASE_URL=sqlite:///ace-demo.db \
  .venv/bin/uvicorn backend.app.api.main:app \
  --host 127.0.0.1 --port 18001
```

Terminal 2, new web app:

```bash
cd /home/ubuntu/Documents/ace-next/web
npm ci
npm run build
API_ORIGIN=http://127.0.0.1:18001 npm run start -- -p 3001
```

Open `http://127.0.0.1:3001`. The demo owner credentials are fictional and are
printed by the seed script. Never seed the production database.

Useful validation:

```bash
cd /home/ubuntu/Documents/ace-next
.venv/bin/python -m pytest backend/tests -q
node extension/test-rules.js
python scripts/no_user_facing_dashes.py

cd web
npm run typecheck
npm run lint
npm run build
npx playwright test
```

The latest account and real-document change passed a focused backend suite of
24 tests, TypeScript, ESLint, the production Next.js build, the source-level
forbidden-dash scan with zero hits, a disposable SQLite migration rehearsal
from 0042 to 0043, and focused Playwright runs in Night and Day. A temporary
generated PDF stored only in the disposable test database was rendered through
the real content path. Production then passed `/healthz`, container health,
schema and aggregate inventory checks.

Review screenshots are stored locally and contain no credentials:

```text
artifacts/account-resume-validation/dark/resume-studio.png
artifacts/account-resume-validation/light/resume-studio.png
artifacts/account-resume-validation/dark/settings.png
artifacts/account-resume-validation/light/settings.png
```

## Safe migration procedure

The migration has four phases.

### Phase 1: rehearsal while legacy stays live

1. Build and test ACE Next against fictional data.
2. Create a consistent PostgreSQL custom-format dump of the legacy database.
3. Restore it into an isolated PostgreSQL instance.
4. Run `alembic upgrade head` against the copy.
5. Capture aggregate inventory before and after restore.
6. Preview and apply the Resume Studio bridge on the copy.
7. Test every UI route, real totals, resume content, auth and extension pairing.
8. Perform a backup restore drill.

The 2026-10-16 rehearsal completed against a private read-only dump of the real
legacy database. PostgreSQL restored the dump without errors, migration 0041
applied, all five legacy resumes became five Studio documents and five approved
versions, one active resume became primary, and 52 suggested facts were created.
A second preview skipped all five resumes, proving idempotency. The live
scheduler remained running and wrote new rows after the dump snapshot, so an
exact comparison against a later live inventory correctly showed drift. Exact
source and target equality is checked during final cutover after the scheduler
write freeze.

After the email verification implementation, the full local validation passed:
1,191 backend tests, 89 Playwright browser tests, 185 extension matcher cases,
TypeScript, ESLint, the production Next.js build, and the source-level
forbidden-dash scan. The Playwright run used an isolated fictional SQLite
database and covered the sign-in code prompt and password reset code form.

`backend.scripts.data_inventory` writes only aggregate counts:

```bash
python -m backend.scripts.data_inventory --output /tmp/ace-before.json
python -m backend.scripts.data_inventory --compare /tmp/ace-before.json
```

The compare must run before Resume Studio backfill because that bridge is
expected to add rows to the three Studio tables.

### Historical phase 2: cloud rehearsal

Follow `deploy/oracle/README.md`. Keep the cloud scheduler stopped while the
legacy scheduler remains authoritative. Verify HTTPS, password sign-in, Google
sign-in, sign out, delivery of the password sign-in code, forgot-password code
delivery, Pulls, application counts, Analytics, Resume Studio, Answers, Settings
and extension pairing.

Before cutover, the local legacy host ran this cron every minute. It was
removed on 2026-10-23:

```text
* * * * * /home/ubuntu/Documents/ace-next/deploy/oracle/sync-legacy-replica.sh >> /home/ubuntu/.local/state/ace-legacy-replica/cron.log 2>&1
```

The replication script first copies newer user-managed application state from
cloud to legacy, then copies legacy discovery state to cloud. Timestamp guards
make newer edits win. A file lock prevents overlap, a five-minute replay overlap
covers transaction boundaries, all writes are idempotent, and the cursor moves
only after the cloud transaction commits. Relevant files:

```text
backend/scripts/legacy_replica.py
deploy/oracle/sync-legacy-replica.sh
deploy/oracle/replica-parity.psql
/home/ubuntu/.local/state/ace-legacy-replica/cursor
/home/ubuntu/.local/state/ace-legacy-replica/cron.log
```

During deployment on 2026-10-22, recreating the API container removed the
temporary `/tmp/legacy_replica.py` helper during one active sync. That run failed
safely, the cursor stayed at the prior boundary, and the next cron run replayed
the interval and advanced successfully through `2026-10-22T00:23:01Z`. This is
expected recovery behavior. In that historical replication mode, API replacement
required verifying that a subsequent log entry said
`ACE legacy replica synchronized through ...` and that the cursor advanced.
This is not an instruction to run replication now: the owner subsequently chose
independent discovery. Keep the replica disabled and never edit its cursor
forward by hand.

`replica-parity.psql` compares settled pull sessions, complete job identities,
qualifying opportunities, enabled sources and user-managed application data.
Use the same successful cursor as the cutoff on both databases and compare the
output lines exactly. Mutable job and evaluation hashes may change beyond that
cutoff while the legacy scheduler is polling.

### Safe production release during independent comparison

Production deployment requires explicit owner approval each time. Before asking
for it, commit the complete change, run applicable tests, confirm the diff does
not contain secrets or unrelated owner edits, and prepare the exact commit SHA.

After approval:

1. Push `wine-rose-platform` without force.
2. On the VM, confirm `/opt/ace` has no conflicting tracked changes. Untracked
   `private-backups/` is expected. Record current commit, API/web image IDs,
   scheduler/PostgreSQL/Caddy container IDs, schema and private aggregate
   inventory. Do not print credentials or private rows.
3. Take a fresh private consistent backup. Verify gzip integrity and PostgreSQL
   archive listing before activation. Keep previous API/web image IDs available
   for rollback. A list check is not a restore drill; do not claim one occurred.
4. Fetch and fast-forward to the exact approved SHA, preserving newer shared
   branch work. Set `ACE_BUILD_SHA` to that full SHA before image construction.
5. Build affected images. `deploy/oracle/prepare-release.sh` builds `migrate`,
   `api` and `web` without changing containers. For a schema-free API/web
   release, a direct `docker compose --env-file .env -f
   deploy/oracle/compose.yaml build api web` also prepares only what is needed.
6. For a schema-free API/web release, activate only those services with
   `docker compose --env-file .env -f deploy/oracle/compose.yaml up -d
   --no-build --no-deps --wait --wait-timeout 180 api web`. Website-only changes
   activate only `web`. `--no-deps` prevents triggering the existing migrate
   prerequisite. Do not include scheduler, migrate, PostgreSQL or Caddy merely
   because they appear in Compose dependencies. A migration needs separate
   explicit approval and the rehearsal procedure above.
7. Verify API/web are healthy, running images match the prepared IDs, public
   `/healthz` and `X-Ace-Frontend-Commit` match the approved SHA, schema is
   unchanged for a schema-free release, and scheduler/PostgreSQL/Caddy container
   IDs are unchanged. If activation fails, restore the recorded previous
   API/web image tags and prior build SHA, then recreate only API/web; never
   restore production data as an automatic application rollback.
8. Compare private aggregate inventories for protected state. Discovery can
   continue adding jobs/Pulls during a release, so those totals need not match.
   Run read-only data invariants and public auth/static-asset checks. Do not
   use mutation tests or an actual owner's browser session as fictional data.
9. Record exact evidence and unverified areas here. Do not claim that container
   health proves signed-in visuals, Gmail sync, official evidence availability
   or legacy scheduler freshness. Keep both schedulers running independently
   and the cross-database replica disabled; do not operate them to validate a
   website release. Monitoring checks may be read-only.

The Analytics release followed the schema-free path. Its protected inventory
comparison checked row counts for `job_marks`, `external_applications`,
`application_answers`, `resumes`, `users`, `resume_documents`, `career_facts`
and `resume_versions`, plus the applied-mark count. Those matched before/after.
This establishes aggregate preservation, not a full row-content hash audit.
The 919 application total is a dated snapshot, not a fixed expected total for
future releases. The Oracle scheduler was healthy and kept its container ID;
legacy health and fresh source-write parity were not rechecked in this release.

Release-script lessons from this deployment:

- When sending `bash -s` over SSH, a child `docker compose exec -T` can consume
  the script's remaining stdin. Give non-input commands `< /dev/null`; reserve
  stdin explicitly for a Python/SQL script or dump stream. A zero SSH exit code
  alone does not prove all planned commands ran. Verify expected artifacts and
  the public release SHA.
- Under `set -o pipefail`, `gzip -dc dump.gz | pg_restore --list` can exit 141
  because listing closes input before gzip finishes. First run `gzip -t` over
  the entire file. Then use Bash process substitution for archive listing,
  check the listing command succeeds and its output is nonempty, and only then
  rename the private `.partial` backup to its completed name. Do not ignore
  integrity errors or treat a partial file's existence as a verified backup.
- The ordinary backup script has retention cleanup. This release used a new
  private dump without pruning existing backups. No scheduler operation,
  cleanup, production restore or migration accompanied the deployment.
- Production data smoke checks used `SET default_transaction_read_only = on`
  on every diagnostic connection, without application startup hooks. The
  existing in-process `time_pages.py` pattern allowed a process-local auth
  override to exercise the route without creating a session or changing live
  auth configuration. Public private endpoints still returned 401. This is not
  verification of the owner's real signed-in browser.

Do not use an unversioned web image. Do not assume a Git push deployed anything.
Do not run `docker compose down`, remove a volume, restore a dump, downgrade a
migration or alter the legacy stack as part of a normal frontend release.

### Historical phase 3: temporary cutover on 2026-10-23, then reversed

The existing cloud database had been continuously replicated and already
included the cloud-only owner and Resume Studio data. Cutover used a verified
cloud backup and isolated restore drill, disabled the minute cron, stopped the
legacy scheduler, ran one final sync, repaired the 3,300 stale source-update
timestamps, confirmed parity, then started the cloud scheduler. The legacy
database remained intact. No full restore was applied over the live cloud
database. The owner then clarified that both discovery systems must stay active
for comparison. The legacy scheduler was restarted, Oracle was restarted, and
the replica cron remained disabled because both databases now contain
independent discovery writes.

### Phase 4: rollback if required

Both systems currently discover independently. Any future switch to one writer
requires deciding how to reconcile job identities, Pull sessions, source state,
and application changes made in either database. Never re-enable the old
ID-based replica cron in independent-discovery mode. Its stale source-update
selection rule also needs repair before any future use.

## Oracle Free Tier operation

The production compose file is `deploy/oracle/compose.yaml`. It runs PostgreSQL,
one migration job, the scheduler, FastAPI, Next.js and Caddy. Full setup,
firewall, restore, Google and backup instructions are in
`deploy/oracle/README.md`.

Oracle's current Always Free documentation allows eligible Ampere A1 compute
within monthly OCPU and memory limits. The planned two OCPU and 12 GB VM fits
those published limits. Oracle may reclaim an idle free instance. Keep daily
backups and verify restores. The account owner must confirm every resource in
the Oracle console is labeled Always Free or Always Free eligible before
creation. Do not enable paid upgrades, paid load balancers or paid databases.

The backup script is `deploy/oracle/backup.sh`. It writes a mode 600 PostgreSQL
custom dump compressed with gzip, retains 14 days locally and can upload to a
private OCI Object Storage bucket when `OCI_BACKUP_BUCKET` is set and the OCI
CLI is configured. The deployment kit includes a 14-day Object Storage
lifecycle rule and a 15 GiB upload ceiling, leaving headroom inside Oracle's
published 20 GB Always Free Object Storage allowance.

## Deferred post-launch retention plan

Do not implement or run this cleanup during migration. Keep the legacy and ACE
Next databases complete through rehearsal, cutover and the rollback window.
Implement this plan only after ACE Next is live, its scheduler and application
history have been verified, and a tested backup exists.

The owner approved a bounded hot-job retention policy to control PostgreSQL
growth without losing application history. The expiration clock is based on a
job's confirmed closure, never its posted date. A posting more than 30 days old
can still be open and must remain available.

Aggregate read-only measurements on 2026-10-19:

| Data | Count or size |
| --- | ---: |
| Total jobs | 845,152 |
| Active jobs | 616,701 |
| Active jobs older than 30 days by posted or first-seen time | 253,713 |
| Closed, unmarked jobs closed more than 30 days ago | 11,379 |
| Job marks | 1,049 |
| Applied job marks | 756 |
| `jobs` total relation size | 2,115 MB |
| `job_evaluations` total relation size | 411 MB |
| `job_resume_scores` total relation size | 180 MB |
| Whole PostgreSQL database | 2,731 MB |

The active backlog must be audited before pruning. The largest groups of
active jobs older than 30 days were Workday 131,192, Oracle Recruiting 40,625,
Greenhouse 34,892 and SmartRecruiters 24,478. Some may be legitimately open;
others may expose source-specific closure gaps. Never infer closure merely from
age, and never mass-close from an empty, partial, refused or failed response.

Retention rules approved for later implementation:

- Keep every active job, regardless of age.
- Keep full job details forever for applied jobs and every application status,
  including screening, interviewing, offer, rejected and withdrawn. The 756
  applied records are negligible compared with the job corpus and remain useful
  application evidence.
- Keep saved jobs and jobs referenced by tailored resume versions or resume
  assessments.
- Protect every manually authoritative mark from automated deletion.
- Delete an unmarked job only after the source has confidently confirmed it
  closed and it has then remained closed for 30 days.
- Delete derived evaluations and resume scores with an eligible deleted job.
- Preserve a compact tombstone before deleting an unmarked job. It must retain
  source, source account, external ID, company, title, content hash, first seen,
  last seen and closed time so an old posting cannot silently return as new.
- Preserve historical analytics in daily aggregate rollups by source, company,
  eligibility and job state before individual history is pruned.
- Keep scheduler source state permanently. Give temporary employer-page
  readings and operational logs their own bounded retention windows.

Implementation order after launch:

1. Audit old active records and correct source-specific closure detection.
2. Add explicit protected-job predicates and tests.
3. Add compact tombstones and teach discovery to consult them.
4. Add daily historical metric rollups and make analytics use them where
   retention would otherwise change historical totals.
5. Add a cleanup command whose default is dry-run and whose report gives counts
   by reason and protected category.
6. Prove that all applied, saved, manually marked and resume-linked jobs are
   excluded from deletion.
7. Take and restore-test a backup before the first real cleanup.
8. Delete in bounded batches, then run `VACUUM (ANALYZE)`. Use a separately
   planned compaction operation only if disk space must be returned to the
   filesystem; ordinary deletion and vacuum primarily make space reusable by
   PostgreSQL.

This policy reduces disk, index, backup and query growth. It does not reduce
the external polling work required to discover jobs, which remains controlled
through source intervals, conditional HTTP requests, backoff and bounded
concurrency.

## Git and GitHub

The configured remote is `https://github.com/anwarbuilds/ace.git`. The working
branch is `wine-rose-platform`. Never commit `.env`, database dumps, private
screenshots or personal data. Run a secret and personal-data diff review before
push.

Git push over the configured HTTPS remote was working on 2026-10-22. Do not
assume credentials remain valid forever; diagnose an actual authentication
failure if one occurs. Do not force-push. The one exception so far was an
owner-approved `--force-with-lease` during the 2026-10-25 reconciliation, which
dropped nothing. Do not merge this branch to `main`
until the owner completes the multi-day legacy comparison and explicitly
approves that merge.

## Outstanding owner decisions and monitoring

The owner wants both legacy and Oracle discovery running until they trust ACE
Next. Monitor scheduler health and comparable source/time-window outcomes on
both sites. Keep the old replica cron disabled because discovery IDs diverged.
Application changes on one site do not sync to the other in this mode.
The owner clarified on 2026-10-23 that they will record new applications in
ACE Next only. Legacy is an independent discovery validation backup. Do not
merge job rows across databases, because doing so would mask missed results.
On 2026-10-23 both scheduler containers were healthy and both health endpoints
returned 200. A read-only job-identity inventory found 944,901 common jobs,
4,157 cloud-only jobs, 119 legacy-only jobs, and 497 numeric job IDs that point
to different jobs in the two databases. The historical ID-based replica now
has a fail-closed guard when Oracle discovery is running. The private inventory
tool in `backend/scripts/discovery_inventory.py` makes this check repeatable.
`backend/scripts/discovery_parity.py` and
`deploy/oracle/compare-independent-discovery.sh` now produce a private,
read-only report of source coverage, fifteen-minute Pulls, qualifying jobs,
unmatched identities, and eligibility differences. The first live report
compared from 08:45 to 09:25 Pacific and found 244 legacy-only and 352
ACE Next-only recent jobs, with no different eligibility decisions among jobs
discovered by both. All four qualifying unmatched jobs were still awaiting a
source check by the other engine, so none was established as a missed job.
One hour later, a second comparison found that 238 of those 244 legacy-only
jobs and 271 of those 352 ACE Next-only jobs had appeared on both sides. The
latest report is `private-reports/latest/report.md` and its complete JSON is
next to it; the folder is private and Git-ignored. A local read-only cron
checks every 15 minutes and produces a full report at most every four hours,
including after a laptop reconnect. It neither changes database rows nor
starts or stops discovery schedulers. The former crontab was saved under
`~/.local/state/ace-discovery-parity/` for rollback. The old replica cron
remains absent.
Legacy has no `sources_attempted` column; the report uses the shared
`boards_checked` measure and labels unavailable attempts as not recorded.
See `deploy/oracle/README.md` for the read-only comparison command and report.
The backup timer is active, but Object Storage offsite backup is not configured.
Arrange an offsite copy if protection against loss of the Oracle VM is desired.
The Pulls badges, expanded-window persistence, and source-count fixes were
deployed in `b8e30b0b4261257fea25fb8e46f03912c6811990` on 2026-10-23.
Do not merge ACE Next to legacy `main` without separate approval.

## Change log

### 2026-10-25, two Pulls and sidebar elements removed

- At the owner's request: the "Company first. Relevant role second." note
  above the Pulls figures, and the "Discovery engine online" line at the
  foot of the sidebar, with their styles. The top bar's live status still
  says when a source last answered.
  Released website-only; `/healthz` reported `922640f` by 2026-10-25T23:58Z.

### 2026-10-25, approved Analytics production release and continuity

- Implemented the exact four-tab Pixel-Lock module compositions in the existing
  Wine and Rose/Inter shell, added the read-only `/api/analytics` projection,
  exact Applications drilldowns, conservative evidence handling, reviewed local
  icons and the Pulls historical calendar above its original cards.
- Preserved the two newer performance commits by rebasing onto `4f41949`.
  Runtime release `340b175251a8040f3eedad9553c3f6f965657698` was pushed and
  deployed after the owner's explicit request. Documentation release record
  `8e604e7` was pushed afterward and does not require another deployment.
- A new 437 MB private backup passed gzip and archive checks. Matching API/web
  images became healthy at 23:41Z. PostgreSQL, Caddy and scheduler kept their
  container IDs; schema stayed `0050`; no migration, Gmail permission change,
  extension publication, retention cleanup or destructive operation occurred.
- Read-only production verification matched 919 unique applications to
  existing totals, checked four date ranges, disjoint cohorts, deduplication
  and drilldowns, and confirmed no-store. Eight protected table counts and
  applied-mark counts matched. Public health/header SHA, 11 logo hashes,
  private API 401s and four sign-in redirects passed. Public health was checked
  again at 23:52Z. No signed-in production browser review is claimed.
- Passed 89 initial focused backend tests, 45 fictional Playwright tests and
  final drilldown/mobile checks; after integration, 112 backend tests,
  TypeScript, lint, build and zero-hit dash scan passed. Browser runs remain
  suspended on this laptop pending cooling repairs. Screenshots, comparisons,
  logs and the 39-file implementation list remain Git-ignored locally.
- Recorded actual remaining gaps: zero production Gmail connections and
  petition reports, missing submitted-resume/channel attribution and complete
  observation coverage, unverified mailbox sync and owner visual acceptance.
  Unknowns remain visible; no source or effectiveness claims were invented.
- Consolidated the complete Analytics contract and file map into this file,
  corrected stale live SHA/branch/schema/auth descriptions, distinguished dated
  history from current facts, and documented safe schema-free releases, SSH
  stdin handling, backup-list SIGPIPE handling and read-only diagnostics.

### 2026-10-25, second speed round

- Released with owner approval at 2026-10-25T22:29Z: `/healthz` reported
  `269cb32fde277e49d31bc78fc821e403bdc8c4b3`; backup service ran first;
  migrate, api and web were recreated and healthy; scheduler untouched.
  `time_pages.py` afterwards, in ms (before in brackets): `/api/stats` 89
  (216), `/api/jobs` 99 (97), page 2 slowest 89 (216), `/api/intelligence`
  401 (2,542), `/api/coverage` 963 (3,365, the first read after a restart
  computes the snapshot), `/api/dashboard` 83 (68), `/api/facets` 138 (146),
  `/api/system` 139 (79, measured right after the API restart). That run
  still timed Applications' old requests and the badge's one-row page; the
  script now times what the pages ask for. The image's copy of the script
  updates with the next release; until then pipe it from a checkout.
- Production timings from `backend/scripts/time_pages.py` led to: two-pass
  job totals, list pages that fetch only what they show, a count-only jobs
  route for the new-since badge, a 6.4x faster exact skill extractor, a
  passing-first Career Dashboard query, JSONB containment plus a background
  snapshot for Coverage's sponsorship list, and no prefetch for job links or
  sign-out. Details under Speed and responsiveness.
- Checks: 1,252 backend tests (new: totals per filter, count-only route,
  external start date, skill extractor proofs, dashboard skills, snapshot,
  sponsorship list), TypeScript, ESLint, dash scan, production build, and
  signed-in fetches of every changed page on fictional data. The browser
  suite was not rerun: the laptop shut down a third time under it.

### 2026-10-25, speed, search history and search box

- Released with owner approval: `https://ace.opik.net/healthz` and the
  `X-Ace-Frontend-Commit` header reported
  `46d8738e29334ea228d6767858f3fd294a9b9dee` from 2026-10-25T21:22Z, API
  ok, signed-out pages answering in about 0.23 s. The owner ran the
  one-line release (backup service, prepare-release, `up` of postgres,
  migrate, api, web and caddy; scheduler untouched). Their output showed
  migrate, api and web recreated and healthy, and `alembic_version`
  `0050`: migration 0050 (Answer Memory) is applied in production.
- JIT off for app database connections and one fewer stats query; list
  pages fetch in parallel; every workspace route has a loading screen;
  same-route clicks dim the page. Details in the working notes above.
- No saved suggestions in any non-sign-in field; search box without the
  "/" chip and with a single focus ring.
- Checks: 1,229 backend tests, TypeScript, ESLint, dash scan, production
  build, a slow-API feedback probe, and the full Playwright suite at one
  worker on fictional data: 174 of 175 passed. The failure was the "/"
  shortcut test pressing the key right after load while the CPU was
  throttled at 93 to 98 C; it then passed 8 runs in a row. Production
  timing is not yet measured after release.
- The laptop shut down twice (12:58 and 14:03) while Playwright started
  four Chrome workers next to the servers; each boot log simply stops.
  `x86_pkg_temp` read 92 C three minutes after boot and 98 C with one
  worker. See the local testing recipes.

### 2026-10-25, agent working notes

- Added "Working notes for agents": owner working style, the no-AI commit
  rule, production access through owner-run one-line SSH, the website-only
  release line, the open Google sign-in sequence issue and its guarded fix,
  the shared Git layout, local test recipes and the typography contract.
- Updated the current state to `386bed9`, manifest 1.28.0, the retired
  pre-rebase clone and its safety copies, and the 22-test extension suite.

### 2026-10-25, V5.1 theme sync and Close

- The card follows the computer's Day or Night setting, live, through
  `prefers-color-scheme`. The header toggle picks the other theme and holds it;
  toggling back to the computer's own theme returns to following it. Stored as
  `aceStudioThemeMode`; the old `aceStudioTheme` value is ignored.
- A Close button (outline X) sits after Minimize in the card header and after
  Expand in the dock. It uses the existing dismiss path: the card stays closed
  on that page, including while the owner types, and returns on a new page,
  a new form step or the toolbar's Fill. Close never submits or advances.
- The Form detected pill stays on one line and the dock text ellipsizes, so
  the extra control changes no layout. Compact card height is 354px.
- Checks: 258 rule cases, the memory safety cases and 22 Chrome extension
  tests passed, including the new `extension-focus-theme-close.spec.ts`.
  Manifest 1.28.0. Local fixtures only; reload the unpacked extension to use it.

### 2026-10-25, reconciliation and V5.1 typography

- Combined the remote typography line with the V5.1 line on GitHub: the rebased
  V5.1 commits, the local continuity commit and this consolidated document are
  all on `wine-rose-platform`. Nothing from either line was dropped.
- Applied the website typography to the V5.1 card: packaged Inter instead of an
  uninstalled "Inter" fallback, the wordmark weight and tracking, an 11.5px
  floor, website weights and tabular numbers. Type properties only; the 318px
  width, drag, dock, Review and motivation exclusion are unchanged.
- Checks: 258 rule cases, the memory safety cases and 19 Chrome extension tests
  (including the seven V5.1 tests) passed. Served over HTTP with the packaged
  font, the card rendered `ace-inter` in Day and Night without page errors. The
  compact card is 355px tall in Inter, against 347px in the approved reference.
- The shared local repository holds a broken Codex checkpoint ref that makes
  `git fetch` fail with "bad object"; pushing still works. Fetch into a separate
  clone, or remove that one dangling ref with the owner's approval.
- Pasting a multi-line block that starts with `ssh` loses the following lines
  during login. Run a remote release as one `ssh host '...'` command.

### 2026-10-25, standalone continuity consolidation

- Made this file the single standalone platform handoff for new chats. The
  topic documents remain optional historical archives rather than required
  startup reading.
- Added a code-verified implementation map covering repository boundaries,
  backend modules, polling transactions, auth and HTTP boundaries, every API
  family, all durable tables, migrations 0001 through 0050, every current page
  route, client state ownership, Combined Intelligence, Gmail safeguards,
  extension modules and storage, Compose topology, environment settings,
  operational scripts, test surfaces and a future-change checklist.
- Reconciled the V2 baseline with current Career Dashboard and Inbox
  Intelligence routes while preserving Pulls as the authenticated home, and
  corrected the extension token description to include approved Answer Memory
  operations.
- Consolidated product vocabulary, the gate, discovery lifecycle, persistence,
  coverage, matching, applications, API domains, the complete website contract,
  Pulls metrics, Focus Mode V5.1, Answer Memory, Resume Studio, privacy,
  testing, operational doctrine, historical safeguards and known limitations.
- Corrected the stale lower-section instruction to stop one scheduler. The
  current owner decision is two independent discovery systems, separate
  databases and no cross-database replication.
- Recorded local documentation HEAD `a1e59ff` and the three-ahead,
  three-behind branch divergence that must be reconciled before any push.

### 2026-10-25, continuity and Focus Mode V5.1

- Recorded the V4 Answer Memory code and additive migration 0050, the locally
  implemented V5.1 extension, and the final visual and Workday listing fix.
- Distinguished local Chrome fixture results from live employer-form and
  production API verification. The V4 production migration and Memory API
  remain unverified in this record despite the owner's deployment approval.
- Recorded the other agent's three typography commits on the tracked remote
  branch so future work can reconcile them with the two local V5.1 commits.

### 2026-10-24, typography release recorded on the remote branch

- Commit `8d84141` records a website-only Inter typography release at frontend
  commit `61debd6`. Its recorded checks covered `/healthz`, the served font,
  sign-in routing, public Day and Night rendering, console output and forbidden
  dashes. That release did not recreate API, migration, scheduler, PostgreSQL or
  Caddy. Its extension typography work is on the remote branch and is not yet
  reconciled into this local V5.1 branch.

### 2026-10-24, owner account release

- Extended the existing owner account with first name, last name, phone number
  and a private profile photo. Added an additive migration (0049), owner-only
  profile endpoints, and current-password plus email-code verification for
  changing the ACE sign-in address. Gmail connection remains separate.
- Deployed the account change at the approved commit shown above. See
  `docs/architecture/2026-10-24-owner-profile.md` for behavior and rollback
  details. Both discovery schedulers and databases remain independent.

### 2026-10-23

- Restored the owner's intended comparison mode after they clarified that
  stopping legacy discovery was premature. Both schedulers are healthy against
  separate databases. The old replica remains off to prevent ID collisions.
- Recorded the owner-approved one-writer cutover to Oracle discovery, final
  replica cursor, parity evidence and intact legacy copy. This was subsequently
  reversed for independent comparison at the owner's direction.
- Recorded the fresh cloud backup, successful isolated restore drill and active
  daily backup timer. Offsite backup remains unconfigured.
- Recorded the replica edge case affecting 3,300 source-update timestamps and
  its guarded, timestamp-only repair before the cloud scheduler started.
- Clarified that normal app releases must leave the now-running cloud scheduler
  healthy and that the pending Pulls UI release remains separate.

### 2026-10-22

- Recorded the canonical Dynu production URL, Oracle deployment path, deployed
  SHA, migration revision, health evidence and post-deployment aggregate data
  inventory.
- Recorded the exact stale-interface cause: the production checkout and images
  had not advanced with the approved branch.
- Documented the one-writer monitoring architecture, minute replication flow,
  parity boundary rules and safe retry observed during API replacement.
- Documented real stored PDF rendering, non-PDF download behavior, My Account,
  persisted display names and verified Google profile-name import.
- Added the safe release procedure and reaffirmed that normal releases must not
  start the cloud scheduler or alter the legacy stack.
- Replaced obsolete cloud-provisioning actions with the current multi-day
  parity-monitoring and final-cutover decisions.

### 2026-10-19

- Recorded the owner-approved post-launch job retention plan.
- Confirmed that applied records must not be deleted through the current
  `job_marks.job_id` cascading foreign key.
- Replaced the proposed posting-age deletion rule with confirmed-closure plus
  30 days, protected full application history, tombstones and analytics
  rollups. No cleanup was executed.

### 2026-10-16

- Audited the legacy Docker runtime and database with aggregate-only queries.
- Confirmed the legacy database already contains migrations through 0040.
- Confirmed ACE Next preserves the complete legacy backend and includes the
  later bounded resume scoring change.
- Added migration 0041 for a bound Google owner subject.
- Added owner-only Google OpenID Connect with full token verification, secure
  cloud cookies and honest unavailable UI state when configuration is absent.
- Added email verification codes for password sign-in and password recovery,
  including expiration, single use, resend replacement, guessing limits and a
  production fail-closed switch.
- Confirmed that 755 is the complete historical application total to preserve:
  708 applied job marks plus 47 external application rows. Removed the earlier
  incorrect estimate from the migration plan.
- Added the idempotent legacy resume to Resume Studio bridge.
- Added privacy-safe source and target inventory tooling.
- Added the Oracle production Compose, Caddy HTTPS, backup script and operating
  guide.
- Bounded offsite backup retention with a 14-day lifecycle rule and a hard
  upload ceiling so ACE backups cannot silently consume the full free quota.
- Completed a migration rehearsal from a private dump of the real database.
  Restore, migration and the five-resume Studio bridge succeeded. Temporary
  dump and rehearsal database files were deleted afterward.
- Kept the live legacy stack and database untouched.
