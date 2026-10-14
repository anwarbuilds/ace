import Link from "next/link";

import { JobTable } from "@/components/jobs/JobTable";
import { LiveChip } from "@/components/shell/Live";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import { HIGH, STATUSES, STATUS_LABEL, clock, shortDate } from "@/lib/format";
import { getPrefs, getPrevVisit } from "@/lib/prefs";
import type { JobPage, MarkCounts, Stats, SystemStatus } from "@/lib/types";

export const metadata = { title: "Overview · ace" };

const NO_JOBS: JobPage = { items: [], total: 0, limit: 0, offset: 0, has_more: false, sort: "", resume_id: null };

function Tile({ n, label, href, tone }: { n: number | string; label: string; href?: string; tone?: string }) {
  const body = (
    <>
      <div className={`stat-n${tone ? ` ${tone}` : ""}`}>{n}</div>
      <div className="stat-l">{label}</div>
    </>
  );
  return href ? (
    <Link className="stat stat-link" href={href}>
      {body}
    </Link>
  ) : (
    <div className="stat">{body}</div>
  );
}

// What to look at first today: new arrivals, the strongest new grad
// matches not yet applied to, where applications stand, and whether ace
// itself is healthy. Every number links to the list it counts.
export default async function OverviewPage() {
  const [{ tz }, prevVisit] = await Promise.all([getPrefs(), getPrevVisit()]);
  const [stats, marks, system, priority, fresh] = await Promise.all([
    apiGetOr<Stats>("/api/stats", { last_poll_at: null }),
    apiGetOr<MarkCounts | null>("/api/marks", null),
    apiGetOr<SystemStatus | null>("/api/system", null),
    apiGetOr<JobPage>("/api/jobs", NO_JOBS, {
      sort: "unapplied_first,new_grad_first,best_match",
      min_match: String(HIGH),
      limit: "6",
    }),
    prevVisit
      ? apiGetOr<JobPage>("/api/jobs", NO_JOBS, { since: prevVisit.toISOString(), limit: "1" })
      : Promise.resolve(NO_JOBS),
  ]);
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

  return (
    <>
      <div className="head">
        <div className="head-row">
          <h1 className="h1">Overview</h1>
          <span className="spacer" />
          <LiveChip />
        </div>
      </div>
      <ScrollArea>
        <div className="page">
          <div className="wrap">
            <div className="cards3 sect">
              <Tile
                n={fresh.total}
                label={prevVisit ? `New since ${clock(prevVisit, tz)}` : "New since your last visit"}
                href="/app/opportunities?view=new"
              />
              <Tile n={stats.match_high ?? 0} label="Strong matches" href="/app/opportunities?view=matched" tone="m-high" />
              <Tile n={stats.labelled_new_grad ?? 0} label="New grad roles open" href="/app/opportunities?newgrad=1" />
              <Tile n={marks?.open_applications ?? 0} label="Applications in progress" href="/app/applications" />
            </div>

            <div className="sect">
              <div className="ov-h">
                <p className="eyebrow">Strong matches you have not applied to</p>
                <Link className="link-btn" href="/app/opportunities?view=matched">
                  See all
                </Link>
              </div>
              {priority.items.length ? (
                <div className="ov-list">
                  <JobTable
                    items={priority.items}
                    total={priority.items.length}
                    offset={0}
                    page="overview"
                    sorts={[]}
                    group={false}
                    emptyState={null}
                    sortLinks={{}}
                    bare
                  />
                </div>
              ) : (
                <p className="why">
                  No strong matches right now. Strong means 70 or more against your resume; it orders the list and
                  never hides a role.
                </p>
              )}
            </div>

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
        </div>
      </ScrollArea>
    </>
  );
}
