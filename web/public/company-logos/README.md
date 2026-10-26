# Reviewed employer icon cache

These are unmodified icon bytes downloaded from the exact official company
URLs in `provenance.json`. The initial 11 were reviewed on 2026-10-25; 48 more
were downloaded and visually inspected on 2026-10-26, for 59 employers total.
Checksums record the cached versions. They identify employers, never ACE.
No marks were generated or reconstructed. Some official pages declare icons
on their own CDN; `website` records the employer page that supplied that URL.

`src/lib/companyLogos.ts` resolves reviewed names and explicit aliases from this
manifest. Matching normalizes Unicode, case, whitespace and periods/commas;
it never strips arbitrary legal suffixes or matches part of a name. A parent
company's icon is not automatically assigned to subsidiaries. FedEx Freight
uses the icon declared by its own official careers website.

The shared `CompanyLogo.tsx`, including the table/detail `Avatar`,
uses these local files. It
never derives a domain from application history, fetches an arbitrary URL,
contacts a third-party logo service, or delays jobs while fetching a logo.
Unknown identities and failed image loads show a neutral monogram beside the
unchanged company name. Empty names show C with the accessible name Company.
Changing companies resets failed-image state. Compact, table and detail sizes
share the same identity mapping in both themes.

To add an employer, confirm its official website, inspect its declared icon,
download the exact image bytes, and visually inspect them. Record the source,
date, SHA-256, local filename and individually reviewed aliases in the manifest.
Run `npm run test:company-logos` from `web/` to catch alias collisions, missing
files, checksum mismatches, identity confusion and image-failure regressions.
Never add a guessed domain or generated substitute. Keep owner history out of
the manifest and tests.

The 2026-10-26 review did not cache Oracle, Intel, Cisco, Dell, Tesla,
Mastercard, Ford, DoorDash or Akamai because their sites refused access; Uber
also refused, HPE timed out, and Walmart supplied no usable raster icon in this
review. These and unreviewed employers retain a visible fallback. This is not
a claim that every company in ACE's dynamic source catalog has an authentic
cached mark.
