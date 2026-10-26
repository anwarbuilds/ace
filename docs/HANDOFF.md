# ace handoff

For a fresh session, cloud or local, picking this project up cold. Read it
top to bottom (about ten minutes), then start at section 9. Written on
2026-10-10. This repo is PUBLIC, so this file holds no personal data; the
private context arrives in the prompt the session is started with.

The full engineering history is split by topic in `docs/knowledge/` (committed,
personal details removed; index and recurring lessons in `docs/knowledge/README.md`).
Open a topic file only when you work in that area. Everything needed to continue is here.

## 1. What the user is trying to achieve

ace is one person's private career engine. In priority order:

1. **Never miss an opening.** Every full-time, early-career software, ML or
   forward deployed engineering role in the US that the user can take, taken
   from the employer's own posting, announced as soon as it appears, with as
   little noise as possible. Built and running; keep widening coverage.
2. **Make applying fast.** A Chrome extension ("ace autofill") fills
   application forms from an answer bank and never submits. Built, v1.20.0.
3. **A professional web platform, not a prototype.** Real routes, pagination,
   sign-in, a proper home page, and the approved Wine and Rose design in Night
   and Day themes. The Next.js rebuild is complete on `wine-rose-platform`; deployment
   to the user's machine still needs approval.
4. **A strong ATS resume system ("Resume Studio").** Resume versions, an ATS
   score and keyword gaps per job are built. Tailored versions and PDF and
   DOCX export remain later scope.
5. **Run it in the cloud, always on**, as a portfolio-grade project. Not
   started. Decided: build the platform properly first, then deploy.

The user is very particular about UI and judges by looking. Show screenshots,
do not describe. They dislike long chats and token waste: keep replies short.

What the gate admits (the product encodes the user's profile as rules in
`backend/app/intelligence/eligibility.py`, version `2026-10-09-v53`): US
locations; full-time only (contract, freelance, temporary, fixed-term and
contract-to-hire are rejected); early career (new grad and junior roles; a posting that requires 4 or more
years, or an open-ended "3+ years", is rejected: `MAX_REQUIRED_EXPERIENCE_YEARS`,
`MAX_OPEN_ENDED_YEARS`); families software engineering, ML and
forward deployed engineering only (data engineering and data science are
classified but excluded by `INCLUDE_NEW_GRAD_DATA_ROLES = False`); internships
out; postings that explicitly refuse visa sponsorship are rejected. Silence
about sponsorship or experience is never a rejection. Do not re-enable the
excluded kinds unless the user asks.

## 2. Hard rules

**Content and design**
- **No em dashes anywhere the user can see**, typed or drawn: UI text, titles,
  placeholders, emails, the extension, and your own messages to the user. Also
  no en dash used as a dash, no minus-sign toggles, and no CSS rule or bar that
  looks like a dash (a bar before "BIG TECH" got through once). The user has
  asked repeatedly. Guards exist: `undash`/MutationObserver in the Next.js UI,
  `_plain()` in the email, `plain()` in the extension, and the browser scan in
  `backend/tests/browser/scans.py`. Port all of them to the new app.
- The wordmark is **"ace"**, all lowercase. No logo tile, no caption, no
  tagline.
- The current palette is the locked **Wine and Rose V2** system. Night uses wine
  and black; Day uses rose wine and white; System follows the operating system.
  The implementation source is `design/ACE_WINE_ROSE_CODEX_IMPLEMENTATION_KIT/`.
  Do not reinterpret its layout, artwork, colors, typography or spacing.
- No upload or import of application spreadsheets (removed on request).
- Every text pair must pass WCAG AA in both themes.

**Engineering invariants** (each exists because breaking it misled the user)
1. The gate decides inclusion, nothing else. Scores and freshness only order or
   alert; they never hide a qualifying job.
2. Silence is not rejection (missing sponsorship, experience or location info
   is unknown, not a blocker).
3. Identity `(source, source_account, external_id)` never changes; content is a
   SHA-256 hash. A retitled posting is UPDATED, not new plus closed.
4. Never mass-close jobs from one bad or empty response.
5. Evaluation is reproducible: no clock, network or randomness inside the gate.
6. The apply link is the employer's own posting. One registered exception:
   RippleMatch, under its own source type.
7. Store everything, show little. Rejected jobs are kept so rules can be
   re-run over history.

**Security and privacy**
- The GitHub repo (anwarbuilds/ace) is **public**. Never commit personal data:
  fictional fixtures only, real answers live only in the database, never commit
  `.env`, dumps or screenshots with real data. Scan every diff before pushing.
- **Never bypass access controls.** robots.txt is obeyed. A 403, 405 or 429, a
  bot challenge (AWS WAF, Akamai, Cloudflare) or an API that wants a CSRF token
  is a refusal; the scheduler backs off and nothing should work around it. Do
  not hammer sites.
