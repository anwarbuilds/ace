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
  currentWeekTotal: number;
  weekToday: string;
}
export const ANALYTICS_WEEK_TIMEZONE = "America/Los_Angeles";
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
export function calendarWeek(today: string, requested?: string) {
  const valid = requested && /^\d{4}-\d{2}-\d{2}$/.test(requested) && !Number.isNaN(Date.parse(`${requested}T00:00:00Z`))
    && new Date(`${requested}T00:00:00Z`).toISOString().slice(0, 10) === requested && requested <= today;
  const start = valid ? mondayOf(requested) : mondayOf(today);
  return { start, end: shiftDate(start, 6), current: start === mondayOf(today) };
}
/** Separate range mark lets the existing punctuation guard retain date ranges. */
export function weekDateLabels(start: string, end: string) {
  const format = (day: string, year: boolean) => new Date(`${day}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short", day: "numeric", ...(year ? { year: "numeric" } : {}), timeZone: "UTC",
  });
  return { start: format(start, start.slice(0, 4) !== end.slice(0, 4)), end: format(end, true) };
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
export function calculateSupplement(d: AnalyticsData, identities: SubmissionIdentity[], interval: Interval, askedWeek?: string, weeklyReport: AnalyticsData = d): AnalyticsSupplement | null {
  if (new Set(identities.map(row => row.key)).size !== identities.length) return null;
  if (weeklyReport.timezone !== ANALYTICS_WEEK_TIMEZONE) return null;
  const today = localDate(weeklyReport.as_of, ANALYTICS_WEEK_TIMEZONE), currentMonday = mondayOf(today);
  const window = calendarWeek(today, askedWeek), weekStart = window.start, weekEnd = window.end;
  const daily = new Map<string, number>(), weeklyDaily = new Map<string, number>(), instants: number[] = [], weeklyInstants: number[] = [];
  let selected = 0;
  for (const row of identities) {
    if (!row.applied_at) { if (d.days === "all") selected++; continue; }
    if (Number.isNaN(Date.parse(utcStamp(row.applied_at)))) return null;
    const day = localDate(row.applied_at, d.timezone);
    daily.set(day, (daily.get(day) ?? 0) + 1);
    instants.push(civilTime(row.applied_at, d.timezone));
    if (Date.parse(utcStamp(row.applied_at)) <= Date.parse(utcStamp(weeklyReport.as_of))) {
      const weekDay = localDate(row.applied_at, ANALYTICS_WEEK_TIMEZONE);
      weeklyDaily.set(weekDay, (weeklyDaily.get(weekDay) ?? 0) + 1);
      weeklyInstants.push(civilTime(row.applied_at, ANALYTICS_WEEK_TIMEZONE));
    }
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
  const weekNow = civilTime(weeklyReport.as_of, ANALYTICS_WEEK_TIMEZONE);
  const weekCount = (start: number, end: number) => weeklyInstants.filter(stamp => stamp >= start && stamp < end).length;
  const weekCurrent = weekCount(midnight(currentMonday), weekNow + 1);
  if (weekCurrent !== weeklyReport.week_total || weeklyReport.week?.some(row => (weeklyDaily.get(row.date) ?? 0) !== row.count)) return null;
  return {
    timeline: groupSubmissions(series, interval, d.start, d.end), interval,
    week: Array.from({ length: 7 }, (_, i) => { const date = shiftDate(weekStart, i); return { date, end: date, count: date > today ? 0 : weeklyDaily.get(date) ?? 0 }; }),
    weekStart, weekEnd, currentWeek: weekStart === currentMonday, submissionTrend,
    currentWeekTotal: weekCurrent,
    weekToday: today,
    weekTrend: compareCounts(weekCurrent, weekCount(midnight(shiftDate(currentMonday, -7)), weekNow + 1 - 7 * DAY),
      `Current Monday through the report's local weekday and time, compared with the same elapsed part of the preceding week in ${ANALYTICS_WEEK_TIMEZONE}.`),
  };
}
