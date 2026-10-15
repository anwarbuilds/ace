import Link from "next/link";

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
          <span className="db-name">{r.label}</span>
          <span className="db-num">{r.b.open}</span>
          <span className="db-num">{r.b.applied}</span>
          {r.b.open ? <ScoreBar b={r.b} /> : <span className="st-muted">none open</span>}
          <span className="db-num">{r.b.high}</span>
        </Link>
      ))}
    </div>
  );
}

export default async function DashboardPage() {
  const d = await apiGetOr<Dashboard | null>("/api/dashboard", null);
  if (!d) {
    return (
      <div className="page">
        <p className="why">The dashboard could not be loaded.</p>
      </div>
    );
  }
  const maxDay = Math.max(1, ...d.daily.map((x) => x.found));
  const apps = Object.entries(d.applications) as [ApplicationStatus, number][];
  const maxApp = Math.max(1, ...apps.map(([, n]) => n));
  const pct = (n: number) => (d.total_open ? Math.round((100 * n) / d.total_open) : 0);

  return (
    <>
      <div className="head">
        <div className="head-row">
          <h1 className="h1">Analytics</h1>
          <span className="h1-count">{d.total_open.toLocaleString("en-US")} open roles</span>
        </div>
        <p className="why" style={{ margin: "6px 0 0" }}>
          {d.resume ? `Scored against ${d.resume.label}.` : "No resume is used for matching yet."} Every row opens the
          roles behind it.
        </p>
      </div>
      <ScrollArea>
        <div className="page">
          <div className="cards3 sect">
            {BANDS.map((k) => (
              <Link
                key={k}
                className="stat stat-link"
                href={k === "high" ? "/app/opportunities?view=matched" : "/app/opportunities?sort=best_match"}
              >
                <div className={`stat-n${k === "high" ? " m-high" : ""}`}>{d.scores[k]}</div>
                <div className="stat-l">
                  {k === "unscored" ? "Not scored" : `${BAND_LABEL[k]} match`}, {pct(d.scores[k])}%
                </div>
              </Link>
            ))}
          </div>

          <section className="sect">
            <h2 className="row-title">By company tier</h2>
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

          <section className="sect">
            <h2 className="row-title">By role family</h2>
            <BreakdownTable
              rows={d.families.map((f) => ({
                key: f.family,
                label: familyLabel(f.family),
                href: `/app/opportunities?family=${f.family}`,
                b: f,
              }))}
            />
          </section>

          <div className="db-grid">
            <section className="card db-card">
              <h2 className="row-title">Found per day</h2>
              <p className="why" style={{ margin: "2px 0 14px" }}>
                Qualifying roles ace first saw each day, last {d.daily.length} days.
              </p>
              <div className="db-days" role="img" aria-label="Qualifying roles found per day">
                {d.daily.map((x) => (
                  <span key={x.date} className="db-day" title={`${x.date}: ${x.found}`}>
                    <span className="db-day-bar" style={{ height: x.found ? `${Math.max(8, (x.found / maxDay) * 100)}%` : 0 }} />
                    <span className="db-day-l">{new Date(`${x.date}T12:00:00`).getDate()}</span>
                  </span>
                ))}
              </div>
            </section>

            <section className="card db-card">
              <h2 className="row-title">Applications by status</h2>
              <div className="bars" style={{ marginTop: 14 }}>
                {apps.length ? (
                  apps
                    .sort((a, b) => b[1] - a[1])
                    .map(([s, n]) => (
                      <Link key={s} className="bar bar-link" href="/app/applications" title={`${STATUS_LABEL[s] ?? s}: ${n}`}>
                        <span>{STATUS_LABEL[s] ?? s}</span>
                        <span className="bar-t">
                          <span className="bar-f" style={{ width: `${Math.round((n / maxApp) * 100)}%` }} />
                        </span>
                        <span className="bar-n">{n}</span>
                      </Link>
                    ))
                ) : (
                  <p className="why">No applications yet.</p>
                )}
              </div>
            </section>
          </div>

          <section className="sect">
            <h2 className="row-title">Best fits by company</h2>
            <p className="why" style={{ margin: "2px 0 12px" }}>
              Companies ordered by their highest scoring open role for your resume.
            </p>
            <div className="db-table" role="table">
              <div className="db-tr db-th db-co" role="row">
                <span role="columnheader">Company</span>
                <span role="columnheader">Tier</span>
                <span role="columnheader">Open</span>
                <span role="columnheader">Best score</span>
                <span role="columnheader">Applied</span>
              </div>
              {d.top_companies.map((c) => (
                <Link
                  key={c.name}
                  className="db-tr db-co"
                  role="row"
                  href={`/app/opportunities?company=${encodeURIComponent(c.name)}`}
                >
                  <span className="db-name">{c.name}</span>
                  <span className="st-muted">{TIER_LABEL[c.tier] || "Other"}</span>
                  <span className="db-num">{c.open}</span>
                  <span className="db-num">{c.best ?? "not scored"}</span>
                  <span className="db-num">{c.applied}</span>
                </Link>
              ))}
            </div>
          </section>
        </div>
      </ScrollArea>
    </>
  );
}