- **Secrets never pass through the conversation.** The user adds them to `.env`
  themselves (for example `RESEND_API_KEY`).
- Extension diagnostics carry no answer values.
- Confirm before anything irreversible or outward-facing: force-push, history
  rewrites, deleting data, spending money.

**Working style**
- Verify against the running system, not memory; state gaps plainly; one change
  at a time; every bug found gets a test that pins it; build before deploy.
- Commit author is the user's configured git identity. Never add a
  Co-Authored-By trailer or mention Claude, Opus, Codex or any AI in commits or
  pull requests, even if a tool asks for one (owner instruction, 2026-10-24).

## 3. State on 2026-10-16

**2026-10-26 employer logo update:** Local website work centralizes employer
identity across lists, job/company details, Analytics, Inbox, Coverage and
Resume Studio. There are 59 authentic local icons and 71 explicit aliases;
FedEx Freight, GM and Southern Company are covered. Encoded company route
names are decoded before evidence queries and logo matching. Unknown, refused
or broken icons retain accessible initials and failed-image state resets when
the employer changes. No backend, Career Dashboard, extension, scheduler or
production data changes. See `docs/architecture/2026-10-26-company-identity.md`
for validation and unavailable sources. Deployment still requires approval;
no browser execution or fresh screenshots due to the cooling restriction.

**2026-10-26 question-following update:** Local 1.28.6 follows clicked/focused
employer questions, fills equivalent known routine answers on focus and records
committed owner answers as Answered on form without duplicate approval. Protected
choices remain per-application; prefills still need one confirmation and ACE
editor drafts still need the explicit fill action. Inputless ARIA dropdowns,
completion invalidation, Memory failure handling and Undo are covered. 58 DOM
contracts, 258 matcher cases, Memory checks, TypeScript, lint, syntax and dash
checks pass. 35 Playwright cases collect only due to cooling. Reload 1.28.6 and
refresh employer tabs; no deployment or publication occurred.

**2026-10-26 drag update:** Local 1.28.5 lifts an embedded form's floating card
into the outer viewport through a tab/frame/document-scoped extension relay.
Form logic stays in the source frame; stale actions are rejected and an
unavailable outer receiver leaves the local card usable. Pointer capture starts
immediately; touch, keyboard, saved position and existing controls remain.
49 DOM contracts, 258 matcher cases, Memory checks, TypeScript, lint, syntax
and dash checks pass. 33 Playwright cases collect only due to cooling. Reload
the extension and refresh employer tabs. No deployment or publication occurred.

**2026-10-26 extension update:** Local 1.28.4 adds owner-authorized automatic
saving of finished routine employer-form answers without per-question approval.
Memory exposes separate Auto-save routine answers and Auto-fill known switches.
Trusted edits, settled readback, protected/motivation exclusions, revision checks
and no-submit remain. 43 DOM contracts, 258 matcher cases, Memory checks,
TypeScript, lint, syntax and dash scan pass. 32 Playwright cases collect only;
browser runs remain suspended for laptop cooling. Reload the unpacked extension
and refresh employer tabs. No production deployment/publication was performed.
See `ACE_NEXT_KNOWLEDGE.md` for the complete current state and limitations.

**2026-10-25 continuity check:** `ACE_NEXT_KNOWLEDGE.md` now distinguishes the local V5.1 extension at `cb7bb5e` from the last independently verified API/database release at `11a7fd4` and the separately recorded website typography release at `61debd6`. The V4 migration 0050 and live Memory API status were not verified in this session. The local branch has two V5.1 commits absent from `origin/wine-rose-platform`; the tracked remote has three typography commits absent locally. Reconcile both lines before pushing or releasing. A root `AGENTS.md` and the root `CLAUDE.md` direct future agents to the continuity file.

**2026-10-24 extension update:** ACE Focus Mode V5.1 is implemented locally in the existing MV3 extension on `wine-rose-platform`. The panel is a compact floating card with Review, Workspace, a minimized dock, free dragging, persisted position, Day/Night themes, native and supported listbox option mirroring, and persistent Review completion. Employer-motivation questions are excluded from scan, fill, Review, Memory reuse and progress; older records are retained on the server. This update requires no database migration and has not been deployed or published. See `extension/README.md` and `web/tests/e2e/extension-focus-v5.spec.ts` for usage and browser verification.

**2026-10-25 speed, second round:** production timings (`backend/scripts/time_pages.py`) showed `/api/stats` 216 ms, Career Dashboard 2.5 s and Coverage 3.4 s; totals now take two passes, list pages fetch only what they show, skill extraction is 6.4x faster with identical results, Coverage's sponsorship list is a background snapshot, and job links no longer prefetch. Production is at migration 0050.

