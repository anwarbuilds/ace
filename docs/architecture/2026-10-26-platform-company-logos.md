# Platform company-logo coverage, 2026-10-26

Status: deployed as `0fef238c9a3c5575927786e823109ad351b78245` on 2026-10-26
at 13:49 Pacific; PR #4 merged.
This follows the deployed Hive/Vizient correction in `bd5c364`. The owner
reported initials throughout Analytics and requested company marks everywhere
company identity is presented. The earlier correction was insufficient in scope.

## What changed

- The optional bundle now contains 80 authentic company marks. Twenty new
  PNGs were obtained from official corporate pages or employer-declared assets
  on registered tenant boards, decoded, re-encoded to at most 96 px, visually
  inspected and checksummed. Exact evidence/image URLs are in provenance.
- The visible JP Morgan Chase spelling maps to the existing JPMorgan Chase
  icon. Explicit C3 AI and ForgeNano aliases cover verified brand spellings.
  No arbitrary suffix/substring matching or historical identity edits.
- Shared extraction recognizes Ashby org-theme logo metadata, Workable account
  logo metadata and Greenhouse's dedicated logo element. Provider host and
  asset-path checks exclude arbitrary job previews and platform branding.
  Parser-versioned seed identities invalidate earlier misses.
- Dynamic image failures retry at most twice (2 and 15 seconds). Unmounting or
  changing identity clears pending work. Static assets retain their fallback;
  genuine unavailable external evidence still uses initials.
- Company filters, exclusions, active chips, the selected Analytics company,
  Inbox linked-application tags and audit references use the shared logo.
  Existing Pulls, job/detail tables, Applications, Analytics, company detail,
  Coverage and Resume Studio already use it. Native dropdown options preserve
  their keyboard behavior; selected company evidence has an adjacent mark.
  Literal email bodies, user inputs and notification text are preserved.

## Evidence and limits

The 21 missing names in the supplied view were audited against exact registered
sources. All 21 now resolve through the reviewed bundle: 20 new marks and one alias.
Marvell and Funnel initially had refused corporate CDN assets. Both were
resolved through separate permitted evidence: Funnel's own developer-site
header and the issuer-provided Marvell image in its January 2025 investor-day
release on PR Newswire. Both final assets were decoded and visually inspected.
Denied resources were not reaccessed through proxies or alternate clients. All future
employers still use automatic discovery, but a universal guarantee of an authentic
external image is impossible when evidence is unavailable or access is refused.
The UI never fabricates a replacement brand.

| Validation | Result |
| --- | --- |
| Fictional logo, authentication and source tests | 142 passed |
| Company React contracts, including retries/cleanup | 10 passed |
| Inbox rendering / Analytics rendering | 12 / 4 passed |
| TypeScript | Passed |
| Lint and production build | Passed |
| All bundled provenance hashes | Passed in company contracts |
| Browser rendering / screenshots | Not run; laptop cooling restriction |
| Production release and signed-in HTTP verification | Passed, detailed below |

No extension, migration, scheduler operation, Gmail scope change or application
write is part of this correction. It requires only API/web replacement under
the owner's existing request to deploy tested changes.

## Live verification and rollback

At 2026-10-26T20:48:50Z through 20:48:58Z, the owner-authenticated public HTTPS
path passed every image and all reviewed company detail checks. All 80 served
assets decoded and matched exact provenance hashes. All 21 reviewed company
pages contained their bundled logo reference. The actual default Analytics
Companies tab returned 200 and referenced JP Morgan Chase plus five of the
new asset filenames. Dynamic CLEAR and Iambic routes returned verified
PNGs, exercising general Greenhouse and Ashby extraction despite local bundles.
All four Analytics tabs, Pulls, Inbox, company/job and Opportunities routes
returned 200. Existing Hive/Vizient and anonymous/unknown-name checks pass.

Totals were unchanged: 884 posting applications and 47 external history, 931
combined. Schema remains 0050. No Gmail sync, status review, source registration
or application write was triggered. Temporary owner verification sessions were
revoked immediately in `finally`. Image public URLs/hashes and boolean status
checks were logged, with no owner HTML, mail, credentials or answer values.

Runtime branding hashes match local tested files. API and website are healthy
and public health reports `0fef238`. Only API/web containers changed. Scheduler,
PostgreSQL and Caddy retained their IDs; `.env` bytes are identical. No migration
container ran. Browser rendering/screenshots remain unverified due to cooling.

Private rollback records are on the VM at
`private-backups/platform-company-logos-20261026/`, including a 467,291,925-byte
custom-format database backup with a successfully read restore catalog, runtime
metadata, prior commit and environment snapshot. Prior images are tagged
`oracle-api:before-platform-logos` and `oracle-web:before-platform-logos`.
Rollback uses only prior API/web images, with no automatic database restore.
Non-input Docker exec calls inside SSH `bash -s` must use `</dev/null` so they
cannot consume following commands from the script's stdin.

Refresh the website once to load the new logo manifest. No extension reload or
publication is involved.

## Exact changed files

- `ACE_NEXT_KNOWLEDGE.md`
- `backend/app/branding/discovery.py`
- `backend/app/branding/sources.py`
- `backend/tests/test_company_logos.py`
- `docs/HANDOFF.md`
- `docs/architecture/2026-10-26-platform-company-logos.md`
- `docs/knowledge/05-web-ui.md`
- `docs/knowledge/11-handoff-state-archive.md`
- `web/public/company-logos/README.md`
- `web/public/company-logos/c3-ai.png`
- `web/public/company-logos/cigna-group.png`
- `web/public/company-logos/citi.png`
- `web/public/company-logos/clear.png`
- `web/public/company-logos/costar-group.png`
- `web/public/company-logos/dtcc.png`
- `web/public/company-logos/forge-nano.png`
- `web/public/company-logos/funnel-leasing.png`
- `web/public/company-logos/gartner.png`
- `web/public/company-logos/greenheck-group.png`
- `web/public/company-logos/iambic-therapeutics.png`
- `web/public/company-logos/marvell.png`
- `web/public/company-logos/mastercard.png`
- `web/public/company-logos/medtronic.png`
- `web/public/company-logos/morningstar.png`
- `web/public/company-logos/provenance.json`
- `web/public/company-logos/t-d-williamson.png`
- `web/public/company-logos/thomson-reuters.png`
- `web/public/company-logos/travelers.png`
- `web/public/company-logos/u-s-bank.png`
- `web/public/company-logos/wex.png`
- `web/src/app/app/analytics/analytics.css`
- `web/src/components/CompanyLogo.tsx`
- `web/src/components/analytics/AnalyticsFilters.tsx`
- `web/src/components/inbox/InboxIntelligence.tsx`
- `web/src/components/jobs/ListControls.tsx`
- `web/tests/company-logos.test.mjs`
