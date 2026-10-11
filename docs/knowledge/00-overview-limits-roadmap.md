# ace: overview, limits, roadmap and recent log

> Part of the ace knowledge set (index: `README.md`). Read this when you need the shape of the whole system, the rules
> that must never break, what is known to be limited, or what happened most recently.

## What ace is

A personal career-intelligence pipeline. It polls job boards continuously (about 2,090 enabled sources on 2026-10-10),
applies a deterministic eligibility gate, and presents the survivors in a web application, one alert email per closed
pull, and a Chrome extension that fills application forms. Flow: sources, poll, persist and diff, eligibility gate,
freshness, materialize, web app. The digest email subsystem was removed on 2026-09-06 and one alert per pull was added
on 2026-09-14. The public `README.md` and `docs/overview.md` describe the system for outsiders; `docs/HANDOFF.md`
holds the current state and the plan.

## Non-negotiable invariants

Break these and the system misleads its user. Each exists because
violating it caused a real failure.

1. **The gate decides inclusion; nothing else does.** Freshness,
   verification status and match score affect alerting and ordering
   only. No score may hide a qualifying job from the database or the
   web application.
2. **Silence is not rejection.** Missing sponsorship, experience or
   location information is *unknown*, never disqualifying. Only explicit
   blockers reject. Measured: only 3 of 437 postings state sponsorship
   positively, so requiring it would empty the system.
3. **Identity and content are separate.** Identity is
   `(source, source_account, external_id)` and never changes. Content is
   a SHA-256 hash. This is what makes a retitled posting an `UPDATED`
   rather than a new job plus a false closure.
4. **Never mass-close from one bad response.** An empty snapshot is
   refused as authoritative.
5. **Evaluation is reproducible.** No wall-clock reads, no network
   calls, no randomness inside the gate. This is what allows the whole
   corpus to be re-evaluated after a rule change.
6. **The apply link is always the employer's own posting.** Never an
   aggregator or redirect. *One deliberate exception, RippleMatch
   (2026-09-17): employers post early-career roles there **instead of**
   their own ATS and receive the application there, so there is no
   employer posting to link to and linking anywhere else would mean
   linking nowhere. The distinction that keeps the invariant meaningful
   is that an aggregator republishes a worse copy of a link ACE could
   have had; this is the only link that exists. It is registered under
   its own source type rather than blended in, so the exception stays
   visible.*
7. **Store everything, show little.** Rejected jobs are retained, never
   deleted, so a rule change can be re-run over history.

## Architecture in brief

| Layer | Module | Responsibility |
| --- | --- | --- |
| Adapters | `app/adapters/` | Provider-specific fetch → `CanonicalJob`. No eligibility knowledge. |
| Runners | `app/runners/` | Composition: injects gate-derived predicates into adapters |
| Scheduling | `app/scheduling/` | Cadence, dispatch, one transaction per poll |
| Persistence | `app/persistence/` | Lifecycle diff, content hashing. Never commits - callers own transactions |
| Intelligence | `app/intelligence/` | The eligibility gate and role classifier. Pure functions |
| Evaluation | `app/evaluation/` | Applies gate + freshness to a snapshot |
| Matching | `app/matching/` | Resume parsing, skill extraction, scoring |
| Discovery | `app/discovery/` | Finds new ATS accounts from public sources |
| Applications | `app/applications/` | Reads a tracker sheet, matches its rows to stored postings, keeps what has no posting behind it |
| History | `history_entries` via `app/api/` | The repeating work and study blocks, as a list rather than a value |
| Answers | `app/answers/` | What each application question *is* - boolean, choice or free text - and the wordings a form might print for each option |
| Coverage | `app/coverage/` | Recall benchmark against a held-out list |
| Notifications | `app/notifications/` | Alert dispatch |
| API | `app/api/` | FastAPI + single-file vanilla-JS UI. Writes the user's own decisions, never a posting |
| Extension | `extension/` | Chrome autofill. `fields.js` is pure matching logic and is unit-tested standalone; `content.js` touches the DOM |

