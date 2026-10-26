# Reviewed employer icon cache

These are authentic marks downloaded from the exact official employer URLs
in `provenance.json`. The first 60 preserve the downloaded icon bytes; the
20 additions below were decoded and re-encoded as PNG at up to 96 px. The initial 11 were reviewed on 2026-10-25; 48 more
were downloaded and visually inspected on 2026-10-26, for 59 employers total.
One more official Hive icon was reviewed on 2026-10-26, for 60 employers total.
Checksums record the cached versions. They identify employers, never ACE.
No marks were generated or reconstructed. Some official pages declare icons
on their own CDN; `website` records the employer page that supplied that URL.

`src/lib/companyLogos.ts` resolves reviewed names and explicit aliases from this
manifest. Matching normalizes Unicode, case, whitespace and periods/commas;
it never strips arbitrary legal suffixes or matches part of a name. A parent
company's icon is not automatically assigned to subsidiaries. FedEx Freight
uses the icon declared by its own official careers website.

The bundled cache is an optional fast path. Companies outside this list now
use the authenticated `/api/company-logo?name=...` route automatically. No
manual manifest edit is needed for a newly pulled employer. The backend
resolves its existing registered source and official posting, reads permitted
public branding, validates image bytes, and caches a small PNG with its source,
evidence page and fetch time. The browser contacts ACE only; it sends no history
to a third-party logo service and the backend forwards no cookies or mail data.

The service accepts an employer-owned site's declared icon, an employer logo
on a verified tenant board, or a logo/website identified by an exactly matched
structured hiringOrganization. It never guesses a company domain, substitutes
an ATS platform favicon, or borrows a parent company's branding automatically.
HTTPS/public-address checks, DNS pinning, redirect/robots checks, time/size
limits and four asset workers keep this separate from job polling. Only decoded
raster images are returned, re-encoded as PNG at up to 96 px; SVG/HTML and empty
or tracking placeholders are not served. No migration or scheduler edit.

Initials remain visible while a dynamic logo is loading or unavailable. Empty
names show C with the accessible name Company. Successful/error state resets
when the employer changes. The private cache holds at most 512 entries, with
seven-day successes and six-hour misses; the first stored job invalidates an
earlier board-only lookup. Its disposable disk cache is outside the repository
and rebuilds after a container replacement. Other ACE data is untouched.

To expand the optional bundled cache, confirm an official website, inspect its
declared icon, download exact bytes and review the image. Record source, date,
SHA-256, local filename and reviewed aliases in the manifest. Run
`npm run test:company-logos` from `web/`. This manual fast path is optional;
automatic future-company discovery does not depend on this list.

The tenant-branding update also recognizes Lever's dedicated employer header
and Workday's same-host, same-site `/assets/logo` metadata. Generic social
preview images and shared provider marks remain excluded. Workday payroll
organization names need not equal the display company when the asset is bound
to the verified tenant/site. Parser revisions invalidate older cached misses.
Hive's official website confirms its rebrand to Deploy and links to the
registered Lever `hive` tenant. The Lever image CDN did not permit automated
reading, so the bundle uses the authentic icon from `https://thehive.ai/favicon.ico`.
Company/history names stay unchanged. No unrelated Hive company is an alias.

The 2026-10-26 review did not cache Oracle, Intel, Cisco, Dell, Tesla,
Mastercard, Ford, DoorDash or Akamai because their sites refused access; Uber
also refused, HPE timed out, and Walmart supplied no usable raster icon in this
review. These employers now also use automatic discovery when a trusted source
is available. Access refusals or unavailable trustworthy raster assets still
produce visible initials; universal external logo availability cannot be promised.

## Platform coverage follow-up, 2026-10-26

The bundle now has 80 reviewed marks. Added C3.ai, Cigna Group, Citi, CLEAR,
CoStar Group, DTCC, Forge Nano, Gartner, Greenheck Group, Iambic Therapeutics,
Mastercard, Medtronic, Morningstar, T.D. Williamson, Thomson Reuters, Travelers,
U.S. Bank, Wex, Marvell and Funnel Leasing. All were decoded, visually reviewed and checksummed. The
JP Morgan Chase spelling now resolves to the existing JPMorgan Chase mark;
C3 AI and ForgeNano have explicit reviewed aliases. No application data or
history-based company counts are stored in this manifest.

Shared discovery also recognizes provider-declared Ashby org-theme logos,
Workable account branding and Greenhouse's tenant-logo element. Generic
preview images and platform favicons remain excluded. Bounded frontend retries
allow transient busy/offline failures to recover, with no polling loop.

Marvell and Funnel initially had refused corporate CDN assets. The final
review obtained permitted authentic marks from Funnel's own developer header
and the issuer-provided image in Marvell's January 2025 PR Newswire release.
Refused image hosts were not bypassed. Provenance records these distinct sources.
