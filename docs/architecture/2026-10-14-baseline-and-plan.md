# ace: verified baseline, gap matrix and plan (2026-10-14)

Written against the master implementation brief. Labels: **VERIFIED IN CODE** (read or exercised in this
session), **DOCUMENTED ONLY** (stated in the handoff or history, not checked), **NOT VERIFIED** (needs the owner's
machine). This session ran in a cloud container: it had the repository, a fictional demo database and real Chrome,
and no access to the live PostgreSQL database, scheduler, `.env` or the extension in the owner's browser.

## 1. Verified current state

| Item | State | Label |
| --- | --- | --- |
| Branch | `next-app`, from `main` at `b68da4a`; main untouched | VERIFIED IN CODE |
| Backend | FastAPI, SQLAlchemy 2, Alembic (36 revisions, head `0036`), gate `2026-10-09-v53` | VERIFIED IN CODE |
| Unit tests | 1038 pass on SQLite (1027 before this work, plus 11 new) | VERIFIED IN CODE |
| Old UI browser suite | 105 pass, 0 skip, against the demo database | VERIFIED IN CODE |
| Extension | MV3 `ace autofill`, 185 matcher cases (`node extension/test-rules.js`) | DOCUMENTED ONLY in this session |
| Next.js | 16.3.8, React 19.2.8, Tailwind 4; now a working app (section 4) | VERIFIED IN CODE |
| Live corpus sizes (2,090 sources, ~1,250 queue, ~600 applications) | historical figures | NOT VERIFIED |
| Resume scores stale since 2026-09-06 | reproduced in tests; fixed (section 3) | VERIFIED IN CODE (fix), NOT VERIFIED (live rows) |
| Alerts | composed per pull; delivery needs `RESEND_API_KEY` | DOCUMENTED ONLY |
| Auth | none today; an earlier attempt was reverted for locking out the extension | VERIFIED IN CODE (absence) |
| CI | none existed; added `.github/workflows/ci.yml` | VERIFIED IN CODE (YAML parses; not yet run on GitHub) |

## 2. Gap matrix

| Requirement (brief section) | Present behaviour | Source | User-visible effect | Risk | Change | Regression test | Phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Runnable without the live DB (12) | none | n/a | nothing to look at in the cloud | high | `backend/scripts/seed_demo.py`, fictional, real gate and scorer | `test_seed_demo.py` | 0, done |
| New jobs scored (5) | only on upload | `matching/service.py` | ~99% of queue "n/a" | high | per-cycle sweep, bounded; refresh on content, rule or algorithm change | `test_score_sweep.py` (9) | 0, done |
| Four honest score states (5) | one "n/a", wrong text | `index.html` | "could not read" when merely unscored | medium | `match_state`: scored, pending, no_description, insufficient, no_resume | `test_listing_names_each_score_state`, e2e | 0, done |
| "Scoring failed" state (5) | n/a | | | low | a failing job is logged and retried, shown as "not scored yet"; no failure row stored | `test_one_job_failing...` | 0, partial (see 6) |
| Route-based app (4) | single HTML file | `static/index.html` | no real URLs | high | Next.js app, routes below | Playwright (39) | 1, in progress |
| URL-held filters, sort, page (4) | memory only, infinite scroll | old UI | no bookmarks, lost place | medium | `lib/listState.ts`, numbered pages | `navigation.spec.ts` | 1, done |
| Renames, Saved out of nav (4) | old names | | | low | new names, 307 redirects, saved data and `/app/saved` kept | `navigation.spec.ts`, `pages.spec.ts` | 1, done |
| No dashes, typed or drawn (4) | guards in old UI | `index.html`, `scans.py` | | high (user rule) | guard ported (MutationObserver + `undash`), both scans ported to Playwright | `pages.spec.ts` | 1, done |
| Palette with search (4) | commands only | old UI | | low | commands plus company/title search | `keyboard.spec.ts` | 1, done |
| Parity report before cutover (5) | n/a | | | high | page by page report; old UI stays at `/` | to write | 1 |
| Home overview `/app` (4) | none | | | low | redirect to Opportunities for now | `navigation.spec.ts` | 1, next |
| Typed API (9) | untyped JSON | `api/main.py` | drift between front and back | medium | Pydantic response models, generated TS | contract tests | 2 |
| Owner-only auth + extension pairing (8) | none | | private data on any reachable port | high | sessions, argon2id, pairing tokens, rollback switch for local dev only | auth suite | 2 |
| SDE II targeting (3) | 3+ open-ended and 4+ rejected | `eligibility.py` | some II roles hidden | medium, invariant change | versioned policy, impact dry run, **owner approval before activation** | fixtures for 2, 3, 3+, 4+, 5+, II, III, L4 | 2 or 3 (gated) |
| Resume Studio, CKB, ATS lab (6, 7) | lexical scorer, one resume | `matching/` | | large | phased, deterministic first | per brief | 3, 4 |
| 24/7 hosting (10) | owner's machine | `compose.yaml` | | large | dated provider research, shadow polling | runbook | 5 |

