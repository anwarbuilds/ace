import Link from "next/link";

import { NavIcon } from "@/components/shell/NavIcon";
import { NAV } from "@/components/shell/nav";

export const metadata = { title: "All pages · ace" };

// Every page, for a phone, where the bottom bar holds only five.
export default function MorePage() {
  return (
    <div className="pg">
      <div className="page-hero">
        <div>
          <div className="eyebrow">Navigation</div>
          <h1 className="h1">All pages</h1>
        </div>
      </div>
      {NAV.map((g) => (
        <section className="more-group" key={g.label} aria-label={g.label}>
          <div className="sb-label">{g.label}</div>
          <div className="more-list">
            {g.items.map((i) => (
              <Link className="more-link" key={i.href} href={i.href}>
                <NavIcon name={i.icon} />
                <span>{i.label}</span>
                <NavIcon name="right" size="sm" />
              </Link>
            ))}
          </div>
        </section>
      ))}
      <section className="more-group" aria-label="Also">
        <div className="sb-label">Also</div>
        <div className="more-list">
          <Link className="more-link" href="/app/answers">
            <NavIcon name="puzzle" />
            <span>Answer bank</span>
            <NavIcon name="right" size="sm" />
          </Link>
          <Link className="more-link" href="/app/insights/skills">
            <NavIcon name="chart" />
            <span>Skills</span>
            <NavIcon name="right" size="sm" />
          </Link>
        </div>
      </section>
    </div>
  );
}
