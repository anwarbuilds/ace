# Approved Analytics implementation, validation and release

This change implements the four-tab Analytics package under the local,
Git-ignored `design/ace-analytics-pixel-lock/` directory. It is based on
`9cbafd7e06beac85bb7767de45b3232d84964ec3`, also verified as the remote branch
head during implementation. No production operation occurred during that phase.
The later owner-approved production release is recorded below.

## Production release, 2026-10-25

The owner explicitly requested deployment. The implementation was rebased onto
`4f41949` to preserve the other session's performance updates, committed and
pushed as `340b175251a8040f3eedad9553c3f6f965657698`. After integration, 112 focused
backend tests, TypeScript, ESLint, production build and dash checks passed.
Analytics code and styles are unchanged from the earlier browser-tested version.
The browser suite was not repeated because of the documented cooling issue.

At 23:41Z, public health reported that exact SHA and API status ok. Only API and
web were rebuilt and replaced, both healthy. Scheduler, PostgreSQL and Caddy
retained their existing container IDs. Schema remained at `0050`; no migration,
Gmail consent change, extension publication or destructive data operation ran.

Before activation, a fresh 437 MB private backup passed gzip integrity and
PostgreSQL archive listing. It and rollback image IDs are under
`private-backups/analytics-release-20261025T233637Z/` on the VM. Eight protected
table counts and applied-mark counts matched before/after inventories.

Read-only production checks verified 919 unique applications against existing
mark totals, four date ranges, cohort partitions, pagination deduplication and
outcome drilldowns. The in-process API returned 200 with no-store. The diagnostic
forced every database connection read-only and created no session. Public
checks verified the health SHA, all 11 cached logo hashes, private API 401s and
sign-in redirects for all four tabs. Production has zero Gmail connections and
zero petition reports. These unavailable states remain truthful. Signed-in
production browser rendering and live mailbox sync were not exercised.

## Implementation and data boundaries

`GET /api/analytics` is an authenticated, no-store, read-only projection. The
existing `/api/intelligence` mixes lifetime submissions with discovery data and
has no submission-date range, complete event undo handling, calendar-week
series, or submitted resume/channel attribution. It remains unchanged for
Career Dashboard. The new projection reuses Inbox's application identities and
existing tables. There are no new tables or migrations. The filtered Applications child view shares this same read projection. A later approved release must include matching API and web images; a website-only release would not provide the new Analytics endpoint.

- Applied marks and distinct external applications retain their established
  unique keys. Closed and currently ineligible postings remain in history.
- Date and role filters apply to submissions. Lifetime Applied remains owned by
  the existing shell. Week bars are Monday through Sunday in the display zone,
  independent of the selected historical range. Undated all-time history is
  included in totals and explicitly excluded from dated charts and cohorts.
- Outcomes are distinct application/event-type pairs. Undone events, preview
  evidence, untrusted actors, future events and pre-submission events are
  excluded. A message linked to conflicting application identities contributes
  no verified email outcome. Owner-confirmed legacy stages are identified as
  manual evidence and never receive invented response timestamps.
- Positive responses exclude automatic application receipts. Explicit
  rejections are counted separately. No reply remains pending regardless of age.
  The 30-day threshold is an observation window, never an automatic rejection.
- Cohort partitions are disjoint. An explicit rejection takes precedence over
  an earlier positive reply in that partition; the event chart retains both
  historical event types and explains the overlap.
- Response rates remain unavailable because the schema has no attestation of
  complete observation coverage. A single event, a Gmail grant or a successful
  sync cannot establish that denominator.
- The schema has no actual submitted resume version or captured application
  channel. Both display `Not recorded`. No primary-resume backfill or provider
  guess is made. Combination ranking remains unavailable without attribution,
  complete comparable evidence and at least five age-qualified applications.
- Company identities are exact strings, never fuzzy merged. Only reviewed
  reports on official allowlisted source hosts are exposed. USCIS petition
  decisions and DOL LCA evidence remain distinct. Report revisions replace
  earlier reviews for the same entity, metric and fiscal year. Missing counts
  for any included legal entity suppress the company-year aggregate. Petition
  decisions are never labeled hires or new graduate eligibility.
- Eleven authentic favicons are cached locally with source URL, verification
  date and SHA-256 provenance. Exact reviewed names select a local asset.
  Missing identities and failed images use a neutral monogram. No browsing-time
  logo request exposes application history to an external service.
