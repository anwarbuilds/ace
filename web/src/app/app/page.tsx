import Link from "next/link";

import { Avatar, ScoreRing } from "@/components/bits";
import { CardRow } from "@/components/browse/JobCard";
import type { CompanyRow } from "@/components/browse/CompanyDirectory";
import { Icon } from "@/components/Icon";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import { GROUPS, companyHref } from "@/lib/browse";
import { HIGH, STATUSES, STATUS_LABEL, TIER_LABEL, clean, clock, expFit, shortDate } from "@/lib/format";
import { getPrefs, getPrevVisit } from "@/lib/prefs";
import type { JobPage, MarkCounts, Stats, SystemStatus } from "@/lib/types";

export const metadata = { title: "Home · ace" };

const NO_JOBS: JobPage = { items: [], total: 0, limit: 0, offset: 0, has_more: false, sort: "", resume_id: null };

const ROWS = ["strong-matches", "new-grad", "big-tech", "machine-learning", "forward-deployed", "top-tier", "remote"];

function Tile({ n, label, href, tone }: { n: number | string; label: string; href: string; tone?: string }) {
  return (
    <Link className="stat stat-link" href={href}>
      <div className={`stat-n${tone ? ` ${tone}` : ""}`}>{n}</div>
      <div className="stat-l">{label}</div>
    </Link>
  );
}

