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
   sign-in, a proper home page, a polished anthracite grey design in a night
   and a day theme. The old single-file UI is live and polished; the Next.js
   rebuild has only been scaffolded.
4. **A strong ATS resume system ("Resume Studio").** Resume versions, an ATS
   score and keyword gaps per job, tailored versions, PDF and DOCX export.
   Not started.
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
  asked repeatedly. Guards exist: `undash`/MutationObserver in the old UI,
  `_plain()` in the email, `plain()` in the extension, and the browser scan in
  `backend/tests/browser/scans.py`. Port all of them to the new app.
- The wordmark is **"ace"**, all lowercase. No logo tile, no caption, no
  tagline.
- Palette is **anthracite grey (RAL 7016, #293133)**, not near-black. Night and
  day versions, plus System. The user found the first version a bit light and asked for
  both themes darker; never lighten. Red is budgeted: the active indicator, the one primary action.
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
- Commit author is the user's configured git identity. End commits with the
  attribution trailer the harness gives you.

## 3. State on 2026-10-10

- **Live** on the user's machine via `compose.yaml`: postgres (host port 5433),
  migrate, scheduler, web (port 8000, FastAPI serving the old UI at `/`). Built
  from the tree at commit 4f516ef. The user's machine is the only deployment.
- About 2,090 enabled sources (about 2,050 polled), about 1,250 qualifying active
  jobs, roughly 600 applications tracked, a 66 row answer bank. The scheduler
  polls continuously (five minute cycles; Google every 30 minutes) and alerts
  are one email per closed 15 minute pull.
- Tests: 1009 unit (hermetic, SQLite, ~20 s), 101 browser (one skips when the
  live data lacks a recent check with a job), 185 extension matcher cases.
- Done this week: own-site readers for Atlassian, EA, Apple, Shopify, AMD, SIG,
  Booking.com, Groq, Google, Meta, Intuit, Arm, Synopsys and about 25 more
  boards; gate v46 to v53; the full anthracite redesign (web, extension, email),
  night and day, then a step darker; em dash guards and the drawn dash scan.
- **Known issue, found 2026-10-10, not fixed: resume scores never refresh.**
  `rescore_corpus` (`backend/app/matching/service.py`) runs only from
  `POST /api/resume`. Every row in `job_resume_scores` (31,445) dates from one
  batch on 2026-09-06. Jobs found since, 1,238 of the 1,249 in the queue, have
  no score, and the job page tells the user "ACE could not read this posting",
  which is wrong for them. See Step 0b.
- Alerts are composed but **not delivered**: `RESEND_API_KEY` is not set, so each
  pull logs `mail_not_configured`. Only the user can add the key.
- `README.md` is stale (472 sources, 706 tests, old UI). Refresh it when
  convenient.
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
| Old UI | `backend/app/api/static/index.html` | one file of vanilla JS, source of truth for the design tokens and behaviours |
| Extension | `extension/` | MV3: `content.js` (panel in a shadow root), `fields.js` (question matcher), `popup.html/js`, `background.js`, `test-rules.js` |
| Tests | `backend/tests/` | browser tests in `backend/tests/browser/` drive real Chrome over DevTools |
| Next.js app | `web/` | scaffold only: create-next-app 16.3.8, nothing wired up |

Terms: **PASS/REJECT** gate outcome. **Pulls** are poll sessions, grouped by run.
**Feed** sources (simplify, ripplematch) list roles before the employer board is
read; ace registers the employer boards that feed links name. **Unverified**
postings (requirements unreadable) are shown but marked. **Tiers**: BIG_TECH,
TOP_TIER, ESTABLISHED, OTHER. **Marks**: saved, reviewed, dismissed (together the
archive), applied with a status (Applied, Screening, Interviewing, Offer,
Accepted, Rejected, Withdrawn, No reply) and a note.

## 5. API the new front end consumes

All JSON, no auth today. Read `main.py` for exact shapes; OpenAPI response
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

Fonts: Geist and Geist Mono. Sidebar 244 px, gutter 32 px. Radii 5, 7, 9, 14,
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

**Step 0. Make the project runnable anywhere** (a cloud session has no database).
Write `backend/scripts/seed_demo.py`: fictional companies and jobs only (the repo
is public), at least 25 companies and a few hundred jobs across tiers, families,
experience and status, plus marks, 66 or more fictional answers, a fictional
resume with skills, and a few pulls. Aim at SQLite first: `backend/tests/
test_web_api.py` already builds the API on in-memory SQLite (`session_factory`,
`add_job`), and `models.py` falls back from JSONB to JSON. `db/session.py` passes pool arguments that an in-memory
SQLite engine rejects, so use a file database or branch on dialect. If something needs Postgres,
install it. Done when `uvicorn` serves `/api/jobs` from the demo database and the
browser tests pass against it.

**Step 0b. Fix resume scoring** (section 3). Score each job when it is persisted
or evaluated, or sweep PASS active jobs with no row for the active resume at the
end of each scheduler cycle; keep `rescore_corpus` for uploads. Test first on
SQLite. Change the job page copy so "not scored yet" and "could not read" differ.
Verifying on real data and deploying must happen on the user's machine.

**Phase 1. Next.js app at parity in `web/`.** TypeScript strict, Tailwind 4 with
the tokens above as CSS variables, `data-theme` set before paint (no flash),
Geist through `next/font`. Server components fetch through `API_ORIGIN`; client
mutations use optimistic updates and a toast with undo. Routes: `/login`,
`/app/queue`, `/app/jobs/[id]`, `/app/pulls`, `/app/saved`, `/app/applied`,
`/app/archive`, `/app/resume`, `/app/skills`, `/app/answers`, `/app/coverage`,
`/app/settings`. Filters, sort and page live in the URL; numbered pagination
replaces infinite scroll. Port the em dash guards. Test with Playwright: both
themes, the drawn dash scan, the text scan, keyboard flow. Keep the old UI at
FastAPI `/` until parity, then switch.

**Phase 2. Sign-in** (decided: one private user, email and password). argon2id;
HttpOnly, Secure, SameSite cookie sessions stored in the database; login
throttling; email verification and password reset through Resend; the owner is
created from env or a CLI, with no open sign-up; CSRF protection; a
`require_user` dependency on every `/api/` route except `/healthz`. The Chrome
extension gets its own pairing token: shown once in Settings, stored hashed,
revocable, sent as a Bearer header. **Auth was rolled back in September 2026
because it locked the extension out**, so ship pairing with it and keep a
rollback switch.

**Phase 3. Home page and onboarding.** A public landing page at `/`; a signed-in
home (new roles today, highly matched, pipeline funnel, poll health, coverage
gaps); first-run onboarding (target families, locations, resume, answer bank).

**Phase 4. Resume Studio.** Versions, parse checks, an ATS score and keyword gaps
per job from stored descriptions and `matching/`, tailored versions the user
edits (never invent experience), PDF and DOCX export (`python-docx`,
`pdfplumber`, `pypdfium2` are already dependencies). Ask the user for design
preferences before building; it is a large product area.

**Phase 5. Cloud on Render** (the user said "you choose"): web, API, the
scheduler as an always-on background worker, managed Postgres with backups,
GitHub deploys. Keep it portable (containers, Postgres, S3-compatible storage).
Confirm live pricing first. The scheduler uses about 1.4 GB RAM and 20 percent
CPU, the database is about 1.8 GB. **Risk**: some boards (Cloudflare, Akamai)
block datacenter addresses that a home connection gets through; measure the
refusal rate from the cloud before cutting over.

## 10. Running and testing

On the user's machine (the only place that can deploy):

```
cd ~/Documents/ace
docker compose build            # rebuilds migrate, scheduler and web (one Dockerfile)
docker compose up -d web scheduler
curl localhost:8000/healthz
```

Tests:

```
.venv/bin/python -m pytest backend/tests -q --ignore=backend/tests/browser   # 1009, hermetic
node extension/test-rules.js                                                 # 185 cases
ACE_BROWSER_TEST_URL=http://127.0.0.1:8000 \
  .venv/bin/python -m pytest backend/tests/browser -q                        # ~4.5 min
```

Browser tests need Chrome, `websocket-client` (not in `requirements.txt`) and an
app with realistic data; they skip rather than fail when either is missing. To
try a UI change without touching the live app, run a second `uvicorn
backend.app.api.main:app --port 8001` and point `ACE_BROWSER_TEST_URL` at it.

In a cloud session: `python -m venv .venv && .venv/bin/pip install -r
backend/requirements.txt websocket-client`, the unit tests work as is, `cd web &&
npm ci`. You cannot reach the user's database, scheduler, `.env` or the
extension in their browser. Work on a branch and open a pull request; main stays
deployable, and the live app only changes when the user pulls and rebuilds.

## 11. Operational gotchas (the short list; the rest is in `docs/knowledge/08-operations-and-testing.md`)

- `docker compose build` before `up`; containers bake the source. `migrate` has
  its own image, so building only web and scheduler leaves migrations unapplied.
- Address the server as `docker exec ace-web-1`; `compose exec` can land in a
  stale one-off container.
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

1. Read this file and the index `docs/knowledge/README.md` (about 1k tokens); check `git log -5` and `git status`.
2. Do Step 0 and Step 0b, test first, on a branch.
3. Start Phase 1 with the shell (layout, tokens, theme switch, nav), then the
   queue with URL-held filters and numbered pagination, then the job page.
4. Show the user a screenshot of each page in both themes as it lands.

## 14. Keeping this current

Knowledge only compounds if it is written down and pushed. Before ending any session:

1. Update section 3 (state) of this file, and section 9 if the plan moved. Keep the file under 450 lines; move detail
   into `docs/knowledge/`.
2. Add a dated entry to the right topic file in `docs/knowledge/` for anything learned or reversed (its README says how),
   and a Status line on anything the entry supersedes.
3. Commit the docs with the code, push, and open or update the pull request. A cloud session starts from what is on
   GitHub, so ask the user to merge, or start the next session from the work branch.
4. No personal data in either place: this repo is public.
