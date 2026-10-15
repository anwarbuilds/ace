import { LiveChip } from "@/components/shell/Live";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { PullsAlerts, PullsLog } from "@/components/pulls/PullsLog";
import { apiGetOr } from "@/lib/api";
import { ago } from "@/lib/format";
import type { Facets, PullsResponse, Stats } from "@/lib/types";

export const metadata = { title: "Pulls · ace" };

// Home: what every check found, newest first. The page the owner opens
// every 15 minutes, so it loads three cheap reads and nothing else.

const SOURCE_LABEL: Record<string, string> = {
  greenhouse: "Greenhouse",
  ashby: "Ashby",
  lever: "Lever",
  workday: "Workday",
  smartrecruiters: "SmartRecruiters",
  amazon: "Amazon",
  simplify: "Simplify",
  eightfold: "Eightfold",
  eightfold_pcsx: "Eightfold (PCS)",
};

function Stat({ k, v, bad = false }: { k: string; v: string; bad?: boolean }) {
  return (
    <div className="pl-stat">
      <span className="pl-k">{k}</span>
      <span className={`pl-v${bad ? " bad" : ""}`} suppressHydrationWarning>
        {v}
      </span>
    </div>
  );
}

// Every check gets a row, including the ones that found nothing: this
// is a log, and a log that hides its quiet entries cannot answer "was
// ace running at 3am".
export default async function HomePullsPage() {
  const [pulls, stats, facets] = await Promise.all([
    apiGetOr<PullsResponse>("/api/sessions", { last_poll_at: null, sessions: [] }, { limit: "30", jobs_per_session: "6" }),
    apiGetOr<Stats>("/api/stats", { last_poll_at: null }),
    apiGetOr<Facets | null>("/api/facets", null),
  ]);
  const elapsed = stats.last_poll_at ? ago(stats.last_poll_at) : "";
  const since = !stats.last_poll_at ? "not recorded" : elapsed === "just now" ? elapsed : `${elapsed} ago`;
  const sick =
    stats.sources_enabled != null && stats.sources_polled != null && stats.sources_polled < stats.sources_enabled;
  const sources = (facets?.sources ?? []).slice().sort((a, b) => b.count - a.count);
  const total = sources.reduce((a, b) => a + b.count, 0);

  return (
    <>
      <div className="head">
        <div className="head-row">
          <h1 className="h1">Pulls</h1>
          <span className="spacer" />
          <LiveChip />
        </div>
        <div className="controls">
          <div className="pl-stats">
            <Stat k="Last check" v={since} />
            <Stat
              k="Sources polling"
              v={stats.sources_polled != null && stats.sources_enabled ? `${stats.sources_polled} of ${stats.sources_enabled}` : "unknown"}
              bad={sick}
            />
            <Stat
              k="Jobs in queue"
              v={stats.qualifying_active_jobs != null ? stats.qualifying_active_jobs.toLocaleString("en-US") : "none"}
            />
            <PullsAlerts />
          </div>
        </div>
      </div>
      <ScrollArea list>
        <div className="pl-layout">
          <div className="pl-wrap">
            <PullsLog initial={pulls.sessions} />
          </div>
          <aside className="pl-side">
            <h3 className="pl-side-t">Where your queue comes from</h3>
            {total ? (
              <div className="pl-side-list">
                {sources.map((s) => (
                  <div className="pl-side-row" key={s.value}>
                    <span className="pl-side-name">{SOURCE_LABEL[s.value] ?? s.value}</span>
                    <span className="pl-side-bar">
                      <span className="pl-side-fill" style={{ width: `${Math.round((100 * s.count) / total)}%` }} />
                    </span>
                    <span className="pl-side-n">{s.count.toLocaleString("en-US")}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="why">Nothing qualifying yet.</p>
            )}
          </aside>
        </div>
      </ScrollArea>
    </>
  );
}