- Analytics invalidates its server projection through the existing settled
  `ace-marks` broadcast and focus/visibility changes. It owns no competing
  application count or optimistic mutation state.
- Inbox review links select existing review, exact-preview or ambiguity views.
  Filtering is applied before the existing 100-message page limit, so older pending matches remain reachable. Existing conservative matching, manual confirmation, audit and undo remain.
- Pulls changes are limited to company logos and a calendar above the original
  right-side cards. Original card markup and content remain intact. Calendar
  links preserve the active filter and use existing local-date Pulls reads.

## Visual review

The running Next.js page, using the real API against a disposable fictional
SQLite database, is captured at 1672 by 941 in Day and Night. The fixture is
`python -m backend.scripts.seed_analytics_demo`; its database is confined to
`/tmp/ace-analytics-fictional.db`. All employer history, applications, emails
and petition counts in those captures are fictional test data. One explicitly
fictional Google application checks the authentic local logo and image fallback.

The reference and implementation retain the same four module compositions.
Intentional differences from the illustrative screenshots are:

- Current ACE sidebar, navigation, account chip, topbar, Answers dock, Wine and
  Rose tokens and Inter remain in place. Existing shell geometry is preserved.
- Real fixture counts and a 90-day range replace the illustrative counts. This
  includes seven recorded role families, so the role table has two more rows.
- Missing response-rate coverage, attribution and sponsorship evidence use
  explicit unavailable states, rather than the sample percentages or rankings.
- The inbox band reports the actual disconnected fixture state. It has no fake
  coverage percentage, fake completed workflow badges, or demo toggle.
- Sponsorship terminology describes verified official petitions, not total
  hiring or unsupported new graduate eligibility.
- Source captions, chart data disclosure and underlying-record links support
  accessible inspection. Phone tables become labeled stacked rows.

The local review artifacts stay Git-ignored under
`artifacts/analytics-validation/`. They are not production verification.

## Verification results

Commands executed against the local checkout:

```text
taskset -c 0 npm --prefix web run typecheck
taskset -c 0 npm --prefix web run lint
taskset -c 0 npm --prefix web run build
python3 scripts/no_user_facing_dashes.py
git diff --check
.venv/bin/python -m pytest backend/tests/test_analytics_read.py backend/tests/test_inbox_reconciliation.py backend/tests/test_inbox_persistence.py backend/tests/test_petition_reports.py backend/tests/test_job_marks.py backend/tests/test_pulls_api.py backend/tests/test_web_api.py -q
WEB_URL=http://127.0.0.1:3111 CHROMIUM_PATH=/tmp/ace-analytics-chrome npx playwright test tests/e2e/analytics-redesign.spec.ts tests/e2e/marks.spec.ts tests/e2e/combined-intelligence.spec.ts --workers=1
.venv/bin/python scripts/compare_analytics_screenshots.py
```

TypeScript, ESLint, production build, static dash scan (zero hits), and whitespace
checks passed. The final backend set passed **89 tests**. Browser results and
artifact comparisons are recorded in the completion entry below.

Generic screening state does not manufacture a separate recruiter reply when an assessment already explains that stage; the same normalized evidence feeds the charts and filtered records.

Chrome used one worker, disabled GPU, one CPU core and a duty-cycle limiter.
A host-visible temperature watcher stopped only this task's Chrome above 92 C,
below the repository's 95 C cutoff. An earlier machine restart invalidated its
partial browser run; no result from that interrupted run is counted. FastAPI
TestClient needed socket access outside the restricted sandbox; all its data
remained isolated in memory. No production database was used.

The tests reproduce and protect two browser races found during this task:
SVG tooltip titles must be one complete string for production hydration, and
an image that fails before hydration must still render its monogram fallback.
The calendar also resets its displayed month after selecting Today. Inbox review
filters are tested beyond the most recent 100 unfiltered messages.

## Acceptance checklist comparison

PASS below means locally verified with fictional records. It does not mean
production verification or a claim of identical illustrative data.

