# Analytics implementation review, 2026-10-27

Status: ready for owner review in [draft PR #10](https://github.com/anwarbuilds/ace/pull/10).
Tested runtime source: `1376b68333311df006adacccc999c5d68850ed0d`.
No deployment or production data change was performed.

## Result

The four screenshot compositions now use the existing authenticated ACE APIs.
The frontend keeps Inter, Wine and Rose Day/Night tokens, the current shared
shell, authentic company identity components and the persistent refresh fix.
Five desktop KPI cards align in one row. The four Role modules and six Companies
modules retain their reference order. Recorded submission timestamps drive
calendar grouping, fair submission trends, historical weeks and exact date
drilldowns. Outcome rates and attribution stay unavailable when their supporting
records are absent.

The owner requested a fresh implementation after reverting the previous design.
The UI was rebuilt from the restored checkout in an isolated worktree. The final
review branch includes the current canonical source so that reviewing this patch
does not roll back protected backend or Inbox changes. Neither the owner's root
checkout nor the concurrent `ace-inbox` worktree was changed. The canonical base
for the final comparison is `34f4663ff4c295d192b071247c28c5b8a5ffb379`.

## Screenshots and comparison

The [passing hosted review run](https://github.com/anwarbuilds/ace/actions/runs/40615555332)
retains the `analytics-review` artifact. Captures use isolated fictional fixtures,
never copied reference values or owner application details. All eight final
desktop images are 1672 x 941. Day captures were compared with the four attached
references; all four final Night captures and mobile reflow were also inspected.

| Tab | Day | Night | Reference comparison |
| --- | --- | --- | --- |
| Overview | `light-overview.png` | `dark-overview.png` | `comparison-overview.png` |
| Outcomes | `light-outcomes.png` | `dark-outcomes.png` | `comparison-outcomes.png` |
| Role and resume | `light-role-resume.png` | `dark-role-resume.png` | `comparison-role-resume.png` |
| Companies | `light-companies.png` | `dark-companies.png` | `comparison-companies.png` |

The owner-local package is
`/home/ubuntu/Documents/ace-next/artifacts/analytics-production-review-20261027/`.
Its `REVIEW.md` links every image, full-page capture, comparison contact sheet and
the private metric audit. The comparison files were generated locally from the
hosted captures and the exact approved reference PNGs. They are not added to Git.

Intentional differences from the references: existing shell dimensions remain
unchanged; counts, labels and graph shapes follow recorded data; unavailable
attribution/coverage/official evidence replaces fictional chart content; every
role remains accessible through the full-list disclosure; the existing Rejected
companies grid follows the six reference modules. Some panel heights differ to
accommodate honest explanations and existing controls. This is a reviewed visual
match, not a claim of pixel-perfect identity or a production browser test.

## Data verification and limits

[Metric sources and calculations](metric-sources.md) defines every displayed
measure, reporting date, denominator, comparison, drilldown and missing state.
The read-only production audit checks all four reporting ranges against existing
application identities, latest statuses, cohorts, role/company totals, outcome
evidence and timing. The existing independent audit and separate frontend daily,
calendar-week and calendar-month reconciliation checks pass. Actual results and
complete numerical series are in the private package's
`private-audit/production-metrics.md`, `production-audit.json` and
`frontend-production-audit.json`. Fresh production measurements are not published
in this public repository. Arithmetic reconciliation does not certify complete
mailbox recall or rule out every potential cross-history identity duplicate.

Supported: unique recorded submissions, latest stages, positive/assessment/
interview/rejection evidence, age-qualified cohort partitions, first reliable
response timing, Inbox review counts, role/company breakdowns, calendar charts,
historical weeks, valid submission comparisons and source-linked official reports
when available. Outcome counts are application counts per evidence type; their
overlap is explicit. No response remains pending rather than becoming rejected.

Unavailable where source information is absent: historical submitted resume
version, application source/channel, comparable role/resume/source combinations,
complete-observation response-effectiveness rates and official employer/year
sponsorship charts or new-graduate rankings. Existing resume versions do not
establish historical submission attribution. Petition decisions and LCA records
are labeled separately and never described as employee hires.

The smallest separate dependencies are optional future submission-time resume/
source capture, a justified observation-coverage contract and reviewed official
employer/year records through the existing dry-run-first importer. None was
implemented. Each requires separate owner approval before backend changes or
ingestion.

## Validation

| Check | Result at tested runtime |
| --- | --- |
| Analytics calculation and rendered component tests | 22 passed |
| Inbox/Analytics DOM contracts | 53 passed |
| Focused backend regressions | 237 passed |
| TypeScript, full ESLint, production web build | Passed |
| Analytics hosted browser suite | 23 passed |
| Full backend unit suite | 1,586 passed |
| Existing extension matcher / hosted extension browser | 258 / 47 passed |
| Combined Inbox/Analytics hosted browser suite | 34 passed |
| Remaining app browser suite | 165 passed, 21 failed; overall CI is not green |
| Read-only primary, independent and frontend metric audits | Passed; private results retained |

The Analytics browser suite covers all four tabs in both themes, 1600/1440/1280/
1024/390 widths, 836px keyboard reflow, all date filters, role filters, daily/
weekly/monthly aggregation, historical-week scope, exact date/status/evidence
drilldowns, logo failure fallback, cross-tab count updates, desktop alignment,
axis-label spacing and bounded refreshes on both Analytics routes. Browser tests
ran on GitHub-hosted infrastructure to honor local cooling restrictions.

The dedicated review run is green. The wider CI run is
[40615561429](https://github.com/anwarbuilds/ace/actions/runs/40615561429).
Its 21 broad-suite failure titles include all 20 from prior canonical review run
`40577319214`, plus `browse.spec.ts:78`, the opened-Pull navigation case. The
additional case times out clicking a company after scrolling; its failure
snapshot shows the selected window collapsed after an earlier expanded assertion.
Pulls implementation, global styles and that test are unchanged from the base.
The cause is unproven and this remains an unresolved validation limitation; it
is not described as a proven pre-existing failure. No unrelated assertion was
removed, skipped or quarantined. The owner-local package retains the exact
failure-title comparison in `ci-failure-comparison.txt`.

No signed-in production browser validation, deployment, migration, Gmail history
recheck, scheduler change or extension publication ran. Early local backend
attempts were interrupted by environment/workspace problems; hosted regression
results above supply the completed verification.

## Changed files

Relative to the canonical base, the implementation and verification files are:

- `web/src/app/app/analytics/analytics.css`
- `web/src/app/app/analytics/page.tsx`
- `web/src/components/analytics/AnalyticsCharts.tsx`
- `web/src/components/analytics/AnalyticsFilters.tsx`
- `web/src/components/analytics/AnalyticsSummary.tsx`
- `web/src/components/analytics/AnalyticsView.tsx`
- `web/src/lib/analyticsCalculations.ts`
- `web/src/lib/analyticsRead.ts`
- `web/tests/analytics-calculations.test.mjs`
- `web/tests/analytics-rejections-render.test.mjs`
- `web/tests/e2e/analytics-redesign.spec.ts`
- `web/tests/inbox-reliability-dom.test.mjs`
- `scripts/audit_analytics_dashboard.py`
- `.github/workflows/analytics-review.yml`
- `docs/analytics/metric-sources.md`

Review and continuity documentation adds this file plus updates to
`ACE_NEXT_KNOWLEDGE.md`, `docs/HANDOFF.md` and `docs/knowledge/05-web-ui.md`.

## Preserved behavior

The final diff leaves `backend/`, `extension/`, `deploy/`, Inbox components,
the shared app layout and persistent `AnalyticsRefresh` byte-for-byte unchanged
from the canonical base. Authentication, OAuth, reconciliation, owner decisions/
Undo, application identity/status rules, discovery, Pulls, Resume Studio, Answer
Memory, company-logo security and scheduler behavior therefore retain their
existing implementation. Focused regression suites pass as reported above;
the broad-suite failures and additional Pulls timeout remain reported separately.
ACE still never submits employer applications or marks them Applied after fill.