**Hard boundaries.** Network I/O never inside a database transaction.
Eligibility rules never inside provider code. The web app never fetches
from an ATS.

"Read-only" above is about postings, and is worth stating precisely
because it has narrowed: the API writes what the *user* decides -- marks,
answers, imported history, a resume -- and never writes a posting or an
evaluation. Those belong to the scheduler, so the web app cannot become
a second, divergent source of truth about what exists out there.

The table dates from 2026-09-06. Since then `app/notifications/` is gone (alerts live in `app/alerts/` and `app/mail/`), `app/coverage/` and `app/discovery/` grew a great deal, and the sheet reader in `app/applications/` lost its UI. `docs/HANDOFF.md` section 4 is the current system map.

## Known limitations

| Limitation | Status |
| --- | --- |
| Google is read from the first page of each search only | Accepted: robots.txt disallows `page=`. Three newest-first US searches every 30 minutes; every read is partial and closes nothing |
| Eightfold boards are expensive to poll | Ten postings a page, polled one at a time, hourly or slower by yield. Newest-first incremental polling is the known fix, not built |
| Some queued postings are unverified | Their requirements could not be read; they are browse-only and marked in the UI. On 2026-10-10, 1,098 of 1,249 qualifying jobs were verified |
| Workday and Amazon cannot use conditional HTTP | Workday lists via POST; Amazon generates its search per request |
| Matching is lexical, and new jobs are never scored | Related-skill credit exists (v2), but scoring runs only when a resume is uploaded. Found 2026-10-10; see HANDOFF.md Step 0b |
| No deadline tracking | Accepted: ATS rarely publish them |
| No sign-in | One private user. Sign-in is Phase 2 of the rebuild; it was built and removed in September 2026 because it locked the extension out (see 07) |
| Some employers cannot be read | Tesla, Citadel, Citadel Securities, D. E. Shaw, LinkedIn, Equinix and others refuse automated access; they are left alone |

## Roadmap history (agreed 2026-09-06)

Agreed 2026-09-06, in order.

| # | Work | Status |
| --- | --- | --- |
| 1 | Cleanup: internships out, email removed, this file | **Done** |
| 2 | Scheduler performance: prefilter, concurrency, conditional HTTP | **Done** |
| 3 | Pull sessions: group jobs by poll run, show last-pulled time | **Done** (backend + API; UI deferred) |
| 4 | Matching v2: related-skill understanding (backend) | **Done** (backend + API; UI deferred) |
| 5 | **One combined UI pass**: session grouping, match display, high-match filter, job detail pages, distinctive design | **Done** (backend + UI) |
| 6 | Applied tracking: upload spreadsheet, mark postings "Applied on <date>" | **Done**, and since grown into a two-way sync - the sheet and ACE each carry what the other is missing, converging rather than drifting |
| 7 | FAANG coverage investigation | **Done** (Netflix adapted; Google, Meta, Microsoft documented as blocked) |
| 8 | Production: dev/prod split, deploy, auth, backups | Planned |
| 9 | Mobile app | Future |

Item 7 is partly superseded: Google and Meta are now read within their robots.txt (2026-10-09). Items 8 and 9 are superseded by the platform rebuild plan in `docs/HANDOFF.md` section 9 (Next.js app, sign-in, home page,
Resume Studio, then the cloud). Intent recorded at the time:

The user wants this as a portfolio project: deployed, with real
dev/production separation, eventually a mobile app. Deployment changes
the safety model - job-search data would leave the local machine, so
authentication is required from day one rather than bolted on.

## Working agreements

- **Verify, don't assume.** Numbers in reports come from the running
  system, not memory. Check the database.
- **State limitations plainly.** The user values honesty about gaps over
  reassurance. Several good decisions came from saying "this cannot be
  done" rather than attempting a workaround.
- **Do not bypass access controls.** Apple's bot protection was
  respected rather than circumvented; this is the standing policy.