| Approved checklist area | Result and evidence |
| --- | --- |
| Four distinct approved layouts | PASS for module composition, type, borders, tabs and chart treatments; see all four native captures and side-by-side comparisons. Existing shell and actual-data differences are disclosed above. |
| Overview application timeline, current week, latest statuses, outcome evidence | PASS. Dates come from submission records; current status and historical event types are separate. |
| Outcomes plain-English 30-day eligibility, timing and confirmed/pending/unknown states | PASS. No response is never rejected; counts partition eligible applications without double counting. Missing observation coverage is explicit. |
| Four Role and resume modules | PASS. Actual role taxonomy is shown; missing submitted resume and channel attribution remain `Not recorded`; comparisons are not ranked without adequate evidence. |
| Rich Companies layout | PASS for two top tables, petition bar/line chart, outcome history, year cards and sourced evidence timeline, with useful unavailable states. |
| Preserved Wine and Rose, Inter and navigation | PASS. Existing palette, fonts, sidebar, navigation and theme provider are reused. |
| No generic replacement panels or extra Analytics tabs | PASS. Only Overview, Outcomes, Role and resume, Companies. |
| Exact chart drilldowns | PASS. Selected dates, status, role, company, outcome evidence, response timing and 30-day cohorts open the corresponding filtered Applications records, with existing controls reachable from each stored job. |
| Unique application totals and external history | PASS. API totals agree with existing marks; closed and now-ineligible marked jobs remain included. |
| Date/role filters, calendar week and unknown dates | PASS. Backend boundaries, local midnight and exact 30-day threshold are tested; filters are bookmarkable. |
| Receipt exclusion, event deduplication, correction/undo, manual stages | PASS. Distinct application/event-type evidence, single identity per message, undo removal and reliable timing only. Existing audit and review mutations are unchanged. |
| Response rates and historical growth | PASS. No missing coverage is turned into a rate, zero or growth arrow. |
| Gmail disconnected state, review links and read-only consent | PASS locally. Real connection state is read; review, exact-preview and ambiguity links filter the existing Inbox. No consent or sync operation runs while reading Analytics. |
| Live Gmail grant, mailbox sync and complete response coverage | NOT VERIFIED in production. These require the owner's real opt-in/configuration and evidence. No success claim is made. |
| Logos and graceful fallback | PASS. Eleven reviewed official assets, exact names, local requests, source hashes and image-error fallback; no arbitrary URL or third-party guessing. |
| USCIS/DOL semantics and employer identity | PASS with fictional source-shaped records and official-host validation. Incomplete entity-year counts suppress annual rates; no new-grad or total-hire claims. |
| Actual production petition imports and new-grad eligibility | NOT VERIFIED. No production data import occurred. Empty real tables remain unavailable. |
| Pulls company-first behavior and original right-side cards | PASS. Only the avatar replacement and calendar insertion affect Pulls. Both original cards retain their existing markup/content/order. Date selection also restores the correct displayed calendar month. |
| Career Dashboard and extension preserved | PASS. No changes in those routes/components, their existing read model, or extension files. |
| Application persistence, cross-tab totals, duplicate saves, failure rollback | Covered by the existing marks suite and the new cross-tab Analytics refresh test; see final browser result below. |
| Responsive widths, themes and accessible controls | Covered at 1672, 1600, 1440, 1280, 1024, 390 and the 836 CSS-pixel reflow equivalent of a 1672-pixel viewport at 200% browser zoom. Charts have accessible descriptions/data, controls and links support keyboard navigation, and theme switching supports Space. |
| Read purity, privacy and operation boundaries | PASS. No chart-side writes, migrations, discovery changes, scheduler operation, production tests, owner-data captures or deployment. |
| Final owner visual acceptance | NOT VERIFIED. Native captures, differences and comparisons are supplied for review; local automated checks do not substitute for the owner's judgment. |

## Data still unavailable

Production Gmail authorization/sync and actual official petition imports were
not accessed or activated. Submitted resume attribution, actual application
channel and complete observation coverage are absent from the current schema.
Analytics exposes each gap. It never substitutes the active resume, sender,
posting provider, mailbox silence, LCA count, or historical petition total for
those facts. This is the intentional accuracy boundary of the delivered UI.

## Exact filtered application drilldowns

Chart, metric, role and company links open `/app/applications/analytics`, a
read-only Applications view backed by the same `/api/analytics` projection with
`records=1`. It supports selected submission dates, current status, company,
role, verified outcome type, the 30-day eligible cohort and reliable response
timing. Every identity appears once; pagination is bounded to 50 rows by default.
The current-week link uses its own exact local Monday-through-today bounds.

