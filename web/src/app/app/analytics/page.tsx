import Link from "next/link";

import {
  ApplicationCount,
  ApplicationHeardBack,
  ApplicationHeardBackFoot,
  ApplicationInterviewFoot,
  ApplicationStageCount,
} from "@/components/applications/ApplicationCount";
import { Bars, DayColumns, Kpi, PageHero } from "@/components/page/PageParts";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import { STATUS_LABEL, TIER_LABEL, familyLabel } from "@/lib/format";
import type { ApplicationStatus, Tier } from "@/lib/types";

export const metadata = { title: "Analytics · ace" };

interface Bucket {
  open: number;
  applied: number;
  high: number;
  medium: number;
  minimal: number;
  unscored: number;
}

interface Dashboard {
  total_open: number;
  resume: { label: string } | null;
  scores: Record<"high" | "medium" | "minimal" | "unscored", number>;
  tiers: (Bucket & { tier: Tier })[];
  families: (Bucket & { family: string })[];
  top_companies: { name: string; tier: Tier; open: number; best: number | null; applied: number }[];
  applications: Partial<Record<ApplicationStatus, number>>;
  daily: { date: string; found: number }[];
  thresholds: { high: number; medium: number };
  applied: Applied;
  filters: { days: number; family: string | null };
  available_families: string[];
}

interface Applied {
  total: number;
  with_posting: number;
  without_posting: number;
  by_status: Partial<Record<ApplicationStatus, number>>;
  by_family: { family: string; count: number }[];
  top_companies: { name: string; count: number }[];
  daily: { date: string; applied: number }[];
  undated: number;
  heard_back: number;
  interviews: number;
  offers: number;
}

const BANDS = ["high", "medium", "minimal", "unscored"] as const;

const BAND_LABEL: Record<(typeof BANDS)[number], string> = {
  high: "High",
  medium: "Medium",
  minimal: "Minimal",
  unscored: "Not scored",
};

// One score bar: the share of each band, separated by a hairline gap,
// with the exact counts on hover.
function ScoreBar({ b }: { b: Bucket }) {
  return (
    <span className="db-stack" aria-hidden="true">
      {BANDS.map((k) =>
        b[k] ? (
          <span
            key={k}
            className={`db-seg db-${k}`}
            style={{ flexGrow: b[k] }}
            title={`${BAND_LABEL[k]}: ${b[k]} of ${b.open}`}
          />
        ) : null,
      )}
    </span>
  );
}

function Legend({ t }: { t: Dashboard["thresholds"] }) {
  return (
    <div className="db-legend">
      <span>
        <i className="db-high" /> High, {t.high} or more
      </span>
      <span>
        <i className="db-medium" /> Medium, {t.medium} to {t.high - 1}
      </span>
      <span>
        <i className="db-minimal" /> Minimal, under {t.medium}
      </span>
      <span>
        <i className="db-unscored" /> Not scored
      </span>
    </div>
  );
}

function BreakdownTable({
  rows,
}: {
  rows: { key: string; label: string; href: string; b: Bucket }[];
}) {
  return (
    <div className="db-table" role="table">
      <div className="db-tr db-th" role="row">
        <span role="columnheader">Group</span>
        <span role="columnheader">Open</span>
        <span role="columnheader">Applied</span>
        <span role="columnheader">How your resume scores</span>
        <span role="columnheader">High</span>
      </div>
      {rows.map((r) => (
        <Link key={r.key} className="db-tr" role="row" href={r.href}>
          <span className="db-name" role="cell">{r.label}</span>
          <span className="db-num" role="cell">{r.b.open}</span>
          <span className="db-num" role="cell">{r.b.applied}</span>
          {r.b.open ? <span role="cell"><ScoreBar b={r.b} /></span> : <span className="st-muted" role="cell">none open</span>}
          <span className="db-num" role="cell">{r.b.high}</span>
        </Link>
      ))}
    </div>
  );
}

const STATUS_ORDER: ApplicationStatus[] = ["applied", "screening", "interviewing", "offer", "accepted", "rejected", "withdrawn", "ghosted"];

