# Automatic Pulls company-logo recovery, 2026-10-26

Status: deployed and verified through public and signed-in HTTPS at
2026-10-27T00:19Z (2026-10-26 17:19 Pacific). The owner explicitly
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


## Packaging verification correction

The first live asset check caught HTTP 500 for the five new bundled files.
The private release script's restrictive umask had also applied to Git's new
public files, which Docker copied as root-owned mode 0600. The unprivileged
Node process could not read them. The verification session was revoked and
application totals remained unchanged. Public health alone did not expose it.

The web runtime image now grants public assets read/traversal permissions
before switching to Node, without granting write access or changing ownership.
Validate every manifest asset's hash through public HTTPS and read access as
the actual container user. Use umask 022 for future Git checkouts and retain
umask 077 for private backups. This is a web packaging fix; no API/backend
behavior changes or database rollback are needed.


## Final live evidence and rollback

API branding source `d0342d4` and web packaging source
`1fee67127877838f09b9a42f5edef6bc4669f34e` are running and healthy. Public health
reports the latter SHA. The actual Node runtime user can read all 87 public
logo-directory files (85 images plus README/manifest). Signed-in live HTTPS
verified all 85 image hashes; all five direct automatic routes returned 200,
verified PNGs matching reviewed hashes and identical cached bytes. Each of the
five company, latest job and Opportunities pages returned 200 with the correct
bundled logo reference. Pulls, all four Analytics tabs and Inbox returned 200.
Anonymous logo access returned 401 and an unknown employer returned 204.
Temporary owner verification sessions were revoked immediately, including the
session used by the initial failed asset check. No owner HTML or credentials
were retained. These are HTTP/asset checks, not browser screenshots or rendering.

The fresh private 470,001,414-byte backup passed complete gzip integrity and
PostgreSQL restore-catalog checks before activation. This was not a restore drill.
Artifacts are in `private-backups/pulls-company-logos-20261026/` on the VM:
backup/catalog, private inventories, build logs, source/image/container records
and `live-verification-final.json`. `.env` bytes, schema 0050 and scheduler,
PostgreSQL and Caddy container IDs are unchanged. The web-only correction also
left the newly deployed API container unchanged. Runtime branding hashes match
tested source. All nine protected table counts and applied count matched at
initial activation. During the web correction, job marks and applied marks each
increased by one concurrently; other protected counts stayed equal. The release
invoked no mark/status, Gmail sync/recheck, source registration or application
write. Final verification totals were stable at 889 posting applications plus
47 external history (936). Discovery continued independently throughout.

Prior working API/web images are tagged `oracle-api:before-pulls-company-logos`
and `oracle-web:before-pulls-company-logos`. Roll back only affected application
images; never automatically restore the database. Concurrent Inbox reliability
diagnosis/documentation was preserved on the source branch; no planned Inbox
reliability implementation was deployed by this logo release. Refresh the website
to load the 85-image manifest. Browser checks remain pending due to cooling.


## Final live evidence

All 85 public assets decoded and matched provenance hashes. Each reported
employer's automatic route returned verified PNG bytes matching its bundled
image and identical bytes on repeat: Uber 96 x 96, Optiver 96 x 96, Chime
96 x 28, temporal 96 x 96 and twitch 32 x 32. All fifteen company/job/Opportunities
pages returned 200 with the corresponding bundled image reference. Pulls,
all four Analytics tabs and Inbox returned 200. Anonymous logo access returned
401; an unknown fictional employer returned 204. The temporary owner session
was revoked in `finally`. No Gmail sync or application mutation was invoked.

Application totals stayed 936 (889 posting applications and 47 external history)
during final verification; schema stayed 0050. At the initial API/web swap all
nine protected row counts and applied-mark count matched exactly. During the
later web-only correction one concurrent new mark/application appeared; all
other protected counts held. No mark endpoint was invoked by release checks.
Scheduler/PostgreSQL/Caddy IDs and private environment bytes match the original
snapshot; the web-only correction also kept the API container unchanged.

Private evidence and rollback are at
`private-backups/pulls-company-logos-20261026/` on the VM. The fresh
470,001,414-byte compressed custom-format backup passed full gzip integrity and
restore-catalog checks, not a restore drill. Original images remain tagged
`oracle-api:before-pulls-company-logos` and
`oracle-web:before-pulls-company-logos`; rollback replaces only application
images, never restores production data automatically. Both prepared builds
passed. Runtime-user read checks passed for every logo-directory file.
No migration, scheduler operation, extension publication or Gmail change ran.

The concurrent `6571585` Inbox diagnosis/report was preserved on the source
branch. Its proposed reliable-Inbox implementation remains unbuilt and unshipped.
The logo release does not implement that plan. Chrome stayed off for cooling;
these are signed-in HTTP/asset checks, not browser visual verification.