**2026-10-25 speed:** PostgreSQL JIT cost about 0.5 s per queue query; app connections now turn it off, every workspace route has a loading screen, same-route clicks dim the page, and no text field outside sign-in keeps browser history. See `ACE_NEXT_KNOWLEDGE.md`, Speed and responsiveness.

**2026-10-25 theme sync and Close:** the V5.1 card follows the computer's Day or Night setting until the owner picks one (`aceStudioThemeMode`), and has a Close X in the header and dock that reuses the existing dismiss path. 22 Chrome extension tests pass. Reload the unpacked extension to use it.

**2026-10-25 visual correction:** The Focus compact and Review card now use the approved V5.1 geometry, colors, typography, borders and icons. A Workday Search For Jobs route is excluded even when its filters resemble application questions, including after SPA navigation. The local extension regression suite has 7 passing Chrome tests. Reload the unpacked extension and refresh employer tabs to see these local changes; no deployment or publication was performed.

The current production migration record is `ACE_NEXT_KNOWLEDGE.md`. Read it
before any database copy, Oracle deployment, Google OAuth setup or scheduler
cutover. It records the aggregate live inventory, staged migration, rollback,
backup and owner input requirements.

- **Typography refresh (2026-10-24, on `wine-rose-platform`):** the approved Refined typography only: self-hosted
  Inter (SIL OFL), one token scale in `web/src/app/globals.css`, sentence case labels, tabular numbers, colour emoji
  fallbacks. Layout, colours and text unchanged; evidence method in `docs/knowledge/05`. The extension panel and popup
  use the same face and scale (`docs/knowledge/06`). Live on https://ace.opik.net since 2026-10-24 (frontend commit
  `61debd6`, web container only). Chrome shows the extension change once its folder is updated and reloaded.
- **Live** on the user's machine via `compose.yaml`: postgres (host port 5433),
  migrate, scheduler, web (port 8000, FastAPI serving the old UI at `/`). Built
  from the tree at commit 4f516ef. The user's machine is the only deployment.
- About 2,090 enabled sources (about 2,050 polled), about 1,250 qualifying active
  jobs, roughly 600 applications tracked, a 66 row answer bank. The scheduler
  polls continuously (five minute cycles; Google every 30 minutes) and alerts
  are one email per closed 15 minute pull.
- Tests on `wine-rose-platform`: 1,191 backend tests (hermetic SQLite), 89 Next.js Playwright tests against fictional demo
  data, and 185 extension matcher cases. The retired single-file UI suite was removed; extension DOM tests remain.
- Done this week: own-site readers for Atlassian, EA, Apple, Shopify, AMD, SIG,
  Booking.com, Groq, Google, Meta, Intuit, Arm, Synopsys and about 25 more
  boards; gate v46 to v53; the full anthracite redesign (web, extension, email),
  night and day, then a step darker; em dash guards and the drawn dash scan.
- 2026-10-12: a posting the user applied to that an employer lists again (new id, no mark) now shows
  "Applied before, Oct 4" on its row, job page, group header, desktop notification and alert email. Derived on
  read in `applications/prior.py`, never stored, and compares requisition numbers so two open listings that differ are
  called possibly separate openings; see `docs/knowledge/04`.
