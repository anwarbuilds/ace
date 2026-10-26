import provenance from "../../public/company-logos/provenance.json";

// Reviewed identities only: no substring matches, inferred domains or arbitrary
// legal suffix removal that could assign another employer's mark.
export function normalizeCompanyIdentity(name: string): string {
  return name.normalize("NFKC").toLocaleLowerCase("en-US")
    .replace(/[.,®™]/g, "").replace(/\s+/g, " ").trim();
}

const logos = new Map(provenance.flatMap(row =>
  [row.company, ...("aliases" in row ? row.aliases as string[] : [])]
    .map(name => [normalizeCompanyIdentity(name), row] as const),
));

export function companyLogoFor(name: string) {
  return logos.get(normalizeCompanyIdentity(name));
}
