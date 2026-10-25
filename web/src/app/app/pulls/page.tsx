import Link from "next/link";

import { ApplicationMetric } from "@/components/applications/ApplicationCount";
import { PullsAlerts } from "@/components/pulls/PullsLog";
import { PullsTimeline } from "@/components/pulls/PullsTimeline";
import { PullsCalendar } from "@/components/pulls/PullsCalendar";
import { NavIcon } from "@/components/shell/NavIcon";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import { calendarDay, clock, zoneName } from "@/lib/format";
import { getPrefs } from "@/lib/prefs";
import type { PullFilter, PullsPage } from "@/lib/types";

export const metadata = { title: "Pulls · ace" };

const FILTERS: { key: PullFilter; label: string }[] = [
  { key: "all", label: "All activity" },
  { key: "opportunities", label: "With opportunities" },
  { key: "quiet", label: "Quiet checks" },
];

const STATE_TEXT = {
  live: { title: "Actively monitoring", value: "Healthy" },
  delayed: { title: "Checks are running late", value: "Delayed" },
  stalled: { title: "ace has stopped checking", value: "Stalled" },
  unknown: { title: "No check recorded yet", value: "Unknown" },
} as const;

function n(value: number): string {
  return value.toLocaleString("en-US");
}

function Kpi({ label, value, foot, tone }: { label: string; value: string; foot: string; tone?: "good" | "warn" | "bad" }) {
  return (
    <div className="kpi">
      <div className="kpi-l">{label}</div>
      <div className="kpi-n">{value}</div>
      <div className={`kpi-f${tone ? ` ${tone}` : ""}`}>{foot}</div>
    </div>
  );
}

