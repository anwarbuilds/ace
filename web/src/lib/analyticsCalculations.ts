import type { AnalyticsData } from "./analytics";

export type Interval = "daily" | "weekly" | "monthly";
export interface SubmissionIdentity { key: string; applied_at: string | null }
export interface ChartPoint { date: string; end: string; count: number }
export interface SubmissionTrend {
  current: number; previous: number; percent: number | null; label: string; description: string;
}
export interface AnalyticsSupplement {
  timeline: ChartPoint[]; interval: Interval; week: ChartPoint[];
  weekStart: string; weekEnd: string; currentWeek: boolean;
  submissionTrend: SubmissionTrend | null; weekTrend: SubmissionTrend | null;
}
const DAY = 86_400_000;
const dateFormats = new Map<string, Intl.DateTimeFormat>();
const clockFormats = new Map<string, Intl.DateTimeFormat>();
const utcStamp = (stamp: string) => /(?:Z|[+-]\d{2}:\d{2})$/i.test(stamp) ? stamp : `${stamp}Z`;
// Calendar dates use UTC arithmetic, then match dates formatted in the
// report's IANA zone. A calendar day is not 24 elapsed hours across DST.
export function shiftDate(day: string, amount: number): string {
  return new Date(Date.parse(`${day}T00:00:00Z`) + amount * DAY).toISOString().slice(0, 10);
}
export function mondayOf(day: string): string {
  return shiftDate(day, -((new Date(`${day}T00:00:00Z`).getUTCDay() + 6) % 7));
}
export function localDate(stamp: string, timezone: string): string {
  let formatter = dateFormats.get(timezone);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" });
    dateFormats.set(timezone, formatter);
  }
  return formatter.format(new Date(utcStamp(stamp)));
}
function civilTime(stamp: string, timezone: string): number {
  let formatter = clockFormats.get(timezone);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat("en-US", {
      timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
    });
    clockFormats.set(timezone, formatter);
  }
  const parts = formatter.formatToParts(new Date(utcStamp(stamp)));
  const p = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second);
}
export function groupSubmissions(daily: { date: string; count: number }[], interval: Interval, start: string, end: string): ChartPoint[] {
  const grouped = new Map<string, ChartPoint>();
  for (const row of daily) {
    const anchor = interval === "weekly" ? mondayOf(row.date) : interval === "monthly" ? `${row.date.slice(0, 7)}-01` : row.date;
    const last = interval === "weekly" ? shiftDate(anchor, 6) : interval === "monthly"
      ? shiftDate(new Date(Date.UTC(+anchor.slice(0, 4), +anchor.slice(5, 7), 1)).toISOString().slice(0, 10), -1) : anchor;
    const date = anchor < start ? start : anchor;
    const point = grouped.get(date) ?? { date, end: last > end ? end : last, count: 0 };
    point.count += row.count;
    grouped.set(date, point);
  }
  return [...grouped.values()];
}
export function compareCounts(current: number, previous: number, description: string): SubmissionTrend {
  const percent = previous ? (current - previous) / previous * 100 : null;
  return { current, previous, percent, description,
    label: percent === null ? current ? "New" : "No prior activity" : `${percent > 0 ? "+" : ""}${Math.round(percent)}%` };
}

/** Adds finer detail only when the complete identity read reconciles with
 * the primary projection. Outcome trends require observation coverage the
 * existing API cannot attest; no outcome comparison is manufactured here.
 */
export function calculateSupplement(d: AnalyticsData, identities: SubmissionIdentity[], interval: Interval, askedWeek?: string): AnalyticsSupplement | null {
  if (new Set(identities.map(row => row.key)).size !== identities.length) return null;
  const today = localDate(d.as_of, d.timezone), currentMonday = mondayOf(today);
  const validWeek = askedWeek && /^\d{4}-\d{2}-\d{2}$/.test(askedWeek) && !Number.isNaN(Date.parse(`${askedWeek}T00:00:00Z`))
    && new Date(`${askedWeek}T00:00:00Z`).toISOString().slice(0, 10) === askedWeek && askedWeek <= today;
  const weekStart = validWeek ? mondayOf(askedWeek) : currentMonday, weekEnd = shiftDate(weekStart, 6);
  const daily = new Map<string, number>(), instants: number[] = [];
  let selected = 0;
  for (const row of identities) {
    if (!row.applied_at) { if (d.days === "all") selected++; continue; }
    if (Number.isNaN(Date.parse(utcStamp(row.applied_at)))) return null;
    const day = localDate(row.applied_at, d.timezone);
    daily.set(day, (daily.get(day) ?? 0) + 1);
    instants.push(civilTime(row.applied_at, d.timezone));
    if (day >= d.start && day <= d.end) selected++;
  }
  if (selected !== d.submitted) return null;
  const series: { date: string; count: number }[] = [];
  for (let date = d.start; date <= d.end; date = shiftDate(date, 1)) series.push({ date, count: daily.get(date) ?? 0 });
  const now = civilTime(d.as_of, d.timezone);
  const count = (start: number, end: number) => instants.filter(stamp => stamp >= start && stamp < end).length;
  const midnight = (day: string) => Date.parse(`${day}T00:00:00Z`);
  const start = midnight(d.start), end = midnight(shiftDate(d.end, 1)), span = end - start;
  const currentEnd = Math.min(now + 1, end), current = count(start, currentEnd);
  const submissionTrend = d.days === "all" || current !== d.submitted ? null : compareCounts(current, count(start - span, currentEnd - span),
    `Compared with ${shiftDate(d.start, -span / DAY)} through ${shiftDate(d.end, -span / DAY)} in ${d.timezone}, using the same local time on the final day. Submission counts, not response effectiveness.`);
  const weekCurrent = count(midnight(currentMonday), now + 1);
  return {
    timeline: groupSubmissions(series, interval, d.start, d.end), interval,
    week: Array.from({ length: 7 }, (_, i) => { const date = shiftDate(weekStart, i); return { date, end: date, count: date > today ? 0 : daily.get(date) ?? 0 }; }),
    weekStart, weekEnd, currentWeek: weekStart === currentMonday, submissionTrend,
    weekTrend: weekCurrent === d.week_total ? compareCounts(weekCurrent, count(midnight(shiftDate(currentMonday, -7)), now + 1 - 7 * DAY),
      `Current Monday through the report's local weekday and time, compared with the same elapsed part of the preceding week in ${d.timezone}.`) : null,
  };
}
