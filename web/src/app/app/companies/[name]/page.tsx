import Link from "next/link";
import { notFound } from "next/navigation";

import { Avatar } from "@/components/bits";
import { JobCard } from "@/components/browse/JobCard";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import type { CompanyRow } from "@/components/browse/CompanyDirectory";
import { TIER_LABEL } from "@/lib/format";
import type { JobPage } from "@/lib/types";

const EMPTY: JobPage = { items: [], total: 0, limit: 0, offset: 0, has_more: false, sort: "", resume_id: null };

export async function generateMetadata({ params }: PageProps<"/app/companies/[name]">) {
  return { title: `${decodeURIComponent((await params).name)} · ace` };
}

export default async function CompanyPage({ params }: PageProps<"/app/companies/[name]">) {
  const name = decodeURIComponent((await params).name);
  const [dir, open, applied] = await Promise.all([
    apiGetOr<{ items: CompanyRow[] }>("/api/companies", { items: [] }),
    apiGetOr<JobPage>("/api/jobs", EMPTY, { company: name, sort: "unapplied_first,new_grad_first,best_match", limit: "60" }),
    apiGetOr<JobPage>("/api/jobs", EMPTY, { company: name, mark: "applied", sort: "newest", limit: "60" }),
  ]);
  const c = dir.items.find((x) => x.name === name);
  if (!c && !open.total && !applied.total) notFound();
  const tier = c?.tier ?? "OTHER";
  return (
    <>
      <div className="head">
        <nav className="crumbs" aria-label="Breadcrumb">
          <Link href="/app">Home</Link>
          <span aria-hidden="true">/</span>
          <Link href="/app/companies">Companies</Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page">{name}</span>
        </nav>
        <div className="co-hero">
          <Avatar name={name} large />
          <div>
            <h1 className="h1">{name}</h1>
            <p className="why" style={{ margin: "4px 0 0" }}>
              {TIER_LABEL[tier] ? `${TIER_LABEL[tier]}, ` : ""}
              {open.total} open role{open.total === 1 ? "" : "s"} for you
              {applied.total ? `, ${applied.total} application${applied.total === 1 ? "" : "s"}` : ""}
            </p>
          </div>
        </div>
      </div>
      <ScrollArea>
        <div className="page">
          <section className="row-sec">
            <div className="row-head">
              <h2 className="row-title">Open roles</h2>
              <span className="spacer" />
              <Link className="row-all" href={`/app/opportunities?company=${encodeURIComponent(name)}`}>
                Open in the full list
              </Link>
            </div>
            {open.items.length ? (
              <div className="card-grid">
                {open.items.map((j) => (
                  <JobCard key={j.id} job={j} />
                ))}
              </div>
            ) : (
              <p className="why">No open role at {name} qualifies right now. ace keeps checking.</p>
            )}
          </section>
          {applied.items.length ? (
            <section className="row-sec">
              <div className="row-head">
                <h2 className="row-title">Your applications here</h2>
              </div>
              <div className="card-grid">
                {applied.items.map((j) => (
                  <JobCard key={j.id} job={j} />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      </ScrollArea>
    </>
  );
}