## 3. The scoring fix

```
before:  upload -> rescore_corpus -> job_resume_scores (once)
         new job -> (nothing) -> "n/a", "could not read"

after:   upload -> rescore_corpus (unchanged)
         each scheduler cycle -> score_unscored_jobs:
             active PASS jobs with no row for the active resume,
             or whose evaluation changed after scoring (content or rules),
             or whose row came from an older MATCHING_ALGORITHM_VERSION
           -> score, remember previous_score, at most 2,000 per cycle
         read -> match_state explains every missing number
```

Failure modes: a job that throws while scoring is logged (`job_score_failed`) and skipped, so one bad posting never
stops the sweep and no made-up score is stored; it is retried next cycle. The first cycle on the live database will
score about 1,250 jobs once (keyword matching, well under the cycle time; to be measured on the owner's machine).

## 4. Information architecture and routing

| Page | Route | Old route (redirects) | Notes |
| --- | --- | --- | --- |
| Opportunity Hub | `/app/opportunities` | `/app/queue`, `/`, `/app` | tabs: All opportunities, Strong matches, New since your last visit, Latest discoveries |
| Job Intelligence | `/app/jobs/[id]` | `/#job/<id>` | resolves closed jobs; Escape returns to the list as left |
| Discovery Activity | `/app/activity` | `/app/pulls` | every check, including empty ones |
| Applications | `/app/applications` | `/app/applied` | standalone records, CSV export |
| Archive | `/app/archive` | | reviewed and not relevant |
| Saved roles | `/app/saved` | | out of navigation by request; data and save action kept; palette "Show saved roles" |
| Resume Studio | `/app/resume-studio` | `/app/resume` | today: the existing resume page; Phase 3 builds the studio here |
| Skills | `/app/insights/skills` | `/app/skills` | |
| Answer Bank | `/app/answers` | | |
| Source Coverage | `/app/coverage` | | |
| Settings | `/app/settings` | | |
| Sign in | `/login` | | Phase 2; not shipped as a cosmetic page |

## 5. Decisions (ADR summary)

1. **Keep the stack.** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Docker Compose, Next.js 16, React 19, Tailwind 4.
   No new runtime dependency for the web app beyond Playwright (dev only). No microservices, queues, Kubernetes or
   vector store until a measurement asks for one.
2. **Port the design, do not redraw it.** The old UI's CSS is carried into `web/src/app/globals.css` with its class
   names, so both can be compared side by side; Tailwind is loaded without its preflight so approved spacing does not
   shift.
3. **Server components read, client components act.** Pages fetch FastAPI directly (`API_ORIGIN`); the browser calls
   `/api/*`, which Next rewrites to FastAPI, so there is no CORS surface. Marks are optimistic with undo.
4. **Theme and time zone are cookies.** The server writes `data-theme` into the first byte of HTML (no flash, no
   script) and formats dates in the reader's zone. Last visit is computed in `src/proxy.ts` before render.
5. **Gate unchanged.** The SDE II targeting change alters a long-standing invariant (3+ open-ended and 4+ rejected).
   It is proposed, not activated: section 6.
6. **Old UI stays at FastAPI `/`** until the parity report passes and the owner approves the switch.
7. **Demo tiers are opt-in.** Fictional employer tiers apply only with `ACE_DEMO_COMPANIES=1`.

## 6. Open decisions for the owner

1. **SDE II gate change.** Proposal: a versioned candidate profile (years of experience editable, today about 3), with
   explicit fixtures for 2, 3, 3+, 4+, 5+, ranges, II/III/L4/L5. Before it is switched on, a read-only dry run on the
   live database lists every currently rejected job that would flip, so the change is judged on real cases.
2. **"Scoring failed" as a stored state.** Today a failure is retried silently and shown as "not scored yet". Storing
   failures needs a small additive migration; worth it only if failures are seen in the logs.
3. **Saved.** Removed from navigation; the star stays on rows. Remove the star too, or keep it?

## 7. Plan and acceptance

| Phase | Scope | Accepted when |
| --- | --- | --- |
| 0 | demo data, scoring fix, score states, CI | unit, browser and e2e suites green on demo data; owner sees scores on live data |
| 1 | Next.js at parity, new IA, overview page, parity report | every route PASS in the report, screenshots in both themes at three widths, owner approves switch |
| 2 | typed API, owner-only auth, extension pairing, security tests | anonymous requests refused on every private route; extension paired and filling; rollback tested |
| 3 | Resume Studio foundation: versions, facts, parse QA, deterministic ATS checker | evidence spans and confidence on every score; adversarial fixtures pass |
| 4 | tailoring: requirement mapping, opt-in AI, diff, approval, DOCX/PDF | no fabricated fact passes review fixtures; exports parse |
| 5 | hosting: dated provider research, shadow polling, backups, runbook | refusal rate measured from the cloud; restore drill done; owner approves spend |
