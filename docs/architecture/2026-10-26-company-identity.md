# Shared company identity and automatic future logos, 2026-10-26

Status: released in `21f563a` on 2026-10-26 after owner approval. PR #1 is merged.
All 59 live assets passed hash checks; Apple details and automatic Shopify
retrieval passed signed-in HTTP checks. Browser validation remains pending.
See `2026-10-26-quick-fill-release.md` for production evidence and rollback.
The following records the original local implementation audit.

The owner requested the same authentic logo inside details and on lists, then
clarified that every newly pulled employer must use automatic discovery. The
59 reviewed bundled icons/71 aliases are now an optional fast path. An employer
outside the bundle uses ACE's owner-only `/api/company-logo?name=...` route,
without adding another company to source code or a branding allowlist.

## Tenant follow-up, 2026-10-26

Status: tested candidate on `company-logo-tenants-20261026`, deployment pending.
The owner reported Hive and Vizient initials on live Pulls. Registered public
source pages returned 200 but neither matched the original extraction rules.

- Workday exposes branding via `og:image` at its own site's `/assets/logo`.
  Vizient's structured payroll entity name differs from the display name, so
  requiring exact organization text skipped the asset. Only a same-HTTPS-host,
  same-site exact branding endpoint is now accepted. Other tenants, sites,
  preview images, query variants and lookalike hosts are rejected.
- Lever's dedicated `a.main-header-logo` contains the tenant's image, while the
  provider logo is in its footer. This header now works across employer rebrands
  on verified Lever tenants. Generic `og:image` remains excluded.