- **Tests pin every bug found.** 1009 unit tests in about 20 seconds, 101 of
  them browser tests against real Chrome, and 185 pinned matcher cases the extension runs with `node extension/test-rules.js`.
- **One change at a time**, verified against live data before the next.

## Backlog (implementation work, none of it blocked)

- Read application status from email (Phase 3 of the original plan): apply the unambiguous status changes
  automatically and queue the rest for review rather than guessing.
- Newest-first polling for Eightfold: one or two requests a poll instead of hundreds, with a periodic full sweep for
  closures. Needs persistence to accept a partial snapshot.
- An adapter for classic iCIMS sites (the Jibe flavour is done): 59 companies were diagnosed as iCIMS, and each
  tenant's robots.txt must be honoured.
- Client-side-rendered careers pages: the 2026-09-10 audit found 94 (Wiz, Retool, dbt Labs and others; Zoom and Shopify
  have since been solved with their own readers). Closing the rest needs a headless-render step in discovery, which puts
  a browser in the scheduler path, so it needs the user's sign-off first.
- Resume scoring for new jobs (found 2026-10-10): HANDOFF.md Step 0b.
- The platform rebuild: HANDOFF.md section 9.

## Recent session log

- **Darker themes.** The user found the first anthracite palette "a bit light"
  and asked for both versions darker. Night: canvas #1F2628, sidebar #1A2022,
  cards #293133 (RAL 7016 itself), surface 2 #2F383A, raised #363F42. Day:
  canvas #E2E7E7, sidebar #D9DFDF, cards #ECF0F0, surface 2 #DDE3E3, raised
  #F4F7F7, ink #1F2628. Applied to index.html, the extension panel and popup,
  and the alert email (INK, MUTED, CANVAS #1f2628, CARD #293133, LINE #3b4547).
  Every text pair re-checked: worst night pair 4.77, worst day pair 5.29.
- **A drawn dash got through.** The 16 by 2 px rule before the tier name on the
  job page (`.jp-tier::before`) read as an em dash and the text guard could not
  see it. It is a 6 px dot now; the popup's "+" / minus toggle is a chevron.
  `backend/tests/browser/scans.py` finds drawn dashes by shape (inked, 6 to 40 px
  wide, at most 3 px tall, from an element or a pseudo-element, or dash
  characters in generated content) on every page in both themes and in the popup;
  a probe test proves it can fail. A progress fill inside a thin wider track is
  exempt (the match bar's fill is 43 percent of 84 px). The old
  `test_no_em_dash_reaches_the_screen` was defined twice, so the first never ran;
  it is `test_the_rendered_queue_has_no_em_dash` now.
- **Deployed and pushed** (d9df41a, 4f516ef): unit 1009, browser 101 (one skip:
  "no check found a job to expand", data dependent, right after a restart),
  rule cases 185. `.dockerignore` now excludes `web/` so node_modules never
  reaches the backend image.
- **Found, not fixed: resume scores never refresh.** `rescore_corpus` runs only
  from `POST /api/resume`. `select resume_id, count(*), max(scored_at) from
  job_resume_scores group by 1` shows resume 2 scored 31,445 jobs in one batch at
  2026-09-06 13:35; `/api/stats` reports match_unscored 1238 of 1249. The job page
  says "ACE could not read this posting" for these, which is wrong. Top of the next
  session's plan (HANDOFF section 9, Step 0b).
- **Platform rebuild** decisions (one private user, Next.js and TypeScript, email
  and password, Render) are in HANDOFF section 9 and in memory. `web/` holds the
  untouched create-next-app 16.3.8 scaffold.
- **Handoff** written for a fresh cloud session: `docs/HANDOFF.md` (committed, no
  personal data) and a private prompt file kept out of the repo.
  A cloud session sees only what is on GitHub: no `.env`, no database, no docker,
  no scheduler, no local memory, no extension in the user's browser.
- A preview server on :8001 (`uvicorn ... --port 8001`, `.env` loaded) was used for
  UI checks and tests before deploying; it stops when the machine restarts.