// The home page, laid out like a shop front: one featured role, then a
// row per group, each leading to that group's own page.
export default async function HomePage() {
  const [{ tz }, prevVisit] = await Promise.all([getPrefs(), getPrevVisit()]);
  const groups = ROWS.map((slug) => GROUPS.find((g) => g.slug === slug)!);
  const [stats, marks, system, pick, fresh, companies, ...rows] = await Promise.all([
    apiGetOr<Stats>("/api/stats", { last_poll_at: null }),
    apiGetOr<MarkCounts | null>("/api/marks", null),
    apiGetOr<SystemStatus | null>("/api/system", null),
    apiGetOr<JobPage>("/api/jobs", NO_JOBS, {
      sort: "unapplied_first,new_grad_first,best_match",
      min_match: String(HIGH),
      limit: "1",
    }),
    apiGetOr<JobPage>("/api/jobs", NO_JOBS, {
      ...(prevVisit ? { since: prevVisit.toISOString() } : { max_detected_age_days: "1" }),
      sort: "newest",
      limit: "12",
    }),
    apiGetOr<{ items: CompanyRow[] }>("/api/companies", { items: [] }),
    ...groups.map((g) => apiGetOr<JobPage>("/api/jobs", NO_JOBS, { ...g.params, limit: "12" })),
  ]);
  const top = pick.items[0];
  const byStatus = marks?.by_status ?? {};
  const pipelineMax = Math.max(1, ...STATUSES.map((s) => byStatus[s] ?? 0));
  const alerts = system?.alerts;
  const alertLine = !alerts
    ? "Unknown"
    : !alerts.address_set
      ? "Off: no alert address set"
      : !alerts.provider_configured
        ? "Not delivered: no mail provider key"
        : alerts.last_sent_at
          ? `Last delivered ${shortDate(alerts.last_sent_at, tz)}, ${clock(alerts.last_sent_at, tz)}`
          : "Configured, nothing sent yet";
  const hiring = companies.items
    .filter((c) => c.open_roles > 0)
    .sort((a, b) => b.open_roles - a.open_roles)
    .slice(0, 12);

  return (
    <ScrollArea>
      <div className="page home">
        {top ? (
          <section className="hero" aria-label="Top pick for you">
            <div className="hero-txt">
              <p className="eyebrow">Top pick for you</p>
              <Link className="hero-co" href={companyHref(top.company)}>
                <Avatar name={top.company} />
                <span>{top.company}</span>
                {TIER_LABEL[top.company_tier] ? <span className="co-tier">{TIER_LABEL[top.company_tier]}</span> : null}
              </Link>
              <h1 className="hero-title">{clean(top.title)}</h1>
              <p className="hero-meta">
                {top.location}
                <span className={expFit(top).cls}>{expFit(top).text}</span>
              </p>
              {top.matched_skills.length ? (
                <div className="skills">
                  {top.matched_skills.slice(0, 8).map((k) => (
                    <span key={k} className="sk have">
                      {k}
                    </span>
                  ))}
                </div>
              ) : null}
              <div className="hero-acts">
                <Link className="btn btn-primary" href={`/app/jobs/${top.id}`}>
                  View role
                </Link>
                <a className="btn btn-secondary" href={top.official_url} target="_blank" rel="noopener noreferrer">
                  Official posting
                  <Icon name="ext" />
                </a>
                <Link className="btn btn-secondary" href={`/app/resume-studio/check?job=${top.id}`}>
                  Check my resume
                </Link>
              </div>
            </div>
            <div className="hero-ring">
              <ScoreRing score={top.match_score} />
              <span className="why">match with your resume</span>
            </div>
          </section>
        ) : null}

        <div className="cards3 sect">
          <Tile
            n={fresh.total}
            label={prevVisit ? `New since ${clock(prevVisit, tz)}` : "New today"}
            href={prevVisit ? "/app/opportunities?view=new" : "/app/browse/new-today"}
          />
          <Tile n={stats.match_high ?? 0} label="Strong matches" href="/app/browse/strong-matches" tone="m-high" />
          <Tile n={stats.labelled_new_grad ?? 0} label="New grad roles open" href="/app/browse/new-grad" />
          <Tile n={marks?.open_applications ?? 0} label="Applications in progress" href="/app/applications" />
        </div>

        <CardRow
          title={prevVisit ? "New since your last visit" : "New today"}
          href={prevVisit ? "/app/opportunities?view=new" : "/app/browse/new-today"}
          count={fresh.total}
          jobs={fresh.items}
          empty="Nothing new yet. ace checks every board continuously."
        />
        {groups.map((g, i) => (
          <CardRow key={g.slug} title={g.title} href={`/app/browse/${g.slug}`} count={rows[i].total} jobs={rows[i].items} />
        ))}

        {hiring.length ? (
          <section className="row-sec">
            <div className="row-head">
              <h2 className="row-title">
                <Link href="/app/companies">Companies hiring for you</Link>
              </h2>
              <span className="spacer" />
              <Link className="row-all" href="/app/companies">
                See all
              </Link>
            </div>
            <div className="row-track">
              {hiring.map((c) => (
                <Link key={c.name} className="co-card" href={companyHref(c.name)}>
                  <Avatar name={c.name} large />
                  <span className="co-card-n">{c.name}</span>
                  <span className="co-tier">{TIER_LABEL[c.tier] || "\u00a0"}</span>
                  <span className="co-card-s">
                    {c.open_roles} open role{c.open_roles === 1 ? "" : "s"}
                  </span>
                </Link>
              ))}
            </div>
          </section>
        ) : null}

        <div className="ov-grid">
              <div className="card">
                <p className="eyebrow">Where your applications stand</p>
                <div className="bars">
                  {STATUSES.map((s) => (
                    <Link key={s} className="bar bar-link" href={`/app/applications`}>
                      <span>{STATUS_LABEL[s]}</span>
                      <span className="bar-t">
                        <span
                          className={`bar-f${s === "offer" || s === "accepted" ? " gold" : ""}`}
                          style={{ width: `${Math.round(((byStatus[s] ?? 0) / pipelineMax) * 100)}%` }}
                        />
                      </span>
                      <span className="bar-n">{byStatus[s] ?? 0}</span>
                    </Link>
                  ))}
                </div>
              </div>
              <div className="card">
                <p className="eyebrow">ace itself</p>
                <dl className="kv">
                  <dt>Discovery</dt>
                  <dd>
                    {system?.scheduler.stale ? "Not updating" : "Live"}
                    {system?.scheduler.last_poll_at
                      ? `, last check ${clock(system.scheduler.last_poll_at, tz)}`
                      : ""}
                  </dd>
                  <dt>Boards watched</dt>
                  <dd>{system?.scheduler.sources_enabled ?? "unknown"}</dd>
                  <dt>Scored</dt>
                  <dd>
                    {system
                      ? system.scoring.resume_active
                        ? `${system.scoring.queue_jobs - system.scoring.queue_unscored} of ${system.scoring.queue_jobs} open roles`
                        : "No resume uploaded"
                      : "unknown"}
                  </dd>
                  <dt>Email alerts</dt>
                  <dd>{alertLine}</dd>
                </dl>
                <div className="ov-actions">
                  <Link className="btn btn-secondary btn-sm" href="/app/activity">
                    Discovery activity
                  </Link>
                  <Link className="btn btn-secondary btn-sm" href="/app/coverage">
                    Coverage
                  </Link>
                </div>
              </div>
            </div>
      </div>
    </ScrollArea>
  );
}