Records link to existing stored-job details and their existing application
controls. External applications remain read-only history, as in the original
workflow. Lifetime Applied, the original Applications page, its mutations and
its full-history CSV export remain intact. No original Applications query
semantics or database records were changed. The drilldown timezone is retained
in its URL so that it reproduces the chart selection exactly.

## Review artifacts

- `artifacts/analytics-validation/light-{overview,outcomes,role-resume,companies}.png`
- `artifacts/analytics-validation/dark-{overview,outcomes,role-resume,companies}.png`
- Full-page versions of each capture, plus four 390-pixel Night captures.
- `comparison-contact-sheet.png`, four `comparison-*.png` pairs, four
  `difference-*.png` diagnostics and `comparison-metrics.json`.
- `playwright-final.log` and `changed-files.txt`.

Raw pixel error includes changed counts, truthful wording, stale/live state and
the preserved existing shell. It is not a pass percentage. Visual refinement
improved the Overview, Outcomes and Companies pixel diagnostics versus the
initial implementation. The role table keeps seven real fixture groups instead
of five illustrative groups, so it is taller despite the matching row treatment.



## Completion results

- **PASS:** 89 focused backend tests.
- **PASS:** 45 Playwright tests, 6.7 minutes, one worker. This includes all 18
  new Analytics checks, 20 existing combined-intelligence checks, and 7 existing
  marks checks. Day and Night captures have no console or page errors.
- **PASS:** TypeScript, ESLint, Next.js production build, forbidden-dash scan
  with zero hits, and `git diff --check`.
- **PASS:** No changes to the Chrome extension, Career Dashboard route or
  components, existing intelligence read model, auth, migrations or scheduler.
- **PRODUCTION:** Released and checked as recorded above. Gmail consent/sync,
  actual petition evidence and final owner visual acceptance remain unavailable
  or unverified. Production has no Gmail connection or petition reports.

The 45-test run is recorded in
`artifacts/analytics-validation/playwright-final.log`. The final 390-pixel mobile recheck also passed after the typography-token adjustment. The final focused drilldown recheck passed after event-type normalization, including its 390-pixel layout and zero browser errors. Temporary API, web and watchdog processes were stopped after verification.

## Exact changed files

- `ACE_NEXT_KNOWLEDGE.md`
- `backend/app/api/main.py`
- `backend/app/api/routers/analytics.py`
- `backend/app/api/routers/inbox.py`
- `backend/scripts/seed_analytics_demo.py`
- `backend/tests/test_analytics_read.py`
- `docs/architecture/2026-10-25-analytics-redesign.md`
- `docs/knowledge/05-web-ui.md`
- `scripts/compare_analytics_screenshots.py`
- `web/public/company-logos/README.md`
- `web/public/company-logos/adobe.ico`
- `web/public/company-logos/amazon.ico`
- `web/public/company-logos/apple.ico`
- `web/public/company-logos/google.ico`
- `web/public/company-logos/ibm.ico`
- `web/public/company-logos/meta.ico`
- `web/public/company-logos/microsoft.ico`
- `web/public/company-logos/nvidia.ico`
- `web/public/company-logos/provenance.json`
- `web/public/company-logos/salesforce.ico`
- `web/public/company-logos/servicenow.ico`
- `web/public/company-logos/stripe.ico`
- `web/src/app/app/analytics/analytics.css`
- `web/src/app/app/analytics/page.tsx`
- `web/src/app/app/applications/analytics/loading.tsx`
- `web/src/app/app/applications/analytics/page.tsx`
- `web/src/app/app/pulls/page.tsx`
- `web/src/app/globals.css`
- `web/src/components/CompanyLogo.tsx`
- `web/src/components/analytics/AnalyticsCharts.tsx`
- `web/src/components/analytics/AnalyticsFilters.tsx`
- `web/src/components/analytics/AnalyticsRefresh.tsx`
- `web/src/components/analytics/AnalyticsView.tsx`
- `web/src/components/inbox/InboxIntelligence.tsx`
- `web/src/components/pulls/PullsCalendar.tsx`
- `web/src/components/pulls/PullsTimeline.tsx`
- `web/src/lib/analytics.ts`
- `web/tests/e2e/analytics-redesign.spec.ts`
- `web/tests/e2e/marks.spec.ts`
