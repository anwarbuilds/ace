import type { ReactNode } from "react";
import { CompanyLogo } from "@/components/CompanyLogo";
import { clean } from "@/lib/format";

/** Keep company names and their existing links alongside the shared mark. */
export function CompanyIdentity({ name, children }: { name: string; children?: ReactNode }) {
  return <span className="company-identity"><CompanyLogo name={name} size="compact" /><span className="company-identity-text">{children ?? (clean(name).trim() || "Company")}</span></span>;
}
