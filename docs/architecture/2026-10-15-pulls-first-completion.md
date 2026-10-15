# Pulls-first completion

Status: implemented on `next-app` and verified against an isolated fictional SQLite database. Live Postgres,
scheduler behavior after restart, extension installation in the owner's browser, and deployment are not verified in
this environment.

| Area | Verified result | Evidence | Remaining operational risk |
| --- | --- | --- | --- |
| Routes and shell | `/` and `/app` lead to `/app/pulls`; the sidebar follows the approved order, collapses on desktop and becomes a phone bar | `web/src/components/shell/`, Playwright navigation tests | Existing external bookmarks to removed Browse and Companies pages redirect to Opportunities |
| Authentication | Owner-only Argon2 sessions, CSRF, throttling, reset, intended-page return and extension tokens remain enforced | `backend/app/auth/`, `backend/tests/test_auth.py`, Playwright auth tests | Production proxy must preserve HTTPS and forwarded host correctly |
| Pull telemetry | 15 minute windows distinguish attempts, checked, answered, failed, observations, new postings and qualifying arrivals; older unavailable attempt data stays nullable | migration 0040, `routers/pulls.py`, `test_pulls_api.py` | Verify the first post-restart windows against live scheduler data |
| Opportunity workflow | Search, ordered sorts, filters, paging, marks, detail routes and official links remain | `JobListPage`, `JobDetail`, Playwright list and marks tests | None found on demo data |
| Applications and analytics | Existing applications, unmatched history and CSV remain; analytics adds URL-backed trend and discovery-family filters | `dashboard.py`, analytics page, studio API tests | Status history is not stored, so conversion uses current status only |
| Resume and extension | Resume Studio foundation, answer bank, extension pairing and revocation remain | studio API and browser auth tests; 185 extension matcher cases | Tailoring and document export remain later scope |
| Legacy retirement | FastAPI `/` redirects to the Next app; old HTML, Browse and Companies UI code are removed without deleting data | redirect tests, Next redirects, clean route build | Rollback is `git revert` of the completion commit |
| Runtime | Compose runs Python `api` and Node `web` separately with health checks; builds use local Geist files | `compose.yaml`, `web/Dockerfile`, production build | Rebuilding the live stack requires owner approval and a database backup |

The metric identity for `sources_checked` is a distinct configured source identity in a window. Poll attempts can be
higher because the same source may run more than once. A source that fails and later answers can count in both source
outcomes. `postings_observed` is the number returned by successful reads, including previously seen postings;
`new_postings` is first observation in the exact window. Pre-migration attempt and failure values are reported as not
recorded rather than inferred.

The production route map is `/app/pulls`, `/app/opportunities`, `/app/jobs/[id]`, `/app/applications`,
`/app/analytics`, `/app/resume-studio` and its nested tools, `/app/extension`, `/app/archive`, `/app/saved`,
`/app/coverage`, `/app/settings`, `/app/answers`, `/app/insights/skills`, and `/app/more` on phones.