- **2026-10-14, branch `next-app` (cloud session, demo data only):**
  - Resume scoring fixed: the scheduler now scores, after every cycle, active PASS jobs with no current score for the
    active resume (new, changed since scoring, or from an older algorithm), at most 2,000 per cycle. The API returns
    `match_state` (scored, pending, no_description, insufficient, no_resume) so no page says "n/a" or "could not read"
    for a job that simply was not scored yet. Not yet run on the live database: after pulling, rebuild and watch the
    scheduler log for `jobs_scored count=`.
  - `backend/scripts/seed_demo.py` builds a fictional demo database (SQLite or empty PostgreSQL); `db/session.py`
    branches on dialect. Demo tiers apply only with `ACE_DEMO_COMPANIES=1`.
  - The Next.js app in `web/` works against FastAPI: every page of the old UI under the new names (section 9), URL-held
    filters, sort and numbered pages, palette with role search, marks with undo, dash guards. Old UI still at `/`.
  - CI added (`.github/workflows/ci.yml`): unit, extension, web build, both browser suites on demo data.
  - Baseline, gap matrix, decisions and open questions: `docs/architecture/2026-10-14-baseline-and-plan.md`.
  - Overview at `/app`, Saved star removed (data kept), new grad first by default, `/api/system` health and
    `/api/export.json`; candidate profiles (`ACE_TARGET_PROFILE`, sde2 off until the owner approves a dry run).
  - **Sign-in (Phase 2):** owner-only, argon2id, DB sessions, CSRF, throttling, extension pairing (extension
    1.21.0), rollback `ACE_AUTH=disabled` (local peers only). Migration 0038. Demo owner `demo@ace.example` /
    `ace demo password` exists only in generated demo databases. Details: `docs/knowledge/07`. On the live database
    the owner runs `create_owner` once and pairs the extension; until then the API answers 401 (or set
    `ACE_AUTH=disabled` for a local rollback).
  - **Approved auth surface (2026-10-15, branch `auth-approved-design`):** `/login` now uses the locked Day and
    Night cinematic design with live DOM controls and the existing owner session flow. Email opens the real sign-in
    form. Google and Microsoft remain honest unavailable states because no OIDC backend exists. `/logout` revokes
    the server session before sending the browser to the exact `/signed-out` success screen. `/` is a public
    informational page, with public `/terms` and `/privacy`; private `/app/*` routes and extension token scopes are
    unchanged. Canonical capture command: `cd web && API_ORIGIN=http://127.0.0.1:18000 npm start`, then
    `WEB_URL=http://127.0.0.1:3000 CHROMIUM_PATH=/usr/bin/google-chrome node scripts/capture-auth-screenshots.mjs`.
  - **Approved Wine and Rose platform (2026-10-15, branch `wine-rose-platform`):** all public, auth and workspace
    routes use the locked V2 Night and Day design. The home and auth views render the complete angular A as live
    DOM artwork. Pulls remains the post-login home. Application totals now come from the backend's combined posting
    and external application history, update optimistically across the shell, synchronize across tabs, persist after
    refresh and roll back on save failure. `scripts/no_user_facing_dashes.py` scans production sources. Visual evidence
    is kept locally under ignored `artifacts/wine-rose/`; implementation baseline and decisions are in
    `docs/architecture/2026-10-15-wine-rose-baseline.md`.
  - **Legacy backend parity (2026-10-15):** the one commit added to `main` after the branches diverged was carried
    forward. Resume activation now scores only active qualifying and marked jobs instead of the entire historical
    corpus. This preserves visible scores while avoiding the 45 minute live upload observed on the legacy system.
  - **Production bridge (2026-10-16):** optional owner-only Google OIDC is wired to the existing owner and cannot
    create an account; migration 0041 stores Google's stable subject. An idempotent bridge copies legacy resume
    history into Resume Studio without changing the matcher's active resume or triggering a rescore. Aggregate-only
    inventory tooling and a single-VM Oracle Compose, Caddy and backup kit are in `deploy/oracle/`. The live legacy
    scheduler and database were not changed. See `ACE_NEXT_KNOWLEDGE.md` for the required rehearsal and cutover.
  - **Email verification (2026-10-16):** production password sign-in now verifies an eight-character email code
    before creating a session. Forgot password sends a separate code before accepting a replacement password. Both
    code types expire after 10 minutes, are hashed, single use and throttled. Oracle sets
    `REQUIRE_LOGIN_EMAIL_CODE=true`, which fails closed if Resend cannot deliver. Google OIDC continues to use its
    verified email claim and does not add a second ACE email step.
  - **Account creation in the browser:** the first visit to `/login` (or the old UI) offers "Create your account"
    while no owner exists; refused afterwards; from a public address it needs `SETUP_TOKEN`. The web app listens on
    127.0.0.1 because Next's rewrites do not forward the browser's address.
  - **Resume Studio foundation:** documents kept as uploaded, a career knowledge base with suggested, verified,
    needs clarification and retired facts and an audit trail, versions with a primary one feeding the job list, and a
    deterministic ATS checker with evidence quotes, unknowns and history. Migration 0039. `docs/knowledge/09`.
  - **Website layout:** top navigation and a department strip instead of the sidebar, whole-page scrolling with a
    footer, browse groups at `/app/browse/<slug>`, a shop-front home, company directory and pages. `docs/knowledge/05`.
  - **Pulls is home** (`/app`), focused navigation, a Dashboard page, no command palette, `/api/sessions` from about
    144 queries to 8. `docs/knowledge/05`.
  - **Pulls-first shell (2026-10-15)**, after the owner's approved prototype: sidebar in three groups, top bar with
    live, delayed or stalled, `/app/pulls` as home, `/app/analytics` (was Dashboard), `/app/extension` (pairing), a
    phone bottom bar. `/api/pulls` serves 15 minute windows with an honest metric contract; migration 0040 adds
    attempts and failures per window (older windows say not recorded). Deep links survive sign-in. Details:
    `docs/knowledge/05`. The web app forwards `/api/*` at runtime (`web/src/app/api/[...path]/route.ts`), so a build
    no longer bakes in API_ORIGIN.
  - **Pulls-first completion (2026-10-15):** the sidebar now collapses and remembers the choice; Analytics has URL
    backed 14, 30 and 90 day trend ranges plus a discovery role-family filter. The obsolete Browse and Companies
    pages redirect to Opportunities and their code is gone. FastAPI `/` redirects to Next.js and the legacy HTML was
    removed. Compose now has separate `api` and `web` services on local ports 8000 and 3000. Geist is bundled from
    the installed Next package, so production builds do not contact Google Fonts.
  - Hazard: the live compose (built from `main`) cannot migrate a database already upgraded by `next-app` (alembic
    cannot locate 0037 or 0038). Do not rebuild the live stack from `main` against a database `next-app` migrated;
    merge first.
