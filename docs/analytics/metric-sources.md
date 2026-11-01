# Analytics metric and source audit

## Chart/interaction release LIVE, 2026-11-01

Exact tested web `3d578e5058fa0efd79e16741d0eda9760e1ac2ca`, merged PR #24,
activated web only at 21:37:36Z–21:37:43Z (13:37 PST). See the current handoff
for release preservation/rollback and private proof. The 57 dedicated browser,
132 unique DOM/calculation and 2,499 backend/PostgreSQL checks pass, plus types,
lint and build. Native Day/Night and wider responsive captures use fictional
test data; fresh actual read-only reconciliation separately covers 44 scopes,
132 weeks, 924 buckets and all cached daily aggregates. No production fixture,
mailbox completeness or signed-in production browser claim.

The reconciled server supplement now returns a Pacific date/count map containing
aggregates only. Client week arrows read this verified map with no report fetch;
identities stay server-side. Week headings, seven bars, role filter, independent
reporting period, native history/back/forward, current bound/reset and exact
record links retain their contracts. The footer compares real counts: equal
elapsed local weekday/time for current, complete weeks for historical, no
percentage with zero prior activity, and the genuine peak day when unique.

The full-width timeline preserves line, markers, fill, axes and unscaled Inter
text while measuring its actual card width. Its exact data/drilldowns are in an
accessible dialog; opening it does not change the four-card geometry. The prior
full-workspace layout and removal of Overview lower sections remain.

Sync requires a ready connected account and real sync timestamp. Match and
Identity use `classified_email_evidence.linked_messages`, excluding company-only
and unlinked correspondence. Verify requires recorded manual/automatic confirmed
evidence, rather than claiming all messages verified. Green describes supported
evidence, not completeness. Coverage uses only existing complete, consistent
`job_mail` Gmail check metadata, with its actual window/check timestamp and
email numerator/denominator. It is separate from application filters and employer
response coverage; an absent/invalid check is Not verified with Check in Inbox.
No Gmail verification or backend change ran. Response-effectiveness rates remain
unavailable without their separate observation contract.

Visible-page timer/focus checks quietly GET the same authenticated no-store
projection and hash every returned field except read timestamps. Unchanged data
never replaces the page or interrupts scroll/dialog/week state. Changed data,
evidence notifications, return, retry and recovery still read a fresh server
projection. Failure retains only this mounted selection's verified output;
older/failed responses cannot replace its snapshot or fingerprint.

## Previous Overview workspace release, 2026-11-01

> The chart/interaction release above supersedes its web image and refresh/coverage presentation. The layout/removal and underlying metric contracts remain current.


