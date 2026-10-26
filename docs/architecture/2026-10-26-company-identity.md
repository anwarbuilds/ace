# Shared company identity, 2026-10-26

Status: implemented and tested locally on `company-logo-consistency-20261026`,
based on `wine-rose-platform` at `cdefb3f`. Not deployed.

The owner requested actual marks for missing employers such as FedEx Freight
and General Motors, plus the same logo after opening an Apple opportunity.
Pulls/Analytics previously knew 11 exact names, while job tables and job detail
heroes always used monograms. A shared resolver and image component now serve
59 reviewed employer icons and 71 explicit aliases across the main employer
views. The approved Wine and Rose layout, typography and company-first rows
are preserved.

## Result and boundaries

- FedEx, FedEx Freight, General Motors and Southern Company have separate
  reviewed assets from their official sites. The Freight icon is declared by
  its own official careers page. All 48 new files preserve downloaded bytes.
- Canonical names and individually listed aliases share one manifest. Matching
  normalizes Unicode/case/whitespace/periods/commas only. Partial-name matches,
  inferred domains and automatic parent/subsidiary substitutions are excluded.
- Pulls rows and its company dialog, job table cells, job detail heroes,
  company evidence headers, stored and external applications, Analytics company
  history, Inbox application records, Coverage, Resume Studio and check history
  use the shared components. Native selects retain text options.
- Company routes decode escaped names once before both evidence queries and
  logo lookup. This fixes multiword identities and keeps malformed bookmarks
  usable. Other page headers retain their existing markup unless given a logo.
- Unknown, empty or failed images have visible accessible initials. Image error
  state is scoped to the current identity, including cached failed images.
  All browser image sources remain local. No extra backend calls or scheduler
  operations are introduced for logos. Table/hero sizes retain 36/64 px and
  26/48 px at the existing 720 px mobile breakpoint.
- Career Dashboard, extension, backend, business rules, application identities,
  authentication, Gmail permissions, production data and scheduler are unchanged.

The official-site review could not retrieve Oracle, Intel, Cisco, Dell, Tesla,
Mastercard, Ford, DoorDash, Akamai or Uber icons because access was refused.
HPE timed out and Walmart supplied no usable raster icon. These and unreviewed
employers retain the visible fallback. A genuine mark for every employer in the
dynamic catalog is not claimed. Additional coverage requires another reviewed
source record, rather than a guessed domain or fabricated mark.

## Validation

| Check | Result |
| --- | --- |
| TypeScript | Passed, `npm run typecheck` |
| ESLint | Passed, `npm run lint`, no warnings |
| Production webpack build | Passed, `npm run build`, one CPU core |
| Company component/DOM contracts | 7 passed: reviewed aliases, false-match protection, manifest integrity, shared list/detail avatars, empty/unknown fallback, encoded routes and evidence queries, failed-image recovery |
| Existing Inbox review rendering | 8 passed |
| Assets | All 59 decode as images, minimum 16 px; every file matches its recorded SHA-256 |
| Built local website | Authenticated HTTP checks on 17 pages against a disposable fictional SQLite database; all four requested brands appear as actual image elements in job and company heroes; Apple list row has its logo |
| Served image bytes | All 59 public image responses return 200 and match manifest hashes |
| Application totals | Unchanged at 33 fictional applications before/after page reads |
| Dash and diff guards | Zero forbidden UI dashes; `git diff --check` passes |
| Playwright | 7 new cases collected only, for Day/Night at 1672, 700 and 390 px, plus broken-image recovery |

The local API ran against `/tmp/ace-company-logos-fictional-20261026.db` with
fictional records only; it did not use or mutate the owner's database. Public
brand names were assigned to four fictional jobs for these checks. Source
bytes were inspected in a local brand contact sheet, not a website screenshot.

Chrome was not launched because the documented laptop cooling restriction
remains. No fresh rendered-page screenshots, pixel comparison, keyboard/browser
accessibility run or production verification are claimed. Pulls job rows and
the Inbox register load interactively; HTTP checks confirm their pages load,
while their full interactive behavior remains a browser verification item.
The seven Playwright cases must run on a machine with working cooling before
claiming visual acceptance. Website deployment requires separate owner approval.

## Files changed

Implementation:

- `web/src/lib/companyLogos.ts`
- `web/src/components/CompanyLogo.tsx`
- `web/src/components/CompanyIdentity.tsx`
- `web/src/components/bits.tsx`
- `web/src/components/page/PageParts.tsx`
- `web/src/components/pulls/PullsTimeline.tsx`
- `web/src/components/jobs/JobListPage.tsx`
- `web/src/components/analytics/AnalyticsView.tsx`
- `web/src/components/inbox/InboxIntelligence.tsx`
- `web/src/components/inbox/InboxReviewPanel.tsx`
- `web/src/components/studio/Checker.tsx`
- `web/src/components/studio/AssessmentView.tsx`
- `web/src/app/app/company/[name]/page.tsx`
- `web/src/app/app/coverage/page.tsx`
- `web/src/app/app/resume-studio/page.tsx`
- `web/src/app/app/resume-studio/history/page.tsx`
- `web/src/app/globals.css`

Tests, provenance and continuity:

- `.github/workflows/ci.yml`
- `web/package.json`
- `web/tests/company-logos.test.mjs`
- `web/tests/inbox-review-render.test.mjs` (loader supports the imported manifest)
- `web/tests/e2e/company-logos.spec.ts`
- `web/public/company-logos/provenance.json`
- `web/public/company-logos/README.md`
- `ACE_NEXT_KNOWLEDGE.md`
- `docs/HANDOFF.md`
- `docs/knowledge/05-web-ui.md`
- `docs/architecture/2026-10-26-company-identity.md`

The following exact new files live under `web/public/company-logos/`:

- `fedex.ico`
- `fedex-freight.png`
- `general-motors.png`
- `southern-company.png`
- `amd.ico`
- `qualcomm.ico`
- `hp.png`
- `netflix.ico`
- `airbnb.png`
- `spotify.png`
- `linkedin.ico`
- `github.png`
- `gitlab.ico`
- `atlassian.ico`
- `intuit.png`
- `paypal.png`
- `block.png`
- `square.ico`
- `visa.ico`
- `jpmorgan-chase.png`
- `goldman-sachs.ico`
- `capital-one.ico`
- `bloomberg.ico`
- `target.ico`
- `boeing.ico`
- `lockheed-martin.ico`
- `northrop-grumman.ico`
- `workday.ico`
- `snowflake.png`
- `databricks.png`
- `datadog.ico`
- `cloudflare.png`
- `mongodb.ico`
- `palantir.ico`
- `lyft.png`
- `dropbox.ico`
- `box.png`
- `pinterest.png`
- `reddit.png`
- `snap.png`
- `zoom.ico`
- `figma.png`
- `notion.ico`
- `roblox.png`
- `electronic-arts.ico`
- `sel.ico`
- `nationwide.ico`
- `formlabs.ico`
