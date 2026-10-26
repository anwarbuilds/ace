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

**2026-10-26 Inbox clarity (live: website `176744f`, API `c7d3451`):** Inbox now checks Gmail
when opened, while open and on one Sync now button, and a status card says whether everything
is in. Email shows exactly as it arrived (rebuilt HTML in a sandboxed frame, no scripts, no
remote pictures). Choices add Recruiter reply, Acknowledgement and Status update. Parser 3
never files a thanks-then-rejection email as a receipt and re-reads ACE-filed receipts.
Analytics shows "Rejected companies" with totals and roles; rejected applications have search
and pages. Released with a verified backup; only API/web changed. `c7d3451` also makes
Analytics count outcomes recorded from email (they were dropped). Owner: press Sync now once.
See `ACE_NEXT_KNOWLEDGE.md`, Inbox clarity and Rejected companies deployed.

**2026-10-26 production release:** API/web are healthy at `21f563a`; logo work,
quick fill 1.29.0 and the existing Inbox fixes are included. All Analytics tabs
and logo assets passed signed-in HTTP checks; application records stayed 929.
Only API/web containers changed; schema 0050, environment and scheduler remain.
Reload the unpacked extension and refresh employer tabs. Browser checks remain
pending due to cooling. Evidence: `architecture/2026-10-26-quick-fill-release.md`.

**2026-10-26 quick fill:** Local extension **1.29.0** replaces the main review/
remember workflow with one **Fill all known answers** action and a shorter
question editor. One verified routine answer fills equivalent empty prompts;
private saving runs in the background and failures do not reopen completed
fields. Repeated controls have distinct identities; job dates/current-job
choices stay tied to saved history. Minimize, full-viewport dragging, themes,
protected decisions and motivation exclusions remain. 65 DOM contracts, 258
matcher cases, Memory safety, TypeScript, lint, syntax, dash checks and the web
build pass. Browser testing remains suspended for cooling. Reload the unpacked
extension and refresh employer tabs; nothing was deployed or published.
Work branch: `extension-quick-fill-20261026`, based on logo commit `2a2982e`.

**2026-10-26 Inbox and Analytics update:** Clear rejection emails matched to exactly one
application (job ID including "Ref:", exact title, or the only application at the named
company) are recorded automatically from sync, historical import and a new recheck, with
Undo; receipts are filed; everything else is one click with the full email (read live) and
ACE's best-guess application preselected. Analytics lists the companies that rejected the
owner. Career Dashboard and `/api/intelligence` are removed; `/app/dashboard` redirects to
Analytics. `GMAIL_AUTO_REJECTIONS` (default true) is the server switch. No migration.
See `ACE_NEXT_KNOWLEDGE.md`, Inbox automatic rejections.


**2026-10-26 automatic employer logos:** Review branch
`company-logo-consistency-20261026`, draft PR #1, now handles future employers
automatically through `/api/company-logo`. The 59 bundled icons/71 aliases are
an optional fast path. Exact registered sources provide employer branding;
no guessed domains, ATS favicon substitutions or external history disclosure.
A bounded, private asset cache and image decoder serve small PNGs while initial
fallbacks stay visible. Auth, application state, polling and scheduler are
unchanged; no migration or deployment. Shopify outside the bundle passed a
real public discovery and authenticated local proxy check against fictional
data. See `docs/architecture/2026-10-26-company-identity.md` for validation,
limits and changed files. Browser screenshots remain pending due to cooling.

Historical state notes from earlier extension and platform releases are retained
in [the handoff state archive](knowledge/11-handoff-state-archive.md). Use
`ACE_NEXT_KNOWLEDGE.md` for current verified production state, deployment controls,
backups and migration evidence before operating production.

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
