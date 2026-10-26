# Platform company-logo coverage, 2026-10-26

Status: locally tested on `platform-company-logos-20261026`; deployment pending.
This follows the deployed Hive/Vizient correction in `bd5c364`. The owner
reported initials throughout Analytics and requested company marks everywhere
company identity is presented. The earlier correction was insufficient in scope.

## What changed

- The optional bundle now contains 78 authentic company marks. Eighteen new
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
sources. The reviewed bundle covers 19 of them: 18 new marks and one alias.
Marvell and Funnel Leasing remain unavailable. Their official pages were
readable, but declared asset hosts did not authorize reads. Denials were not
bypassed via alternate clients, proxies or third-party logo services. All future
employers still use automatic discovery, but a universal guarantee of an authentic
external image is impossible when evidence is unavailable or access is refused.
The UI never fabricates a replacement brand.

| Validation | Result |
| --- | --- |
| Fictional logo, authentication and source tests | 142 passed |
| Company React contracts, including retries/cleanup | 9 passed |
| Inbox rendering / Analytics rendering | 12 / 4 passed |
| TypeScript | Passed |
| Lint and production build | Passed |
| All bundled provenance hashes | Passed in company contracts |
| Browser rendering / screenshots | Not run; laptop cooling restriction |
| Production release and signed-in verification | Pending |

No extension, migration, scheduler operation, Gmail scope change or application
write is part of this correction. It requires only API/web replacement under
the owner's existing request to deploy tested changes.
