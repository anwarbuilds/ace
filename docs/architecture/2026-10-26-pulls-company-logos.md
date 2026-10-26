# Automatic Pulls company-logo recovery, 2026-10-26

Status: implemented and under release validation. Production activation and
post-release verification will be recorded separately. The owner explicitly
requested fixing missing logos, including future incoming employers, and deploying.

## Cause and correction

The screenshot employers all reached the existing automatic service, but its
branding extraction was incomplete:

- Uber: Oracle declares an employer favicon at a site-number-bound endpoint.
  Accept only the verified Oracle tenant host, candidate-site page, declared
  site number and exact favicon path, with no unexpected query parameters.
- Chime: Greenhouse supplies its logo through a sharded recruiting CDN and a
  legal payroll alt name. Accept tenant-logo metadata/images only at the
  provider's exact CDN host family and dedicated employer-logo path.
- temporal: Ashby publishes the authentic logo as `twitter:image`, while
  `og:image` is a social preview. Accept the existing org-theme-logo path
  from either metadata field; do not accept the social preview path.
- Optiver: a Greenhouse posting leads to the employer's own site. Its exact
  structured hiringOrganization authorizes declared icons on that nonshared
  host, without assuming every Greenhouse job remains hosted by Greenhouse.
- twitch: Greenhouse's tenant configuration declares the official employer
  website even when its logo URL is null. Parse the fixed configuration as JSON
  without executing JavaScript, follow its declared HTTPS employer site and use
  that site's icon. Legacy HTTP declarations are contacted only over HTTPS.

These rules apply to future registered employers. A transient page/image failure
can fall through to another already-verified candidate within the existing
12-second/four-page budget. An explicit refusal still stops resolution. Public
address pinning, robots, authentication, raster validation, cache/worker limits
and all data boundaries remain. Parser v4 invalidates old misses.

All five candidate lookups retrieved authentic images from the VM through the
unchanged production transport. They were decoded and visually inspected, then
added to the optional bundle with exact source/evidence/hash provenance. The
bundle now has 85 images. Existing shared components cover Pulls rows, job heroes,
company pages, Opportunities, Applications, Analytics, filters and Inbox records.
No per-employer code is needed for future automatic discovery.

External evidence can still be absent or refused. This change does not promise
an invented mark or company/sponsorship facts when authoritative evidence is
unavailable. Company labels and application identities stay exact.

## Validation and release boundaries

Focused fictional backend logo/auth tests: 159 passed; source-host/board-name
contracts: 9 passed. Company React contracts: 11 passed, including the five
reported names across list, hero and company detail surfaces and all 85 asset
hashes. Existing Inbox and Analytics render contracts passed. TypeScript,
lint, production build, zero-hit dash scan and whitespace checks passed. Chrome remains off
under the laptop cooling restriction; no browser screenshots are claimed.

Only the independent branding parser, parser cache revision, public logo assets,
focused tests and documentation change. No schema/migration, scheduler,
eligibility, adapters, Gmail configuration, application status, auth, extension
or other backend feature changes are part of this release. Production activation
will replace only API/web after a fresh private backup and verified rollback
images, with service/container and protected-inventory comparisons.
