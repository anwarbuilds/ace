"use client";

import { useState } from "react";
import { clean } from "@/lib/format";

// Exact, reviewed identities only. Assets are cached from the official sites;
// see public/company-logos/provenance.json. No runtime requests disclose history.
const LOGOS: Record<string, string> = { Google: "google", Apple: "apple", Microsoft: "microsoft", Stripe: "stripe", Amazon: "amazon", NVIDIA: "nvidia", Adobe: "adobe", IBM: "ibm", Salesforce: "salesforce", Meta: "meta", ServiceNow: "servicenow" };
export function CompanyLogo({ name }: { name: string }) {
  const [failed, setFailed] = useState(false);
  const asset = LOGOS[name];
  return <span className="company-logo" title={asset && !failed ? `${clean(name)} official website icon` : `${clean(name)}: logo unavailable`}>
    {asset && !failed ? /* eslint-disable-next-line @next/next/no-img-element */
      <img ref={element => { if (element?.complete && element.naturalWidth === 0) setFailed(true); }} src={`/company-logos/${asset}.ico`} alt={`${clean(name)} logo`} width="28" height="28" onError={() => setFailed(true)} />
      : <span aria-label={`${clean(name)} monogram`}>{clean(name).split(/\s+/).slice(0,2).map(w => w.charAt(0)).join("").toLocaleUpperCase()}</span>}
  </span>;
}