The owner removed Recognized hiring progress, About these metrics and evidence,
and footer/export links from Overview. It now ends after the four chart cards,
which expand through desktop workspace width and remaining height. Other tabs,
CSV APIs, all metric/date definitions and weekly behavior remain unchanged.
Exact tested web `5c36ea98b967e3d8c851a73509d113975f4e5a78` activated at
2026-11-01T20:35:28Z–2026-11-01T20:35:34Z; [PR #23](https://github.com/anwarbuilds/ace/pull/23).
The same strict height assertion passes after fixing equal-row overflow with
longer status lists. Day/Night and 1920/2560 layout captures use fictional hosted
records; current actual production data is separately verified read-only across
44 role/period scopes and 132 weeks / 924 daily buckets. No backend change,
production fixture, migration, private hosted export or production browser test.

## Overview weekly navigation LIVE, 2026-10-31

The weekly card selects one Monday-to-Sunday calendar week in
America/Los_Angeles. Current week is titled “This week” with its date range;
historical headings show the selected range, including both years when needed.
Arrows move seven calendar dates, forward stops at the current week, and the
small reset returns there. Only the page-level Choose dates retains a calendar
icon and date inputs. Period, role and chart-interval selections are preserved.

The existing server-only supplemental reader uses unique application identities
and their submission timestamps, never email receipt dates. It reconciles the
current week's total and daily buckets against the existing Analytics projection
before returning aggregate chart points. If the report uses another timezone,
one existing read-only Analytics request supplies the Pacific week projection.
Role-filtered identities still come from exact paginated Analytics records.
Historical daily links use their own dates rather than the reporting-period
bounds. Missing historical data shows Unavailable; it never substitutes current
bars. Future current-week days have no completed-zero label or records link.

The five KPI definitions and receipt-date invitation binding remain intact.
Coverage stays Unavailable because no existing field certifies complete
comparable observation for the selected period. No backend, migration, Gmail,
application-state or scheduler change is part of this frontend release.

The previous weekly-navigation release, exact tested `d26bfac1c64eaa5a8a479c89d5099b6474f67a4e`,
activated web only at 2026-10-31T16:12:34Z–16:12:41Z. Exact-source hosted checks
pass 2,499 backend/PostgreSQL, 54 Inbox/Analytics browser and 127 unique DOM/
calculation cases, TypeScript, lint and build. A fresh post-release read-only
snapshot reconciles 132 weeks / 924 buckets across 44 role/period scopes against
independent Python Pacific-calendar expectations. Actual Day/Night snapshot
renders and comparisons stay private; existing shell dimensions, data-dependent
notices and truthful evidence states differ from sample images. This is not a
pixel-perfect or signed-in production-browser claim. No mock production response
or screenshot count was used.

## Inbox synchronization integration, 2026-10-30

The [integration review](inbox-sync-review.md) documents the current candidate
and deployment state. Analytics uses the shared effective Inbox classifications,
including owner receipt overrides and compatibility markers. Its API reads one
PostgreSQL READ ONLY, REPEATABLE READ snapshot, with no cached counters.

`classified_email_evidence` counts distinct effective messages by receipt date,
independently of the application submission cohort. It includes acknowledgements,
assessment/interview invitations, offers, recruiter replies, action requests and
rejections; completion, cancellation and routine progress remain separate
categories. Acknowledgements never enter meaningful replies. Its linked/company/
unlinked partition describes supported identity, not authorization to promote a
stage. A retained receipt target alone is not verified identity.

The email floor is July 1, 2026 midnight America/Los_Angeles
(`2026-07-01T07:00:00Z`), with older evidence preserved. Finite/custom selections
use local receipt dates; All time includes in-scope email even before the first
recorded application. Application `applied_at`, event dates and official-source
reporting dates remain separate clocks.

Every recognized-email category opens exact paginated records from
`GET /api/analytics?emails=1&email_kind=...`. Optional
`email_scope=linked|company|unlinked`, company and family filters require supported
identity. These links preserve the original reporting selection when returning
to application Analytics. The Companies email link uses company-only rejection
scope and never includes its messages in application-specific rejection totals.

Current effective meaning/target/decision, active event/Undo, actor and chronology
control confirmed application evidence. Explicit active owner manual stage
corrections retain the existing optional-kind contract. Invalidated email stages
cannot be resurrected through current-status fallback or cohort polarity.
Historical assessments/interviews and later rejections remain distinct valid
events, deduplicated by application and kind.

Open Analytics and records pages revalidate on evidence notifications, return,
retry and online recovery. Two-minute visible-page and focus/visibility checks
compare the authoritative projection quietly; unchanged data does not replace
the page, and changed data requests a fresh server projection. Query
filters remain unchanged. Failed refreshes retain only the mounted selection's
last verified rendered report with a freshness/error indication; no counts are
invented and older responses cannot replace newer results.

The remaining source table below still defines submission and official metrics;
its original narrower email-history implementation is superseded above.

The screenshots specify layout only. The production UI reads authenticated,
no-store ACE APIs. No image numbers, fictional employers, random series or
browser-local analytics database enter the dashboard.

## Source contract

`GET /api/analytics` remains the authority for the selected submission cohort,
latest stages, verified outcome evidence, role families and official reports.
`GET /api/inbox/applications` supplies compact application identities and genuine
submission timestamps for calendar grouping and submission comparisons. With a
role filter, the existing paginated Analytics records endpoint supplies the exact
family keys. Those records stay on the Next.js server; only aggregates reach the
browser. Incomplete, duplicate or inconsistent reads disable supplemental metrics.

The submission cohort includes applied `job_marks` and `external_applications`,
including closed/archived postings. Separate requisitions retain separate keys.
Potential job/external duplicates are not silently merged. The date is applied_at,
never discovery date, email receipt date or current-status date.

| Visible measure | Definition and API fields | Denominator / comparison | Drilldown and missing state |
| --- | --- | --- | --- |
| Applications sent | Unique identities in local submission dates; `submitted` | Prior equal local calendar interval through the same final-day clock time. All time has no prior interval | Exact selected application records. A missing supplemental ledger removes the trend only |
| This week KPI | Reconciled Pacific `week_total`, current America/Los_Angeles Monday through report time, with role selection | Same elapsed weekday/time in prior week, rather than the entire prior week | Current Monday through today; independent of historical chart week |
| Meaningful replies | `positive`: distinct selected applications with a positive recorded employer outcome or supported recorded stage; no receipts | No effectiveness trend without comparable observation coverage | `evidence=positive`. No evidence is unavailable, recorded zero remains zero |
| Online assessments | `assessments`: distinct applications with recorded assessment evidence | No inferred prior evidence percentage | `evidence=online_assessment` |
| Interview invitations | `classified_email_evidence.categories.interview`: distinct effective invitation emails, including unlinked evidence; receipt dates and July Pacific floor | No inferred prior observation percentage. Email counts do not assign an application stage | Exact `emails=1&email_kind=interview` records. Missing projection is unavailable; recognized zero stays zero |
| Verified interview stages | `interviews`: distinct applications with valid recorded interview history in the submission cohort | Historical stages survive later rejection; no identity inference from an unlinked invitation | `evidence=interview`, also linked from the metric explanation |
| Submission timeline | Genuine identity submission timestamps grouped in display timezone | Daily, calendar Monday weeks, calendar months. Edge buckets clip to selected dates | Every point/data-table row opens exactly its date interval. Missing detail uses the API's existing series |
| Week bars | Same timestamps, selected Monday through Sunday | Historical navigation changes only the chart; future days are labeled as future | Each completed day opens its exact submissions |
| Current statuses | `statuses`: one latest stage per selected identity | Percentage of `submitted`; sums to cohort total | `status` selection. Silence is never rejection |
| Outcome evidence | `evidence.positive` and `evidence.rejected` | Application/outcome-type pairs; one application can appear in both categories. Donut center explicitly says outcome pairs | Separate positive/rejection evidence links; no claim of disjoint applications |
| Age-qualified applications | `cohort.eligible`, submission at least 30 elapsed days before `as_of` | This is an observation threshold, not a rejection rule | `eligible=1`; undated records excluded |
| Confirmed responses | `cohort.positive + cohort.rejected` | Disjoint latest cohort polarity from existing API | Eligible evidence records; no invented response date |
| Confirmed/pending/unknown partition | `cohort.positive/rejected/pending/unknown` | Denominator `cohort.eligible`; legend percentages use that denominator | Underlying eligible applications. Unknown/withdrawn remain distinct from pending |
| Employer response rate | `cohort.rate` / per-group `rate` | Coverage attestation missing | Unavailable with explanation; connected Gmail does not unlock a rate |
| Response timing | `timing`, `timing_sample`, `median_days` from first reliable dated outcome after submission | Bucket shares divide by timing sample, not submissions | Dated evidence records; missing timestamps excluded, no-sample state distinct from zero |
| Inbox review | `review.needs_review/exact_preview/ambiguous` | Message counts, not application counts. Ambiguity overlaps review | Existing Inbox decision filters; no matching/triage changes |
| Role table | `roles[].family/submitted/eligible/responses` | Exact recorded evaluation family; five-row summary and expandable full list, with no title-based family inference | Family-filtered records; Unknown retained |
| Sources/channels | `attribution.channel`; no application-time source field exists | No provider/sender inference | Not recorded row; all selected records remain inspectable |
| Submitted resume versions | `attribution.resume`; no application-to-submitted-file relationship exists | Current primary resume is not historical attribution | Not recorded row; Resume Studio versions alone do not prove submission |
| Best combinations | `attribution.combinations` | Requires actual role/resume/channel, at least five age-qualified applications and comparable observation | Not enough comparable applications. No winner or causal claim |
| Top companies | `companies[].submitted/latest/latest_at/responses` | Same selected identities, exact company strings, sorted application counts | Exact company-filtered records and shared authentic logo component |
| Employer history | `companies[].submitted/assessments/interviews/responses` | Each bar counts distinct applications per type; types can overlap | Exact company records; bars are not a stacked application partition |
| Verified sponsorship companies | `verified_companies[].reports` | Reviewed official reports with exact legal-entity mapping | Existing company evidence. No new-grad eligibility/strength ranking inferred |
| H-1B history | `annual[].approvals/denials/period/rate` | USCIS approvals / (approvals + denials), both counts verified; zero denominator has no rate | Source-linked evidence; missing entity-year data stays unavailable |
| Historical petition activity | Same verified fiscal-year series for selected employer | Approval + denial decisions; never total hires | Explicitly labeled petition decisions; missing data is unavailable |
| Sponsorship timeline | `reports[].entity/period/source/url/metric/version/checked_at` | Reporting year is separate from verification date. DOL LCA and USCIS petition measures remain distinct | Direct official source links. Historical activity never proves current job sponsorship |
| Rejected companies | `rejected_companies` | Existing newest 15 card grid retained after the six reference modules | Search/pagination stay in the existing rejection records route |

## Reporting and evidence limits

Reporting-period arithmetic uses the projection's IANA zone. Weekly chart/KPI
arithmetic always uses America/Los_Angeles, including when the reporting
projection uses a different zone. Original Inter, Wine and Rose themes,
shell dimensions and global type tokens are retained. Sidebar lifetime Applied
continues to use the existing shell ledger, independent of the chosen date range.

Outcome counts describe confirmed evidence for the submission cohort, not the
number of emails received in the selected dates. The existing backend retains
its actor, identity, undo and timestamp guards. Legacy stage evidence can be
undated. An individual email does not certify complete observation. A successful
sum is not proof of perfect mailbox recall or distinct real-world submissions.

## Private verification artifacts

The requested engineering audit is generated by
`scripts/audit_analytics_dashboard.py` in an enforced repeatable read-only
PostgreSQL transaction. The independent existing Inbox/Analytics audit is also
included when available. A separate frontend calculation audit reconciles daily,
weekly and monthly aggregates against that private snapshot.

Actual measurements, complete numerical series, anonymous timestamp input and
comparison results stay in ignored `artifacts/analytics-review/production-audit.json`
and `frontend-production-audit.json`. They are owner review artifacts and must
never be staged or pushed to this public repository. The new script makes no
Gmail calls, reads no bodies and creates no authentication session. It prints no
real application key, company list, job title, resume, answer or credential.

Following owner-approved web deployment of `70d95a9`, a fresh post-release primary
and independent audit plus all 12 frontend calendar reconciliations also pass.
Actual results are private in the owner package's `release/post-audit.json` and
`release/frontend-production-audit.json`, with the authoritative VM copy under
`/opt/ace/private-backups/analytics-dashboard-20261028T0153Z/`. Source/runtime,
preservation and HTTP verification are recorded in the first root knowledge
section; no production browser or mailbox-completeness claim is implied.

## Separate backend dependencies, not implemented

Future application-time submitted-resume and source capture would need nullable,
backward-compatible attribution fields or an append-only submission record plus
an explicit owner capture action. Historical values must remain unknown. A
response-effectiveness rate additionally needs a justified observation-coverage
contract. Official sponsorship charts require reviewed official employer/year
records through the existing dry-run-first importer. These dependencies require
separate approval; no storage, ingestion, OAuth or backend operation was added.
