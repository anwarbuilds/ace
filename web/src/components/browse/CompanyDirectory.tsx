"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Avatar } from "@/components/bits";
import { companyHref } from "@/lib/browse";
import { TIER_LABEL } from "@/lib/format";
import type { Tier } from "@/lib/types";

export interface CompanyRow {
  name: string;
  tier: Tier;
  open_roles: number;
  applied: number;
  newest_role_at: string | null;
}

const ORDER: Record<Tier, number> = { BIG_TECH: 0, TOP_TIER: 1, ESTABLISHED: 2, OTHER: 3 };

/** Every employer, as a directory: filter by name or tier, then open its
 *  own page. */
export function CompanyDirectory({ companies }: { companies: CompanyRow[] }) {
  const [q, setQ] = useState("");
  const [tier, setTier] = useState<Tier | "">("");
  const [hiringOnly, setHiringOnly] = useState(true);
  const shown = useMemo(
    () =>
      companies
        .filter((c) => (!q || c.name.toLowerCase().includes(q.toLowerCase())) && (!tier || c.tier === tier))
        .filter((c) => !hiringOnly || c.open_roles > 0)
        .sort((a, b) => ORDER[a.tier] - ORDER[b.tier] || b.open_roles - a.open_roles || a.name.localeCompare(b.name)),
    [companies, q, tier, hiringOnly],
  );
  return (
    <>
      <div className="dir-bar">
        <input
          className="st-input dir-q"
          placeholder="Find a company"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Find a company"
        />
        {(["", "BIG_TECH", "TOP_TIER", "ESTABLISHED"] as const).map((t) => (
          <button key={t || "any"} className={`chip${tier === t ? " ctl-active" : ""}`} onClick={() => setTier(t)}>
            {t ? TIER_LABEL[t] : "Any tier"}
          </button>
        ))}
        <button className={`chip${hiringOnly ? " ctl-active" : ""}`} onClick={() => setHiringOnly((v) => !v)}>
          Hiring now
        </button>
      </div>
      <div className="co-grid">
        {shown.map((c) => (
          <Link key={c.name} className="co-card" href={companyHref(c.name)}>
            <Avatar name={c.name} large />
            <span className="co-card-n">{c.name}</span>
            {TIER_LABEL[c.tier] ? <span className="co-tier">{TIER_LABEL[c.tier]}</span> : <span className="co-tier">&nbsp;</span>}
            <span className="co-card-s">
              {c.open_roles ? `${c.open_roles} open role${c.open_roles === 1 ? "" : "s"}` : "No open roles"}
              {c.applied ? `, applied ${c.applied}` : ""}
            </span>
          </Link>
        ))}
      </div>
      {!shown.length ? <p className="why">No company matches.</p> : null}
    </>
  );
}
