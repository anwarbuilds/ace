# Startup talent networks and the site reliability and mobile exclusion, 2026-10-29

Status: **LIVE** on API and scheduler since 2026-10-29 23:03 UTC (16:03 Pacific), commit `fc81876`, with the
owner's approval. Board registration ran in the background afterwards; see the root knowledge file for the result,
evidence and rollback.

## Owner request

The owner pointed at a16z's speedrun talent network (its New York collection) and said ACE misses many startups with
new grad roles across US cities. They asked for every such site to be explored, the startups listed, then added to
ACE's sources without breaking anything, as an upgrade. In the same session they asked that site reliability ("software
reliable engineer") and mobile engineer roles stop appearing.

## What was read, and how

Venture firms and accelerators publish their portfolio companies' open roles. Each role links to the company's own
board (Ashby, Greenhouse, Lever, Workable, Gem), which is what ACE reads directly. So the networks were treated as lists
of boards, the way the Simplify feed already is, never as a source of postings: an aggregator is a floor, not a
ceiling (see `docs/knowledge/03-coverage-and-discovery.md`).

Every request obeyed robots.txt, including wildcard rules (speedrun's decoy `/jobs/*-ad00000` postings were never
fetched), at least 1.25 seconds apart per host, with every Getro board sharing one limit of about three requests a
second because they are one platform. A 401, 403, 429 or challenge would have stopped that host; none occurred in 3,910
requests. Getro's own API host disallows crawlers, so it was not used: one posting page per company carries the
original posting link in its server-rendered data. One posting per company, with an engineering title, was enough to
find its board.

| Kind | Networks | Result |
| --- | --- | --- |
| a16z speedrun | 1 (765 companies, 23,474 postings in its sitemap) | read |
| Getro boards | 35: Accel, General Catalyst, Insight, Khosla, Lux, Thrive, 8VC, Redpoint, Sapphire, SV Angel, Scale, DCVC, SignalFire, Madrona, Notable, Greycroft, Lerer Hippeau, AlleyCorp, Primary, RRE, Uncork, True, Upfront, Foundry, Revolution, NYCA, Reach, Fifth Wall, Underscore, Bonfire, NFX, Live Oak, Lightbank, Glasswing, Techstars | read |
| CareerPuck and own pages | a16z, Initialized, South Park Commons, Greylock, Paradigm | read (the last four: first page only) |
| Hacker News "Who is hiring?" | August, September, October 2026 (884 posts) | read through the public item API |
| Consider boards | 20: Sequoia, Kleiner Perkins, GV, Lightspeed, Bessemer, Felicis, NEA, First Round, USV, Battery, CRV, Bain Capital Ventures, Forerunner, Contrary, Abstract, Costanoa, Necessary, 5AM, Gaingels, Pioneer Square Labs | refused: the job data API requires a CSRF token |
| robots.txt disallows | 13: Boldstart, GGV, Susa, Obvious, Amplify, Coatue, Eclipse, ffVC, Floodgate, Harlem Capital, M12, Owl, Venture for America | not read |
| Other | Climatebase (bot challenge); YC Work at a Startup (about 40 roles public, the rest behind a sign-in); Craft and Menlo (timed out) | not read |

speedrun's "backed by" collections list portfolio companies of Sequoia, Kleiner Perkins, GV, Felicis, Bessemer,
Lightspeed, USV, Index and others, so the refused Consider boards are partly covered through it.

## What was found

2,181 distinct employer boards ACE can read (987 Ashby, 645 Greenhouse, 239 Workday, 193 Lever, 49 Gem, 44 Workable, 17 SmartRecruiters, 7 Oracle). 682 were already in ACE (legacy catalog as a proxy). Of the 1,499 new ones, **732 are hiring US software, machine learning or forward deployed engineers today** (434 Ashby, 204 Greenhouse, 60 Lever, 28 Gem, 6 SmartRecruiters): 241 of them hold 395 roles that pass the gate (v55) right now, and 2,188 US engineering roles in all. 580 are left out until they hire; 41 are staffing agencies; 15 links were unreadable and 13 boards empty; one is a firm's shared portfolio board (Pear VC). 117 Workday, Workable and Oracle boards were left to the server (Workable answered 429 here). Twenty-four boards declare a different employer than the network listed, mostly acquisitions and renames (Data.ai is Sensor Tower, Drift Salesloft, Split Harness, Capella Space IonQ, Toggle Reflexivity), and are registered under their own name.

Boards were read once through ACE's own adapters (`build_default_source_dispatcher`) to count US software, machine
learning and forward deployed roles and new grad eligible roles under the gate. Known boards were compared with the
legacy catalog as a proxy; the production script compares with the production catalog itself.

Startups on boards ACE has no reader for, counted by distinct company in the links: Rippling 72, Notion pages 63, Paylocity 39, YC Work at a Startup 39, Wellfound 35, Dover 33, BambooHR 27, Breezy 27, JazzHR 21, Teamtailor 17, Recruitee 7, Pinpoint 5. Rippling is the
largest structured gap and the next reader worth building; Dover's robots.txt disallows its API, Notion pages carry no
structured postings, and Work at a Startup needs a sign-in.

## Registering them: `backend/scripts/register_network_boards.py`

`backend/app/discovery/network_boards.json` holds every board found (staffing agencies excluded), with the networks
that named it. The script:

- skips every board the catalog holds, enabled or not, under any case (`board_key`);
- reads each new board once through the normal adapter, as feed links are;
- leaves out unreadable, empty and agency boards (the feed path's `staffing_reason`), and boards with no US software,
  machine learning or forward deployed role today, without recording them, so a later run adds them once they hire;
- adds the rest enabled, `discovery_source = "talent_network"`, at the provider's registration cadence (fifteen
  minutes for single-request boards), committing each board as it goes;
