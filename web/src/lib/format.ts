// Formatting shared by server and client components. Ported from the
// helpers in backend/app/api/static/index.html, with the time zone made
// explicit: the server renders these, so "which day was this" has to be
// asked in the reader's zone, not the container's (UTC).

import type { ApplicationStatus, Job, Tier } from "./types";

export const HIGH = 70;
export const MED = 45;
export const PAGE_SIZE = 50;

export const TIER_LABEL: Record<Tier, string> = {
  BIG_TECH: "Big tech",
  TOP_TIER: "Top tier",
  ESTABLISHED: "Established",
  OTHER: "",
};

export const STATUSES: ApplicationStatus[] = [
  "applied",
  "screening",
  "interviewing",
  "offer",
  "accepted",
  "rejected",
  "withdrawn",
  "ghosted",
];

export const STATUS_LABEL: Record<ApplicationStatus, string> = {
  applied: "Applied",
  screening: "Screening",
  interviewing: "Interviewing",
  offer: "Offer",
  accepted: "Accepted",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  ghosted: "No reply",
};

// A dash the user never sees: em dash, horizontal bar, or an en dash
// with spaces around it (which reads as one). "2–4 years" keeps its
// unspaced en dash, because that is a range, not a dash.
const DASH = /\s*(?:[—―]+|\s–\s)\s*/g;

/** Replace any dash a source shipped with the punctuation it stood for. */
export function undash(text: string): string {
  return text.replace(DASH, (match, offset: number, whole: string) => {
    if (offset === 0) return "";
    if (offset + match.length === whole.length) return " ";
    return ", ";
  });
}

/** Normalise a posting title: no dashes, no doubled spaces. */
export function clean(value: string | null | undefined): string {
  return undash(String(value ?? ""))
    .replace(/\s*[—–]\s*/g, ", ")
    .replace(/\s+([,;:])/g, "$1")
    .replace(/\s{2,}/g, " ")
    .trim();
}

/** Parse an API timestamp. SQLite returns naive ones, which are UTC. */
export function parseDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const hasZone = /[zZ]|[+-]\d\d:?\d\d$/.test(iso);
  const d = new Date(hasZone ? iso : iso + "Z");
  return Number.isNaN(d.getTime()) ? null : d;
}

export function ago(iso: string | null | undefined, now: number = Date.now()): string {
  const d = parseDate(iso);
  if (!d) return "";
  const s = (now - d.getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d`;
  return shortDate(iso);
}

export function clock(iso: string | Date | null | undefined, tz?: string): string {
  const d = iso instanceof Date ? iso : parseDate(iso);
  if (!d) return "";
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: tz });
}

export function shortDate(iso: string | null | undefined, tz?: string): string {
  const d = parseDate(iso);
  if (!d) return "";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: tz });
}

export function dateTime(iso: string | null | undefined, tz?: string): string {
  const d = parseDate(iso);
  if (!d) return "";
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: tz,
  });
}

function dayKey(d: Date, tz?: string): string {
  return d.toLocaleDateString("en-CA", { timeZone: tz });
}

export function dayName(iso: string, tz?: string, now: number = Date.now()): string {
  const d = parseDate(iso);
  if (!d) return "";
  if (dayKey(d, tz) === dayKey(new Date(now), tz)) return "Today";
  if (dayKey(d, tz) === dayKey(new Date(now - 86400000), tz)) return "Yesterday";
  return d.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric", timeZone: tz });
}

export type MatchTier = "high" | "medium" | "minimal" | "unscored";

export function tierOf(score: number | null | undefined): MatchTier {
  if (score == null) return "unscored";
  if (score >= HIGH) return "high";
  if (score >= MED) return "medium";
  return "minimal";
}

export function tierLabel(t: MatchTier): string {
  return t === "high" ? "HIGH" : t === "medium" ? "MEDIUM" : t === "minimal" ? "MINIMAL" : "Not scored";
}

export function expFit(j: Job): { text: string; cls: string } {
  if (j.is_early_career) return { text: "Early career", cls: "exp-early" };
  if (j.required_experience_years != null)
    return {
      text: `${j.required_experience_years}${j.required_experience_years === 1 ? " yr" : " yrs"} max`,
      cls: "exp-known",
    };
  return { text: "Not stated", cls: "exp-unknown" };
}

/** One or two initials, skipping legal suffixes. */
export function monogram(name: string): string {
  const words = String(name || "")
    .replace(/[^A-Za-z0-9& ]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter((w) => w && !/^(inc|llc|ltd|the|co|corp|corporation|group|holdings)$/i.test(w));
  if (!words.length) return "?";
  if (words.length === 1) return words[0].charAt(0);
  return words[0].charAt(0) + words[1].charAt(0);
}

/** A hue derived from the name, so a company always looks the same. */
export function hueOf(name: string): number {
  let h = 0;
  const t = String(name || "").toLowerCase();
  for (let i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) % 360;
  return h;
}

const INITIALISMS = new Set(["AI", "ML", "UI", "UX", "QA", "IT", "SRE"]);

export function familyLabel(value: string): string {
  return String(value || "")
    .split("_")
    .map((w, i) => {
      if (INITIALISMS.has(w)) return w;
      const l = w.toLowerCase();
      return i === 0 ? l.charAt(0).toUpperCase() + l.slice(1) : l;
    })
    .join(" ");
}

export const EXPORT_NOTE =
  "May require U.S.-person status for export control; the posting does not say the employer will seek a licence. Check before applying.";

export function exportCaveat(j: Job): boolean {
  return (j.reasons || []).some((r) => /^Export control:/.test(r));
}

export function isDone(j: Job): boolean {
  return j.review_state === "reviewed" || j.review_state === "dismissed";
}

/** What "applied before" means for this posting, in one sentence or three. */
export function beforeNote(j: Job, tz?: string): string {
  const b = j.applied_before;
  if (!b) return "";
  const bits: string[] = [];
  if (b.requisition_id) bits.push(`requisition ${b.requisition_id}`);
  if (!b.is_active) bits.push("that posting has closed");
  let note =
    `You applied to "${clean(b.title)}"` +
    (b.location ? `, ${clean(b.location)}` : "") +
    ` on ${shortDate(b.applied_at, tz)}` +
    (bits.length ? ` (${bits.join(", ")})` : "") +
    ".";
  if (b.requisition_id && j.requisition_id)
    note +=
      b.requisition_id === j.requisition_id
        ? " Same requisition as this posting."
        : ` This posting is requisition ${j.requisition_id}, so it may be a separate opening.`;
  if (b.count > 1) note += ` ${b.count - 1} other earlier application${b.count === 2 ? "" : "s"} match too.`;
  return note;
}

/** "MEDIUM to HIGH" when a re-score moved this job since the last visit. */
export function tierMove(j: Job, prevVisit: Date | null): string | null {
  if (j.previous_match_score == null || j.match_score == null) return null;
  const a = tierOf(j.previous_match_score);
  const b = tierOf(j.match_score);
  const changed = parseDate(j.score_changed_at);
  if (a === b || !prevVisit || !changed || changed <= prevVisit) return null;
  return `${tierLabel(a)} to ${tierLabel(b)}`;
}

export function plural(n: number, one: string, many?: string): string {
  return `${n.toLocaleString("en-US")} ${n === 1 ? one : many ?? one + "s"}`;
}