export default async function AnalyticsPage({ searchParams }: PageProps<"/app/analytics">) {
  const query = await searchParams;
  const days = query.days === "30" || query.days === "90" ? query.days : "14";
  const family = typeof query.family === "string" ? query.family : "";
  const params: Record<string, string> = { days };
  if (family) params.family = family;
  const d = await apiGetOr<Dashboard | null>("/api/dashboard", null, params);
  if (!d) {
    return (
      <div className="pg">
        <PageHero eyebrow="Understand what works" title="Analytics" subtitle="The analysis could not be loaded. Check that the API is running, then reload." />
      </div>
    );
  }
  const a = d.applied;
  const pct = (n: number) => (d.total_open ? Math.round((100 * n) / d.total_open) : 0);
  const appliedRange = a.daily.reduce((x, y) => x + y.applied, 0);
  const foundRange = d.daily.reduce((x, y) => x + y.found, 0);

  return (
    <ScrollArea>
      <div className="pg">
        <PageHero
          eyebrow="Understand what works"
          title="Analytics"
          subtitle={
            <>
              Application performance, role distribution and stage progression. Every metric links to underlying records.{" "}
              {d.resume ? `Resume fit uses ${d.resume.label}.` : "No resume is used for matching yet."}
            </>
          }
          actions={
            <a className="btn" href="/api/applications/export.csv" download>
              Export applications CSV
            </a>
          }
        />

        <form className="analytics-filters" action="/app/analytics">
          <label>
            Trend range
            <select name="days" defaultValue={String(d.filters.days)}>
              <option value="14">Last 14 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
            </select>
          </label>
          <label>
            Discovery role family
            <select name="family" defaultValue={d.filters.family ?? ""}>
              <option value="">All role families</option>
              {d.available_families.map((value) => <option key={value} value={value}>{familyLabel(value)}</option>)}
            </select>
          </label>
          <button className="btn" type="submit">Apply filters</button>
          {d.filters.days !== 14 || d.filters.family ? <Link className="btn ghost" href="/app/analytics">Clear</Link> : null}
          <span>Role family narrows discovery and resume fit. Application totals always include your full history.</span>
        </form>

        <section className="kpis" aria-label="Applications">
          <Kpi
            label="Applications"
            value={<ApplicationCount />}
            foot={`${a.with_posting} with a stored posting, ${a.without_posting} without`}
            href="/app/applications"
          />
          <Kpi label="Heard back" value={<ApplicationHeardBack />} foot={<ApplicationHeardBackFoot />} />
          <Kpi
            label="Interviews"
            value={<ApplicationStageCount statuses={["interviewing", "offer", "accepted"]} />}
            foot={<ApplicationInterviewFoot />}
          />
          <Kpi
            label={`Applied, last ${d.filters.days} days`}
            value={appliedRange.toLocaleString("en-US")}
            foot={a.undated ? `${a.undated} application${a.undated === 1 ? "" : "s"} have no date` : "Every application is dated"}
          />
        </section>

        <div className="cards-2 sect-gap">
          <section className="panel">
            <h3>Applied per day</h3>
            <p>Applications by the day you marked them, last {a.daily.length} days.</p>
            <DayColumns days={a.daily.map((x) => ({ date: x.date, n: x.applied }))} label="Applications per day" />
          </section>
          <section className="panel">
            <h3>By current status</h3>
            <p>
              ace keeps each application&rsquo;s current status, not its history, so one rejected after an interview counts as
              rejected. No reply is never counted as rejected.
            </p>
            <Bars
              rows={STATUS_ORDER.filter((st) => a.by_status[st]).map((st) => ({
                label: STATUS_LABEL[st],
                n: a.by_status[st] ?? 0,
                href: "/app/applications",
              }))}
              empty="No applications yet."
            />
          </section>
          <section className="panel">
            <h3>By role family</h3>
            <Bars
              rows={a.by_family.map((f) => ({
                label: f.family === "NOT_STORED" ? "No stored posting" : familyLabel(f.family),
                n: f.count,
                href: f.family === "NOT_STORED" ? "/app/applications" : `/app/applications?family=${f.family}`,
              }))}
              empty="No applications yet."
            />
          </section>
          <section className="panel">
            <h3>Most applied companies</h3>
            <Bars
              rows={a.top_companies.map((c) => ({ label: c.name, n: c.count, href: `/app/applications?company=${encodeURIComponent(c.name)}` }))}
              empty="No applications yet."
            />
          </section>
        </div>

        <div className="section-head">
          <h2>Discovery and resume fit</h2>
          <span className="section-sub">{d.total_open.toLocaleString("en-US")} open qualifying roles</span>
        </div>

        <section className="kpis" aria-label="Resume fit">
          {BANDS.map((k) => (
            <Kpi
              key={k}
              label={k === "unscored" ? "Not scored" : `${BAND_LABEL[k]} match`}
              value={d.scores[k].toLocaleString("en-US")}
              foot={`${pct(d.scores[k])}% of open roles`}
              tone={k === "high" && d.scores[k] ? "good" : undefined}
              href={k === "high" ? "/app/opportunities?view=matched" : "/app/opportunities?sort=best_match"}
            />
          ))}
        </section>

        <section className="panel sect-gap">
          <h3>By company tier</h3>
          <Legend t={d.thresholds} />
          <BreakdownTable
            rows={d.tiers.map((t) => ({
              key: t.tier,
              label: TIER_LABEL[t.tier] || "Other companies",
              href: t.tier === "OTHER" ? "/app/opportunities" : `/app/opportunities?tier=${t.tier}`,
              b: t,
            }))}
          />
        </section>

        <section className="panel sect-gap">
          <h3>By role family</h3>
          <BreakdownTable
            rows={d.families.map((f) => ({
              key: f.family,
              label: familyLabel(f.family),
              href: `/app/opportunities?family=${f.family}`,
              b: f,
            }))}
          />
        </section>

        <div className="sect-gap">
          <section className="panel">
            <h3>Qualifying roles found per day</h3>
            <p>
              First seen each day, last {d.daily.length} days: {foundRange.toLocaleString("en-US")} still open. Closed roles are
              not counted.
            </p>
            <DayColumns days={d.daily.map((x) => ({ date: x.date, n: x.found }))} label="Qualifying roles found per day" />
          </section>
        </div>

        <section className="panel sect-gap">
            <h3>Best fits by company</h3>
            <p>Companies ordered by their highest scoring open role for your resume.</p>
            <div className="db-table" role="table">
              <div className="db-tr db-th db-co" role="row">
                <span role="columnheader">Company</span>
                <span role="columnheader">Tier</span>
                <span role="columnheader">Open</span>
                <span role="columnheader">Best</span>
                <span role="columnheader">Applied</span>
              </div>
              {d.top_companies.map((c) => (
                <Link key={c.name} className="db-tr db-co" role="row" href={`/app/opportunities?company=${encodeURIComponent(c.name)}`}>
                  <span className="db-name" role="cell">{c.name}</span>
                  <span className="st-muted" role="cell">{TIER_LABEL[c.tier] || "Other"}</span>
                  <span className="db-num" role="cell">{c.open}</span>
                  <span className="db-num" role="cell">{c.best ?? "not scored"}</span>
                  <span className="db-num" role="cell">{c.applied}</span>
                </Link>
              ))}
            </div>
        </section>
      </div>
    </ScrollArea>
  );
}
