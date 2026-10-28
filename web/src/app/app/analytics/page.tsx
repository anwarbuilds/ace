import { AnalyticsRefresh } from "@/components/analytics/AnalyticsRefresh";
import { AnalyticsView } from "@/components/analytics/AnalyticsView";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import { getPrefs } from "@/lib/prefs";
import type { AnalyticsData, InboxConnection } from "@/lib/analytics";
import { readAnalyticsSupplement } from "@/lib/analyticsRead";
import "./analytics.css";

export const metadata = { title: "Analytics · ace" };
export default async function AnalyticsPage({ searchParams }: PageProps<"/app/analytics">) {
  const sp = await searchParams;
  const prefs = await getPrefs();
  const query: Record<string,string> = {};
  for (const key of ["days", "family", "start", "end", "tab", "company", "interval", "week"]) if (typeof sp[key] === "string") query[key] = sp[key];
  if (!query.days) query.days = query.start && query.end ? "custom" : "30";
  const params: Record<string,string> = {...query, tz:prefs.tz};
  delete params.tab;
  delete params.interval;
  delete params.week;
  const results = await Promise.allSettled([
    apiGetOr<AnalyticsData|null>("/api/analytics", null, params),
    apiGetOr<InboxConnection|null>("/api/inbox/connection", null),
  ]);
  const d = results[0].status === "fulfilled" ? results[0].value : null;
  const connection = results[1].status === "fulfilled" ? results[1].value : null;
  if (!d) return <div className="an-page"><h1>Analytics</h1><p role="alert">Analytics could not be loaded. Check the date range or reload to try again.</p><a className="btn" href="/app/analytics">Reset filters</a></div>;
  const tab = ["overview","outcomes","role-resume","companies"].includes(query.tab) ? query.tab : "overview";
  const interval = query.interval === "weekly" || query.interval === "monthly" ? query.interval : query.interval === "daily" ? "daily" : d.granularity === "monthly" ? "monthly" : "daily";
  const supplement = await readAnalyticsSupplement(d, interval, query.week);
  return <ScrollArea><AnalyticsRefresh/><AnalyticsView d={d} connection={connection} tab={tab} query={query} supplement={supplement}/></ScrollArea>;
}