- skips Workday and Oracle boards unless `--include-paged`: they are large public companies, and each tenant is up to
  a hundred requests on a shared edge;
- stops reading a provider for the rest of the run after a 429 or 5xx;
- writes nothing without `--apply`.

Load: 241 boards at fifteen minutes and 491 hourly add about 1,455 polls an hour to roughly 9,400 (legacy catalog proxy), about 15 percent; all at fifteen minutes would have been about a third. The legacy scheduler on the same catalog keeps fifteen-minute boards at a median of 11 to 14 minutes old, 90th percentile near 20, with the same concurrency of six. Nothing was measured on production: the agent was refused read-only access.

## Gem boards are detected

ACE has read Gem boards since Groq (`adapters/gem.py`), but `detect_source_from_url` did not know `jobs.gem.com`, so
feed and network links to Gem boards were dropped. `_detect_gem` now returns `gem/<board>` with the API host
`api.gem.com`, the host hand-registered Gem boards already carry. The scheduler's feed-link maintenance picks Gem boards
up from then on.

## Site reliability and mobile leave the list, gate v55

See `docs/knowledge/01-gate-and-roles.md`, "Site reliability and mobile leave the list". Two named families, rejected
as `NON_TARGET_ROLE` with a reason; measured on the legacy corpus, 156 of 3,133 active passing roles change.
`backfill_job_evaluations.py --status PASS` re-evaluates only stored passing decisions after the release.

## Validation

- Full hermetic backend suite: 2,162 passed (pyenv 3.12.12 with the venv's site-packages; the venv's own
  interpreter cannot import `_ctypes`). New tests: `test_register_network_boards.py` (13),
  `test_backfill_job_evaluations.py` (2), site reliability, mobile and edge-case titles in `test_roles.py`, the gate
  test in `test_eligibility.py`, Gem detection in `test_ats_detector.py`, the network cadence in
  `test_coverage_cadence.py`.
- `register_network_boards` run end to end against a throwaway SQLite database with four real boards: the dry run
  wrote nothing; `--apply` added the two hiring boards (15 minutes for the one with passing roles, hourly for the
  other), skipped a board with no US engineering roles and the Workday board; a second run skipped both as known.
- Forbidden-dash scan 0, `git diff --check` clean. No browser, web or production check: the web is unchanged, and
  the agent permission classifier refused even read-only production queries this session.

## Release plan (approved and run)

1. Fresh private backup; record running images and protected inventories, as in earlier releases.
2. Fast-forward canonical to the reviewed commit; build `api` and `scheduler` only.
3. Recreate `api` and `scheduler` with `--no-build --no-deps --wait`. The scheduler resumes from each source's last
   success; web, PostgreSQL and Caddy are untouched; no migration.
4. `docker compose exec -T api python -m backend.scripts.backfill_job_evaluations --status PASS --apply`.
5. `docker compose exec -T api python -m backend.scripts.register_network_boards` (dry run), then with `--apply`.
6. Verify health, the scheduler polling the new boards, zero passing site reliability or mobile roles, and the
   protected inventories.

Rollback: the previous `api` and `scheduler` images. New catalog rows are additive and marked `talent_network`;
switching them off is an `UPDATE ... SET enabled = false WHERE discovery_source = 'talent_network'`, never a delete.
The legacy system keeps the v54 gate and its own catalog, so the independent comparison will show these boards as
ACE Next only.

## Round two: every major tech city (2026-10-29 evening)

The owner asked for every speedrun-like site in each major US tech city, deep research, and all of it added. Three kinds
of source turned out to be readable within robots.txt:

- **Regional VC boards** found by probing 124 more firm and accelerator hosts: FirstMark (New York), F-Prime and .406
  Ventures (Boston), Ascend (Seattle), Capital Factory, S3 and Silverton (Austin), M13 (Los Angeles), Innovation Works
  (Pittsburgh), Album and Pelion (Utah), Variant, Dragonfly, Polychain and Multicoin. 619 companies, 146 readable
  boards, 122 new. Amplify LA, Congruent and Robin Hood Ventures are Consider boards (CSRF); Jump Capital (Chicago),
  Comcast Ventures, M12, Backstage, Energize and Entrepreneur First disallow their job pages.
- **Y Combinator**: YC's own directory disallows query strings and Work at a Startup shows little before a sign-in,
  but the public yc-oss dataset (GitHub Pages) lists every company marked hiring with its website: 1,497, of which
  1,239 in the US or Canada. 1,018 were not yet covered; ACE's verified name lookup found 219 boards and its
  careers-page reader, started from the real website, 25 more. Most of the rest post only on Work at a Startup.
- **Built In**, entry-level and junior engineering listings in 22 cities (San Francisco, San Jose, New York, Seattle,
  Austin, Boston, Los Angeles, Chicago, Denver, Boulder, Atlanta, Miami, Washington, San Diego, Dallas, Houston,
  Raleigh, Pittsburgh, Philadelphia, Salt Lake City, Portland, Minneapolis): 1,396 companies. Built In's apply links
  need a sign-in and were not followed; ACE's verified name and careers-page lookup found 270 boards for the 895 not yet
  covered.

TrueUp answers 403 and was not read. Board names come from the board's own declaration where it has one.

The list grew from 2,139 to 2,726 boards. The production run reads only the boards the catalog does not hold, with
`--include-paged` this time so large employers' Workday and Oracle boards (many with new grad programmes in speedrun's
early-career collection) are read too, one at a time.
