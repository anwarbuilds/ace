import Link from "next/link";

import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import { GROUPS } from "@/lib/browse";
import type { JobPage } from "@/lib/types";

export const metadata = { title: "Browse · ace" };

export default async function BrowsePage() {
  const totals = await Promise.all(
    GROUPS.map((g) =>
      apiGetOr<JobPage | null>("/api/jobs", null, { ...g.params, limit: "1" }).then((p) => p?.total ?? 0),
    ),
  );
  return (
    <>
      <div className="head">
        <div className="head-row">
          <h1 className="h1">Browse</h1>
        </div>
        <p className="why" style={{ margin: "8px 0 0" }}>
          Every group is a saved view of the same qualifying roles. Nothing here is hidden from Opportunities.
        </p>
      </div>
      <ScrollArea>
        <div className="page">
          <div className="dept-grid">
            {GROUPS.map((g, i) => (
              <Link key={g.slug} className="dept" href={`/app/browse/${g.slug}`}>
                <span className="dept-n">{totals[i].toLocaleString("en-US")}</span>
                <span className="dept-t">{g.title}</span>
                <span className="dept-b">{g.blurb}</span>
              </Link>
            ))}
            <Link className="dept" href="/app/companies">
              <span className="dept-n">A to Z</span>
              <span className="dept-t">Companies</span>
              <span className="dept-b">Every employer with an open role for you, or an application.</span>
            </Link>
          </div>
        </div>
      </ScrollArea>
    </>
  );
}
