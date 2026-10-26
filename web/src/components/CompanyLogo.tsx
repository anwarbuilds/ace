"use client";

import { useState } from "react";
import { clean } from "@/lib/format";
import { companyLogoFor } from "@/lib/companyLogos";

type LogoSize = "compact" | "small" | "table" | "large";

// Identity-keyed state lets a reused row recover from the previous image's
// failure. Images stay local: no browsing history reaches a logo service.
export function CompanyLogo({ name, size = "small", className = "" }: { name: string; size?: LogoSize; className?: string }) {
  const label = clean(name).trim() || "Company";
  const asset = companyLogoFor(name)?.asset;
  return <LogoImage key={`${label}:${asset ?? ""}`} name={label} asset={asset} size={size} className={className} />;
}

function LogoImage({ name, asset, size, className }: { name: string; asset?: string; size: LogoSize; className: string }) {
  const [failed, setFailed] = useState(false);
  const initials = name.split(/\s+/).slice(0, 2).map(word => Array.from(word)[0]).join("").toLocaleUpperCase();
  return <span className={`company-logo company-logo--${size} ${className}`.trim()} title={asset && !failed ? `${name} official website icon` : `${name}: logo unavailable`}>
    {asset && !failed ? /* eslint-disable-next-line @next/next/no-img-element */
      <img ref={element => { if (element?.complete && element.naturalWidth === 0) setFailed(true); }} src={`/company-logos/${asset}`} alt={`${name} logo`} width={size === "large" ? 56 : 28} height={size === "large" ? 56 : 28} decoding="async" onError={() => setFailed(true)} />
      : <span aria-label={`${name} monogram`}>{initials}</span>}
  </span>;
}