// Home. Every quarter hour in which ace read anything is one window,
// quiet ones included: a log that hides its quiet entries cannot answer
// "was ace running at 3am". One request: /api/pulls.
export default async function PullsPageRoute({ searchParams }: PageProps<"/app/pulls">) {
  const sp = await searchParams;
  const prefs = await getPrefs();
  const filter: PullFilter = sp.filter === "opportunities" || sp.filter === "quiet" ? sp.filter : "all";
  const date = typeof sp.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(sp.date) ? sp.date : null;
  const params: Record<string, string> = { tz: prefs.tz, filter };
  if (date) params.date = date;
  const data = await apiGetOr<PullsPage | null>("/api/pulls", null, params);

  if (!data) {
    return (
      <div className="pg">
        <div className="page-hero">
          <div>
            <div className="eyebrow">Your daily starting point</div>
            <h1 className="h1">Pulls</h1>
            <p className="subtitle">The activity log could not be loaded. Check that the API is running, then reload.</p>
          </div>
        </div>
      </div>
    );
  }

  const { status, summary, day } = data;
  const text = STATE_TEXT[status.state];
  const isToday = data.date === data.today;
  const href = (next: Record<string, string | null>) => {
    const q = new URLSearchParams();
    const merged = { date: isToday ? null : data.date, filter: filter === "all" ? null : filter, ...next };
    for (const [k, v] of Object.entries(merged)) if (v) q.set(k, v);
    const s = q.toString();
    return s ? `/app/pulls?${s}` : "/app/pulls";
  };
  const zone = zoneName(status.last_success_at ?? summary.window_end, prefs.tz);
  const latest = data.buckets.find((b) => b.new_qualifying > 0) ?? null;

  return (
    <ScrollArea list>
      <div className="pg">
      <div className="page-hero">
        <div>
          <div className="eyebrow">Your daily starting point</div>
          <h1 className="h1">Pulls</h1>
          <p className="subtitle">Fresh opportunities, grouped into transparent 15-minute discovery windows.</p>
        </div>
        <div className="btns">
          {latest && isToday ? (
            <a className="btn" href={`#pull-${latest.id}`}>
              <NavIcon name="pulls" size="sm" /> Latest pull
            </a>
          ) : null}
          <Link className="btn primary" href="/app/opportunities">
            View all opportunities <NavIcon name="right" size="sm" />
          </Link>
        </div>
      </div>

      <div className="company-first-note"><strong>Company first. Relevant role second.</strong> Scan employers first, then review the matched role and verified sponsorship history in context.</div>

      <section className="kpis" aria-label="Last 24 hours">
        <Kpi label="Newly detected postings" value={n(summary.new_postings)} foot="First seen in the last 24 hours" />
        <Kpi
          label="New qualifying opportunities"
          value={n(summary.new_qualifying)}
          foot={latest && isToday ? `${n(latest.new_qualifying)} in the latest window with any` : "Passed your filters, last 24 hours"}
          tone={summary.new_qualifying ? "good" : undefined}
        />
        <Kpi
          label="Sources polling"
          value={n(status.sources_polled)}
          foot={`of ${n(status.sources_enabled)} enabled. ${n(summary.sources_succeeded)} answered in the last 24 hours`}
          tone={status.sources_polled < status.sources_enabled ? "warn" : undefined}
        />
        <ApplicationMetric />
      </section>

      <div className="pull-grid">
        <div>
          <div className="section-head">
            <h2>{isToday ? "Recent activity" : calendarDay(data.date)}</h2>
            <span className="section-sub">
              {isToday ? "Today" : "Earlier"} · times in {zone || prefs.tz}
            </span>
          </div>
          <div className="pull-tools">
            <div className="chip-row" role="group" aria-label="Show">
              {FILTERS.map((f) => (
                <Link
                  key={f.key}
                  className={`filterchip${filter === f.key ? " on" : ""}`}
                  href={href({ filter: f.key === "all" ? null : f.key })}
                  aria-current={filter === f.key ? "true" : undefined}
                  scroll={false}
                >
                  {f.label}
                  <span className="fc-n">{n(day.counts[f.key] ?? 0)}</span>
                </Link>
              ))}
            </div>
            <nav className="day-nav" aria-label="Day">
              {data.prev_date ? (
                <Link className="btn ghost" href={href({ date: data.prev_date })} scroll={false}>
                  <NavIcon name="left" size="sm" /> {calendarDay(data.prev_date)}
                </Link>
              ) : null}
              {data.next_date ? (
                <Link
                  className="btn ghost"
                  href={href({ date: data.next_date === data.today ? null : data.next_date })}
                  scroll={false}
                >
                  {data.next_date === data.today ? "Today" : calendarDay(data.next_date)} <NavIcon name="right" size="sm" />
                </Link>
              ) : null}
            </nav>
          </div>
          <PullsTimeline
            key={`${data.date}:${filter}`}
            buckets={data.buckets}
            tz={prefs.tz}
            filter={filter}
            isToday={isToday}
            date={data.date}
          />
        </div>

        <aside className="pull-rail">
          <PullsCalendar key={data.date} date={data.date} today={data.today} filter={filter} />
          <div className={`panel status-panel s-${status.state}`}>
            <div className="tiny-label">
              <NavIcon name="pulls" size="sm" /> Discovery status
            </div>
            <h3>{text.title}</h3>
            <p>
              ace checks each source continuously on its own interval. The 15-minute windows organise what was found; they
              do not decide when a source is polled.
            </p>
            <div className="lineitem">
              <span>Scheduler</span>
              <strong className={`st-${status.state}`}>{text.value}</strong>
            </div>
            <div className="lineitem">
              <span>Last successful check</span>
              <strong>{status.last_success_at ? `${clock(status.last_success_at, prefs.tz)} ${zone}` : "None"}</strong>
            </div>
            <div className="lineitem">
              <span>Sources enabled</span>
              <strong>{n(status.sources_enabled)}</strong>
            </div>
            <div className="lineitem">
              <span>Windows with failures, 24 h</span>
              <strong>
                {summary.windows_with_failures == null
                  ? "Not recorded"
                  : `${n(summary.windows_with_failures)} of ${n(summary.windows)}`}
              </strong>
            </div>
          </div>

          <div className="panel">
            <h3>{isToday ? "Today at a glance" : `${calendarDay(data.date)} at a glance`}</h3>
            <div className="lineitem">
              <span>Windows recorded</span>
              <strong>{n(day.counts.all)}</strong>
            </div>
            <div className="lineitem">
              <span>With opportunities</span>
              <strong>{n(day.counts.opportunities)}</strong>
            </div>
            <div className="lineitem">
              <span>New postings</span>
              <strong>{n(day.new_postings)}</strong>
            </div>
            <div className="lineitem">
              <span>Passed your filters</span>
              <strong>{n(day.new_qualifying)}</strong>
            </div>
            <Link className="btn wide" href="/app/analytics">
              Open analytics <NavIcon name="right" size="sm" />
            </Link>
          </div>

          <div className="panel">
            <h3>What the numbers mean</h3>
            <p className="quiet-note">
              <b>Sources polling</b> counts enabled boards with poll history. <b>Boards read</b> counts successful
              boards once per window. <b>Attempted</b> and <b>failed</b> can both include a board that later recovered.
              <b>Postings observed</b> is what the
              boards held, mostly seen before; <b>new</b> is first seen in that window.
            </p>
            <div className="alerts-row">
              <PullsAlerts />
            </div>
          </div>
        </aside>
      </div>
      </div>
    </ScrollArea>
  );
}