- Alerts are composed but **not delivered**: `RESEND_API_KEY` is not set, so each
  pull logs `mail_not_configured`. Only the user can add the key.
- `README.md` now reflects the Next.js runtime and current test counts. Live source and posting totals remain the
  last recorded production figures until the approved deployment verification.
- User side, not yours: add `RESEND_API_KEY`; reload the extension at
  `chrome://extensions` (1.20.0, it never reloads itself); a private cleanup
  item the prompt mentions.

## 4. System map

```
sources -> adapters -> persist and diff -> eligibility gate -> freshness
        -> materialize -> API -> UI, extension, alert email
```

| Area | Path | Notes |
| --- | --- | --- |
| Readers per ATS | `backend/app/adapters/` | greenhouse, lever, ashby, workday, smartrecruiters, workable, eightfold, jibe, avature, apple, google, atlassian, shopify, gem, ibm, amazon, oracle_recruiting, feeds (simplify, ripplematch), sitemap_jobs. One fetch path per provider, retries for transient errors, conditional HTTP where it works |
| Gate | `backend/app/intelligence/` | `eligibility.py` (rule version), `roles.py` (families, patterns), `companies.py` (tiers) |
| Scheduler | `backend/app/scheduling/`, `backend/scripts/run_scheduler.py` | concurrent polling, re-reads sources between cycles, health check `scheduler_health.py` |
| Persistence | `backend/app/persistence/`, `backend/app/db/models.py`, `backend/migrations/` | Alembic, 36 revisions; JSONB with a JSON fallback so tests run on SQLite |
| Discovery and coverage | `backend/app/discovery/`, `backend/app/coverage/` | finds boards from feed links, probes companies, audits what ace cannot see |
| Matching | `backend/app/matching/` | lexical skills match, related-skill partial credit, skills gap |
| Answers, applications | `backend/app/answers/`, `backend/app/applications/` | answer bank catalogue; application tracking and export |
| Alerts | `backend/app/alerts/service.py` | one HTML email per closed pull, via Resend |
| API | `backend/app/api/main.py`, `queries.py`, `marks.py` | FastAPI; every `/api/` response is `no-store` |
| Web UI | `web/` | canonical Next.js multi-route app; FastAPI `/` redirects to `/app/pulls` on `WEB_BASE_URL` |
| Extension | `extension/` | MV3: `content.js` (panel in a shadow root), `fields.js` (question matcher), `popup.html/js`, `background.js`, `test-rules.js` |
| Tests | `backend/tests/` | browser tests in `backend/tests/browser/` drive real Chrome over DevTools |
| Next.js app | `web/` | the new app: `src/app/app/*` routes, `src/lib/listState.ts` (URL state), `src/components/`; Playwright in `web/tests/e2e` |

Terms: **PASS/REJECT** gate outcome. **Pulls** are poll sessions, grouped by run.
**Feed** sources (simplify, ripplematch) list roles before the employer board is
read; ace registers the employer boards that feed links name. **Unverified**
postings (requirements unreadable) are shown but marked. **Tiers**: BIG_TECH,
TOP_TIER, ESTABLISHED, OTHER. **Marks**: saved, reviewed, dismissed (together the
archive), applied with a status (Applied, Screening, Interviewing, Offer,
Accepted, Rejected, Withdrawn, No reply) and a note.

## 5. API the new front end consumes

All JSON and owner authenticated. Read `main.py` for exact shapes; OpenAPI response
bodies are untyped, so hand-write TypeScript types (or, better, add Pydantic
response models to FastAPI and generate them).

