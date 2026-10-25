# Reviewed employer icon cache

These are authentic favicon bytes downloaded from the exact official company
URLs in `provenance.json`, reviewed visually on 2026-10-25. Checksums record the
cached versions. They are used as small employer identifiers, never as ACE
branding. No marks were generated or reconstructed.

`CompanyLogo.tsx` maps exact reviewed company names to these local files. It
never derives a domain from application history, fetches an arbitrary URL,
contacts a third-party logo service, or delays jobs while fetching a logo.
Unknown identities and failed image loads show a neutral monogram beside the
unchanged company name. Additional employers need an explicit reviewed mapping
and official source record. An unavailable Oracle icon was not cached.
