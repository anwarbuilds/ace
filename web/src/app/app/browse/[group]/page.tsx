import Link from "next/link";
import { notFound } from "next/navigation";

import { JobCard } from "@/components/browse/JobCard";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import { BROWSE_SORTS, GROUPS, groupBySlug, sortParam } from "@/lib/browse";
import type { JobPage, Tier } from "@/lib/types";

const PER_PAGE = 24;

const TIERS: [Tier, string][] = [
  ["BIG_TECH", "Big tech"],
  ["TOP_TIER", "Top tier"],
  ["ESTABLISHED", "Established"],
];

export async function generateMetadata({ params }: PageProps<"/app/browse/[group]">) {
  const g = groupBySlug((await params).group);
  return { title: `${g?.title ?? "Browse"} · ace` };
}

export default async function GroupPage({ params, searchParams }: PageProps<"/app/browse/[group]">) {
  const group = groupBySlug((await params).group);
  if (!group) notFound();
  const sp = await searchParams;
  const one = (k: string) => (Array.isArray(sp[k]) ? sp[k][0] : sp[k]) ?? "";
  const sort = BROWSE_SORTS.some(([k]) => k === one("sort")) ? one("sort") : "fit";
  const tier = TIERS.some(([t]) => t === one("tier")) ? one("tier") : "";
  const pageNo = Math.max(1, parseInt(one("page"), 10) || 1);

  const query: Record<string, string> = {
    ...group.params,
    sort: sortParam(sort, group),
    limit: String(PER_PAGE),
    offset: String((pageNo - 1) * PER_PAGE),
  };
  if (tier) query.tier = tier;
  const data = await apiGetOr<JobPage>("/api/jobs", { items: [], total: 0, limit: 0, offset: 0, has_more: false, sort: "", resume_id: null }, query);
  const pages = Math.max(1, Math.ceil(data.total / PER_PAGE));

  const href = (change: { sort?: string; tier?: string; page?: number }) => {
    const p = new URLSearchParams();
    const s = change.sort ?? sort;
    const t = change.tier ?? tier;
    const n = change.page ?? 1;
    if (s !== "fit") p.set("sort", s);
    if (t) p.set("tier", t);
    if (n > 1) p.set("page", String(n));
    const q = p.toString();
    return `/app/browse/${group.slug}${q ? `?${q}` : ""}`;
  };

  return (
    <>
      <div className="head">
        <nav className="crumbs" aria-label="Breadcrumb">
          <Link href="/app">Home</Link>
          <span aria-hidden="true">/</span>
          <Link href="/app/browse">Browse</Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page">{group.title}</span>
        </nav>
        <div className="head-row">
          <h1 className="h1">{group.title}</h1>
          <span className="h1-count">{data.total.toLocaleString("en-US")}</span>
        </div>
        <p className="why" style={{ margin: "6px 0 0" }}>
          {group.blurb}
        </p>
      </div>
      <ScrollArea list>
        <div className="page browse">
          <aside className="browse-side" aria-label="Refine">
            <p className="eyebrow">Sort by</p>
            {BROWSE_SORTS.map(([k, label]) => (
              <Link key={k} className="side-opt" aria-current={k === sort ? "true" : undefined} href={href({ sort: k })}>
                {label}
              </Link>
            ))}
            {group.params.tier ? null : (
              <>
                <p className="eyebrow" style={{ marginTop: 22 }}>
                  Company tier
                </p>
                <Link className="side-opt" aria-current={!tier ? "true" : undefined} href={href({ tier: "" })}>
                  Any
                </Link>
                {TIERS.map(([t, label]) => (
                  <Link key={t} className="side-opt" aria-current={t === tier ? "true" : undefined} href={href({ tier: t })}>
                    {label}
                  </Link>
                ))}
              </>
            )}
            <p className="eyebrow" style={{ marginTop: 22 }}>
              More groups
            </p>
            {GROUPS.filter((g) => g.slug !== group.slug).map((g) => (
              <Link key={g.slug} className="side-opt" href={`/app/browse/${g.slug}`}>
                {g.title}
              </Link>
            ))}
          </aside>
          <div className="browse-main">
            {data.items.length ? (
              <div className="card-grid">
                {data.items.map((j) => (
                  <JobCard key={j.id} job={j} />
                ))}
              </div>
            ) : (
              <div className="empty">
                <h3>Nothing in {group.title.toLowerCase()} right now</h3>
                <p>ace checks every board continuously. New roles appear here as they are found.</p>
                <Link className="btn btn-secondary btn-sm" href="/app/opportunities">
                  See every opportunity
                </Link>
              </div>
            )}
            {pages > 1 ? (
              <nav className="pager" aria-label="Pages">
                {pageNo > 1 ? (
                  <Link className="pager-btn" href={href({ page: pageNo - 1 })}>
                    Previous
                  </Link>
                ) : null}
                {Array.from({ length: pages }, (_, i) => i + 1)
                  .filter((n) => n === 1 || n === pages || Math.abs(n - pageNo) <= 2)
                  .map((n) => (
                    <Link
                      key={n}
                      className="pager-btn"
                      aria-current={n === pageNo ? "page" : undefined}
                      href={href({ page: n })}
                    >
                      {n}
                    </Link>
                  ))}
                {pageNo < pages ? (
                  <Link className="pager-btn" href={href({ page: pageNo + 1 })}>
                    Next
                  </Link>
                ) : null}
              </nav>
            ) : null}
          </div>
        </div>
      </ScrollArea>
    </>
  );
}