| Method and path | Purpose |
| --- | --- |
| `GET /api/jobs` | one page. Filters: `status` (default PASS), `family`, `priority`, `company`, `exclude_company`, `source`, `tier`, `q`, `max_age_days`, `max_detected_age_days`, `include_old`, `early_career_only`, `experience_fit_only`, `new_grad_only`, `verified_only`, `min_match`, `mark` (saved, archived, applied), `session_id`, `since`, `active_only`. `sort` is a comma list that combines (unknown keys are dropped). `limit` default 50, max 200, plus `offset`. Returns `items, total, limit, offset, has_more, sort, resume_id` |
| `GET /api/jobs/{id}` | one job, resolves even after it closes |
| `GET /api/stats` | headline counts under the same filters, plus `last_poll_at` |
| `GET /api/facets` | companies, sources, families, priorities, statuses, sorts |
| `GET /api/sessions` | pulls with their best arrivals |
| `GET /api/marks`, `PUT /api/marks/{id}` | counts; partial update (`saved`, `review_state`, `clear_review`, `applied`, `application_status`, `status_note`) |
| `GET/PUT /api/answers` | answer bank rows `{label, value}` |
| `GET/PUT /api/history/{work\|education}` | repeating form sections |
| `GET/POST /api/resume` | active resume and skills; POST uploads and rescores |
| `GET /api/coverage`, `POST /api/sources` | what ace cannot see; add a company by name or URL |
| `GET /api/applications/external`, `/export.csv` | applications with no stored posting; CSV |
| `POST /api/applications/preview` and `/import` | no UI uses them now; candidates for removal |
| `GET /healthz` | liveness |

A job object carries id, company, title, location, official_url, source,
eligibility_status, role_family, company_tier, required_experience_years,
posted_at, first_seen_at, last_seen_at, is_active, is_early_career,
requirements_verified, match_score, matched_skills, missing_skills,
related_skills, related_evidence, previous_match_score, is_saved, review_state,
application_status, status_note, applied_at. Match tiers: HIGH at 70 and above,
MEDIUM at 45 and above, otherwise MINIMAL, null is "not scored".

## 6. Design system (source of truth: `:root` blocks at the top of `index.html`)

Fonts: Inter for the interface (self-hosted, typography tokens in `globals.css`), Geist Mono for code and keys
only. Sidebar 244 px, gutter 32 px. Radii 5, 7, 9, 14,
20. Motion 110, 170, 280 ms; ease-out `cubic-bezier(.2,0,0,1)`.

| Token | Night | Day |
| --- | --- | --- |
| canvas / sidebar | #1F2628 / #1A2022 | #E2E7E7 / #D9DFDF |
| surface 1 / 2 / raised | #293133 / #2F383A / #363F42 | #ECF0F0 / #DDE3E3 / #F4F7F7 |
| text / secondary / muted | #F1F3F3 / #B8C0C2 / #A7B0B2 | #1F2628 / #3F4A4D / #4E5A5D |
| accent / hover / text | #E50914 / #F6121D / #FF8A8F | #D90B15 / #E50914 / #A50C15 |
| match, warning, danger, info | #5BE083, #F7B84B, #FF9C9C, #86BFFF | #0E6532, #7A4900, #A11F15, #1A54A8 |
| tier big / top / established | #F1F3F3 / #A3ACAE / #4F595B | #1F2628 / #56625F / #B5BEBF |

Borders are the text colour at 8 to 22 percent alpha. White on the accent is
4.79 (night) and 5.24 (day). Components to carry over: wordmark; company
monogram tiles (initials on a hue hashed from the name); tier rail on each row
(big tech brightest, with a glow); match ring and bar; a sliding-pill tab group;
a hover action dock on rows; spotlight cards and a glow on the job page; a
floating "Answers" button that opens a drawer; a Ctrl or Cmd+K command palette;
toasts with undo; a live indicator ("Live, updated just now") with stale
detection; empty states that say what to do.

## 7. Feature inventory of the old UI (the parity checklist)

- **Queue**: tabs All, Highly matched, New for you (since last visit), Latest
  pull; search (`/` focuses it); eight combinable sorts shown as ordered chips
  (Not applied first, Fits my experience, New grad first, Best match, Big tech
  first, Newest, Oldest, Company) with a sentence saying what the combination
  does; filters for company tier, early career, new grad, plus company include
  and exclude, source, family, age; a "last visit" divider; rows with company,
  role, location, experience chip, match, status, age.
- **Job page** (`#job/<id>`): hero; resume match card; skills you have, partial
  credit via related skills, skills missing; why it is in the queue; actions
  (open the official posting, save, reviewed, not relevant, applied); status
  grid with a note; details (first detected, last confirmed, source,
  requisition).
- **Pulls**, **Saved**, **Applied** (with applications that have no stored
  posting, and Export CSV), **Archive**.
- **Resume** and **Skills** (gaps ranked by demand, by family): to be replaced
  by Resume Studio.
- **Answers**: the answer bank editor (yes/no as two buttons, month and year
  selectors for work and education history).
- **Coverage**: what ace cannot see, grouped by reason, a box to add a company,
  and the miss audit ("caught late", "feed only").
- **Settings**: Night, Day, System; pipeline stats; active resume; sources.
- Desktop notifications (opt in), `Ctrl/Cmd+K`, and keys: `j`/`k` or arrows,
  `Enter` open, `o` posting, `s` save, `e` reviewed, `x` dismiss, `a` applied,
  `Esc`.