- [Hive's official homepage](https://thehive.ai/) announces that Hive is now
  Deploy; [its careers page](https://thehive.ai/careers) links to the registered
  Lever `hive` tenant. That tenant now displays Deploy branding. Its S3 image
  CDN's robots response does not authorize automated reads. The unmodified
  [official website favicon](https://thehive.ai/favicon.ico) was available,
  decoded and visually reviewed, and is bundled with exact provenance.
  The bundle now has 60 icons. No unrelated Hive businesses or guessed aliases
  are included. Existing company/history names are preserved.
- Parser-versioned seed keys invalidate old six-hour negative cache entries
  without touching application/source records. Fetch bounds, robots/refusal
  handling, owner-only access and PNG re-encoding remain unchanged.

135 fictional backend logo/auth/source contracts and 7 React contracts pass.
The candidate parser fetched Vizient's authentic 96 x 44 PNG using the actual
registered production source and existing bounded public fetcher, with no
service replacement. Both public images were visually inspected as standalone
assets. TypeScript, lint and the production build pass. Nine Playwright cases
collect; execution/screenshots remain suspended for cooling. Deployment checks
are pending.
No scheduler, migration, Gmail sync or application status operation is needed.

Changed files: branding `discovery.py`/`sources.py`, backend logo tests, frontend
logo contracts, `hive.ico`, provenance and logo README, this architecture note,
web knowledge, handoff and the root knowledge record.

## Behavior

The shared CompanyLogo inherits the existing company's name on every supported
surface: Pulls rows/dialog, job tables and details, company evidence pages,
external applications, Analytics employer history, Inbox application records,
Coverage and Resume Studio/check history. Unknown names now start a lazy
same-origin image request; readable initials stay visible during loading and
on failure. Success/error state resets on identity changes. The approved layout,
company-first ordering, typography and 36/64 px table/hero sizes remain, with
26/48 px sizes below the existing 720 px breakpoint.

The backend reads exact employer/source identities from the existing catalog
and indexed job records. Enabled registered source metadata, verified board
accounts and stored jobs establish which public employer pages can be read.
Feed-only/unregistered links, external application URLs and arbitrary browser
URLs never become fetch seeds. It accepts an employer-owned site's declared
icon, a company-specific logo on a verified tenant board, or branding/website
from an exactly matched structured hiringOrganization. Shared ATS/platform
favicons and social-profile branding are excluded. No company domain is guessed
and no parent company's mark is automatically assigned to another employer.

The independent asset service performs certificate-checked HTTPS, validates
all DNS answers and pins the public address with the original TLS SNI/Host.
It checks redirects and robots for pages and image CDNs, stops on an explicit
refusal, shares a host cooldown after rate limits, limits bytes/deadlines and forwards no cookies, referrers, mail or
owner application contents. Raster images are decoded and re-encoded as PNG
at up to 96 px. HTML, SVG, tracking-size, transparent and solid placeholders
are not returned as brand assets.

Four asset workers, a 32-request ceiling and coalesced company lookups keep
this independent of job polling. Cancelling one image request does not cancel
other rows' shared lookup. The 512-entry cache retains source, evidence page,
fetch time and PNG hash. Successes expire after seven days, misses after six
hours; first-job evidence invalidates an earlier board-only lookup. Private
0700/0600 disposable cache files live under the system temp directory in
`ace-company-logo-cache-v1`, outside Git and the database. A replacement
container may rebuild that cache automatically. The API's normal owner guard,
extension scope and no-store policy remain; database connections close before
public image work. Unavailable evidence returns 204 so the client retains
initials without a fake brand or noisy missing-resource response.

## Scope and limits

The API has a new public-branding-fetch exception to its previous prohibition
on inline ATS networking. It still never polls or evaluates jobs inline.
Application identities, totals/statuses, job discovery business rules, auth,
Gmail permissions, Career Dashboard, extension, schema and scheduler are
unchanged. No migration or scheduler operation occurred. A release requires
matching API and website images and separate owner approval.

Automatic discovery applies to future employers without manual logo entries.
An external site can still refuse access, disallow reading, require browser
rendering or provide no trustworthy supported image. Such a company retains
visible initials and retries after the cache cooldown. Authentic logos from
every external company cannot be guaranteed; substitutes are never fabricated.
The optional bundle remains useful for reviewed assets on blocked sites.

## Validation

| Check | Result |
| --- | --- |
| TypeScript, ESLint, webpack production build | Passed |
| Backend logo/source/transport/cache contracts | 53 passed |
| Existing auth and board-name regressions | 73 passed; 126 backend tests passed together |
| Company React/DOM contracts | 7 passed, including future-name loading/success/failure and identity changes |
| Existing Inbox review rendering | 8 passed |
| Existing bundled assets | All 59 decode and match recorded SHA-256; earlier built-site serving checks verified all 59 |
| Real public future-employer discovery | Shopify, outside the bundled list, automatically supplied its authentic icon from its official careers site |
| Built local website/API proxy | Shopify company HTML uses the dynamic route; authenticated request returns a PNG up to 96 px, repeat bytes match; anonymous request denied and unknown source returns 204 |
| Fictional application totals | Stayed 33 before and after the automatic route checks |
| Dash/diff guards | Zero forbidden UI dashes; `git diff --check` passes |
| Playwright | 9 cases collected only: Day/Night at 1672, 700 and 390 px; broken image, unbundled company success and pending/unavailable evidence |

The real public check used
[Shopify's official careers page](https://www.shopify.com/careers), whose
HTML declared the downloaded icon. It was inspected locally, not added to the
bundled manifest. The website integration used an explicitly fictional Shopify
job in `/tmp/ace-company-logos-fictional-20261026.db`, never owner applications.
All automated backend records/network responses are fictional/in-memory.
The earlier shared-logo pass also checked 17 authenticated local pages and all
59 served bundle hashes. Current backend tests verify a name first unavailable
and then newly registered, exact identity protection, first-job invalidation,
refusals, mixed/private DNS, pinning, redirect robots checks, raster decoding,
cache reuse/expiry/restart, coalescing, cancellation and unchanged totals.

Chrome was not launched because the documented laptop cooling restriction
remains. No fresh website screenshots, pixel comparison, browser accessibility
run or production verification are claimed. The 9 browser cases remain pending
on a machine with working cooling. The temporary local services were stopped;
no production deployment was performed.

## Files changed

Implementation:

- `backend/app/branding/__init__.py`
- `backend/app/branding/sources.py`
- `backend/app/branding/transport.py`
- `backend/app/branding/discovery.py`
- `backend/app/branding/cache.py`
- `backend/app/api/routers/companies.py`
- `backend/app/api/main.py`

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

- `backend/tests/test_company_logos.py`
- `docs/knowledge/08-operations-and-testing.md`

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