## 8. Next.js 16 notes (read `web/node_modules/next/dist/docs/` before coding)

`web/AGENTS.md` says this is not the Next.js you know; obey it. Already checked:
Next 16.3.8, React 19.2.8, Tailwind 4, Turbopack by default; `params` and
`searchParams` are Promises; `proxy.ts` replaces `middleware.ts`; with
`cacheComponents: true` navigation keeps component state and scroll (Activity),
which suits a list you return to; `rewrites()` can forward `/api/*` to FastAPI;
`PageProps` and `LayoutProps` are generated types. Re-read the guide for any API
you use that is not listed here.

## 9. The plan, in order

**Step 0 and 0b: done on `next-app`** (demo database, scoring sweep, score states, CI). Verify on the live database
after merging.

**Phase 1. Next.js app at parity in `web/`: in progress.** Built: shell, Opportunities (was Queue), job page, Activity
(was Pulls), Applications (was Applied), Archive, Saved (kept, out of navigation), Resume Studio (today the old Resume
page), Skills, Answers, Coverage, Settings, palette, toasts with undo, keyboard flow, numbered pages. Old names
redirect. Remaining: a signed-in overview at `/app`, the page by page parity report with old and new screenshots, and
the switch of FastAPI `/` (only with the owner's approval). The master brief's route names and phases are in
`docs/architecture/2026-10-14-baseline-and-plan.md`; it supersedes the route list that used to be here.

**Phase 2. Sign-in: done on `next-app`** (2026-10-14, extended 2026-10-16). Owner from the CLI, no sign-up; cookie
sessions with CSRF; throttling; one-time email codes for production password sign-in and password recovery;
extension pairing token limited to answers and history; rollback switch. Remaining from the brief: typed API
(Pydantic response models and generated types).

**Resume Studio foundation: done on `next-app`** (2026-10-14): knowledge base, versions, checker. Next: tailoring
without AI (map requirements to verified facts, propose reorderings and wording drawn only from them, side-by-side
diff, approve), DOCX export into the owner's template and PDF, durable jobs.

**Phase 3. Home page and onboarding.** A public landing page at `/`; a signed-in
home (new roles today, highly matched, pipeline funnel, poll health, coverage
gaps); first-run onboarding (target families, locations, resume, answer bank).

**Phase 4. Resume Studio.** Versions, parse checks, an ATS score and keyword gaps
per job from stored descriptions and `matching/`, tailored versions the user
edits (never invent experience), PDF and DOCX export (`python-docx`,
`pdfplumber`, `pypdfium2` are already dependencies). Ask the user for design
preferences before building; it is a large product area.

**Phase 5. Cloud on Oracle Cloud Always Free** (2026-10-14: the owner will not pay for hosting): one VM running the
same compose stack (Postgres, API, scheduler, Next.js) behind Caddy for HTTPS, backups to Object Storage, a restore
drill. Keep it portable (containers, Postgres, S3-compatible storage). Confirm the free tier limits on the day. The scheduler uses about 1.4 GB RAM and 20 percent
CPU, the database is about 1.8 GB. **Risk**: some boards (Cloudflare, Akamai)
block datacenter addresses that a home connection gets through; measure the
refusal rate from the cloud before cutting over.

## 10. Running and testing

On the user's machine (the only place that can deploy):

```
cd ~/Documents/ace
docker compose build migrate scheduler api web
docker compose up -d migrate scheduler api web
curl localhost:3000/healthz
curl localhost:8000/healthz
```

Tests:

```
.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/browser   # 1173, hermetic
node extension/test-rules.js                                                 # 185 cases
cd web && npm run check:dashes && npm run typecheck && npm run lint && npm run build
cd web && npx playwright test                                                # 87 cases, fictional demo data
ACE_BROWSER_TEST_URL=http://127.0.0.1:8000 \
  .venv/bin/python -m pytest backend/tests/browser -q                        # ~4.5 min
```

Browser tests need Chrome, `websocket-client` (not in `requirements.txt`) and an
app with realistic data; they skip rather than fail when either is missing. To
try a UI change without touching the live app, run a second `uvicorn
backend.app.api.main:app --port 8001` and point `ACE_BROWSER_TEST_URL` at it.

Demo data and the new app, anywhere (no live database needed):

```
.venv/bin/python -m backend.scripts.seed_demo                       # writes ace-demo.db, fictional
ACE_DEMO_COMPANIES=1 DATABASE_URL=sqlite:///ace-demo.db \
  .venv/bin/uvicorn backend.app.api.main:app --port 8000
cd web && npm ci && npm run dev                                     # http://localhost:3000, API_ORIGIN defaults to :8000
npx playwright test                                                 # writes marks: demo data only
```

In a cloud session: `python -m venv .venv && .venv/bin/pip install -r
backend/requirements.txt websocket-client`, the unit tests work as is, `cd web &&
npm ci`. You cannot reach the user's database, scheduler, `.env` or the
extension in their browser. Work on a branch and open a pull request; main stays
deployable, and the live app only changes when the user pulls and rebuilds.

## 11. Operational gotchas (the short list; the rest is in `docs/knowledge/08-operations-and-testing.md`)

- `docker compose build` before `up`; containers bake the source. `migrate`,
  `scheduler` and `api` use the Python image; `web` uses the Next.js image.
- Run backend maintenance with `docker compose exec api ...`.
- Containers run on UTC. Any date shown to a person goes through
  `settings.display_timezone`.
- The extension does not reload itself; unpacked extensions need the refresh icon
  at `chrome://extensions`, and only newly opened pages pick it up.
- Browser tests run against a live server; restarting it mid-run causes "the app
  rendered nothing" failures, so re-run.
- A restart no longer re-polls everything, but do not restart in a loop.
- A registered source is picked up within one cycle with no restart.
- psycopg generic plans can ignore expression indexes: use
  `literal(..., literal_execute=True)` for index constants. Test a suspect query
  with `PREPARE` and `plan_cache_mode = force_generic_plan`.
- After a gate version bump, re-evaluate rows that are currently PASS first
  (minutes); the full corpus backfill runs at about 25 jobs per second.
- Export control is not citizenship: only ITAR, an explicit citizenship demand,
  or access without a licence blocks.
- "US" beside Canada is the US; a remote "Americas" role is open to the US.
- A numeral in a title ("Software Engineer III") is judged by stated years,
  senior when none are given.
- Unreachable, and left alone: Tesla, Citadel, Citadel Securities, D. E. Shaw,
  LinkedIn, Equinix (bot protection or robots.txt). IBM is read from its site
  search API because the careers site sits behind a WAF challenge.
- Transient errors (429, timeouts) record nothing and skip the provider for the
  run; they never switch a board off.

## 12. Decisions, newest first

- 2026-10-14: owner answered the open questions: experience is 3 years; new grad first, SDE II also targeted (behind
  the profile switch); Resume Studio starts with no AI (deterministic), a provider can be added later; templates
  adapt to an uploaded DOCX; hosting must cost nothing, so Oracle Cloud Always Free replaces Render; the Saved star
  is removed. Sign-in shipped with extension pairing and a local-only rollback switch.
- 2026-10-14: master brief adopted as the spec for new scope. Route names changed (Opportunities, Activity,
  Applications, Resume Studio, Skills under insights); Saved left the navigation, its data and route kept. Theme and
  time zone are cookies. SDE II targeting proposed, not active, pending the owner's approval of a dry run.

- 2026-10-15: the approved Wine and Rose V2 demo supersedes the anthracite palette across the Next.js platform.
  Pulls remains home, all metrics use real backend data, and application totals update optimistically and consistently.
- 2026-10-10: darker anthracite (night and day); no drawn dashes; platform
  rebuild decided: one private user, Next.js and TypeScript, email and password,
  Render; phases above. Resume Studio will replace Resume and Skills.
- 2026-10-09: data engineering and data science excluded again after being
  included for a day. Contract-to-hire stays rejected until the user asks.
- 2026-10-08 to 09: own-site readers (robots.txt respecting) for the companies
  listed in section 3; wider board discovery sweep.
- 2026-09-06: internships out, email subsystem removed then replaced by one
  alert per pull, matching v2 (related skills), interface as a triage tool.

## 13. First moves for the next session

1. Before daily-use rollout, merge `next-app`, back up Postgres, run migrations, rebuild all four application images,
   and verify Pulls against live data read-only. This needs the owner's explicit deployment approval.
2. Confirm new Pulls windows show checked, answered, failed and attempts; pre-0040 windows must say not recorded.
3. Later scope: Resume Studio tailoring and DOCX/PDF export, the Oracle Always Free kit, and the SDE II dry run.
4. Do not switch on the SDE II gate change until the owner approves the dry run (baseline doc, section 6).

## 14. Keeping this current

Knowledge only compounds if it is written down and pushed. Before ending any session:

1. Update section 3 (state) of this file, and section 9 if the plan moved. Keep the file under 450 lines; move detail
   into `docs/knowledge/`.
2. Add a dated entry to the right topic file in `docs/knowledge/` for anything learned or reversed (its README says how),
   and a Status line on anything the entry supersedes.
3. Commit the docs with the code, push, and open or update the pull request. A cloud session starts from what is on
   GitHub, so ask the user to merge, or start the next session from the work branch.
4. No personal data in either place: this repo is public.
