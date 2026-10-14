// Filters, sort and page live in the URL, so a view can be bookmarked,
// shared, and returned to with Back exactly as it was left. This module
// is the one place that reads them, writes them, and turns them into
// the parameters /api/jobs understands.

import { HIGH, PAGE_SIZE } from "./format";
import type { Tier } from "./types";

export type ListPage = "queue" | "saved" | "applied" | "archive";
export type QueueView = "all" | "matched" | "new" | "latest";

export const SORTS: [string, string][] = [
  ["unapplied_first", "Not applied first"],
  ["experience_fit_first", "Fits my experience"],
  ["new_grad_first", "New grad first"],
  ["best_match", "Best match"],
  ["big_tech_first", "Big tech first"],
  ["newest", "Newest"],
  ["oldest", "Oldest"],
  ["company", "Company"],
];

export const SORT_PHRASE: Record<string, string> = {
  unapplied_first: "the ones you have not applied to",
  experience_fit_first: "roles that fit your experience",
  new_grad_first: "new grad roles",
  best_match: "best match",
  big_tech_first: "big tech",
  newest: "newest first",
  oldest: "oldest first",
  recently_posted: "recently posted",
  company: "company name",
  title: "job title",
};

export const DEFAULT_SORTS = ["unapplied_first", "experience_fit_first", "best_match"];

export const TIERS: Tier[] = ["BIG_TECH", "TOP_TIER", "ESTABLISHED"];

// Optional housekeeping, off by default: hide what ACE detected more
// than this many days ago. Nothing is ever deleted.
export const RECENT_DAYS = 15;

export interface ListState {
  page: ListPage;
  view: QueueView;
  q: string;
  sorts: string[];
  /** True when the sort came from the URL rather than the view's default. */
  sortChosen: boolean;
  tiers: Tier[];
  companies: string[];
  excluded: string[];
  sources: string[];
  families: string[];
  early: boolean;
  newGrad: boolean;
  verified: boolean;
  includeOld: boolean;
  recent: boolean;
  pageNo: number;
  session: number | null;
}

export type RawParams = Record<string, string | string[] | undefined>;

function one(raw: RawParams, key: string): string {
  const v = raw[key];
  return (Array.isArray(v) ? v[0] : v) ?? "";
}

function list(raw: RawParams, key: string): string[] {
  return one(raw, key)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function flag(raw: RawParams, key: string): boolean {
  const v = one(raw, key);
  return v === "1" || v === "true";
}

const VIEWS: QueueView[] = ["all", "matched", "new", "latest"];
const KNOWN_SORTS = new Set(SORTS.map(([k]) => k));

export function parseListState(raw: RawParams, page: ListPage): ListState {
  const viewRaw = one(raw, "view") as QueueView;
  const view: QueueView = page === "queue" && VIEWS.includes(viewRaw) ? viewRaw : "all";
  // "none" is every sort switched off, which is a choice too.
  const none = one(raw, "sort") === "none";
  const chosen = list(raw, "sort").filter((s) => KNOWN_SORTS.has(s)).slice(0, 3);
  const sorts = none ? [] : chosen.length ? chosen : defaultSorts(page, view);
  const pageNo = Math.max(1, parseInt(one(raw, "page"), 10) || 1);
  const session = parseInt(one(raw, "session"), 10);
  return {
    page,
    view,
    q: one(raw, "q").trim(),
    sorts,
    sortChosen: none || chosen.length > 0,
    tiers: list(raw, "tier").filter((t): t is Tier => (TIERS as string[]).includes(t)),
    companies: list(raw, "company"),
    excluded: list(raw, "exclude"),
    sources: list(raw, "source"),
    families: list(raw, "family"),
    early: flag(raw, "early"),
    newGrad: flag(raw, "newgrad"),
    verified: flag(raw, "verified"),
    includeOld: flag(raw, "old"),
    recent: flag(raw, "recent"),
    pageNo,
    session: Number.isFinite(session) ? session : null,
  };
}

/** New arrivals and a single pull read best newest first. */
export function defaultSorts(page: ListPage, view: QueueView): string[] {
  if (page === "applied") return ["newest"];
  if (page === "queue" && (view === "new" || view === "latest")) return ["newest"];
  return DEFAULT_SORTS;
}

/** The URL for a list state. Defaults are left out, so URLs stay short. */
export function listHref(base: string, s: ListState, change: Partial<ListState> = {}): string {
  const n = { ...s, ...change };
  // Any change other than the page number goes back to page one: page
  // 4 of one filter is meaningless under another.
  if (!("pageNo" in change)) n.pageNo = 1;
  const p = new URLSearchParams();
  if (n.page === "queue" && n.view !== "all") p.set("view", n.view);
  if (n.q) p.set("q", n.q);
  const sortDefault = defaultSorts(n.page, n.view).join(",");
  if (n.sorts.join(",") !== sortDefault) p.set("sort", n.sorts.join(",") || "none");
  if (n.tiers.length) p.set("tier", n.tiers.join(","));
  if (n.companies.length) p.set("company", n.companies.join(","));
  if (n.excluded.length) p.set("exclude", n.excluded.join(","));
  if (n.sources.length) p.set("source", n.sources.join(","));
  if (n.families.length) p.set("family", n.families.join(","));
  if (n.early) p.set("early", "1");
  if (n.newGrad) p.set("newgrad", "1");
  if (n.verified) p.set("verified", "1");
  if (n.includeOld) p.set("old", "1");
  if (n.recent) p.set("recent", "1");
  if (n.session != null && n.view === "latest") p.set("session", String(n.session));
  if (n.pageNo > 1) p.set("page", String(n.pageNo));
  const q = p.toString();
  return q ? `${base}?${q}` : base;
}

/** Filters shared by /api/jobs, /api/stats and /api/facets. */
export function filterParams(s: ListState): URLSearchParams {
  const p = new URLSearchParams();
  if (s.q) p.set("q", s.q);
  if (s.tiers.length) p.set("tier", s.tiers.join(","));
  if (s.companies.length) p.set("company", s.companies.join(","));
  if (s.excluded.length) p.set("exclude_company", s.excluded.join(","));
  if (s.sources.length) p.set("source", s.sources.join(","));
  if (s.families.length) p.set("family", s.families.join(","));
  if (s.early) p.set("experience_fit_only", "true");
  if (s.newGrad) p.set("new_grad_only", "true");
  if (s.verified) p.set("verified_only", "true");
  if (s.includeOld) p.set("include_old", "true");
  // Scoped to the Queue: a saved or archived job is never hidden by a
  // housekeeping default.
  if (s.page === "queue" && s.recent) p.set("max_detected_age_days", String(RECENT_DAYS));
  return p;
}

export function markParam(page: ListPage): string | null {
  return page === "saved" ? "saved" : page === "archive" ? "archived" : page === "applied" ? "applied" : null;
}

/** The /api/jobs query for one page of a list. */
export function jobsParams(
  s: ListState,
  opts: { prevVisit: Date | null; latestPullId: number | null },
): URLSearchParams {
  const p = filterParams(s);
  p.set("sort", s.sorts.length ? s.sorts.join(",") : "new_grad_first");
  p.set("limit", String(PAGE_SIZE));
  p.set("offset", String((s.pageNo - 1) * PAGE_SIZE));
  const mark = markParam(s.page);
  if (mark) {
    p.set("mark", mark);
    return p;
  }
  if (s.view === "matched") p.set("min_match", String(HIGH));
  if (s.view === "new" && opts.prevVisit) p.set("since", opts.prevVisit.toISOString());
  if (s.view === "latest") {
    const id = s.session ?? opts.latestPullId;
    if (id != null) p.set("session_id", String(id));
  }
  return p;
}

/** What the filter menu counts within: the list on screen, unpaged. */
export function facetParams(s: ListState): URLSearchParams {
  const p = filterParams(s);
  const mark = markParam(s.page);
  if (mark) p.set("mark", mark);
  else if (s.view === "matched") p.set("min_match", String(HIGH));
  return p;
}

/** "Showing the ones you have not applied to first, then ..." */
export function sortSentence(sorts: string[]): string {
  const names = sorts.map((k) => SORT_PHRASE[k] ?? k);
  if (!names.length) return "";
  // "first" belongs to the leading key; some phrases already end in it.
  const lead = /first$/.test(names[0]) ? names[0] : `${names[0]} first`;
  return lead + names.slice(1).map((x) => `, then ${x}`).join("");
}

export function isFiltered(s: ListState): boolean {
  return Boolean(
    s.q ||
      s.tiers.length ||
      s.companies.length ||
      s.excluded.length ||
      s.sources.length ||
      s.families.length ||
      s.verified,
  );
}

export const CLEARED: Partial<ListState> = {
  q: "",
  tiers: [],
  companies: [],
  excluded: [],
  sources: [],
  families: [],
  verified: false,
  early: false,
  newGrad: false,
};

/** Turning a sort on makes it the primary one, as a column header does;
 *  appending it instead only broke ties and looked broken. */
export function toggledSort(sorts: string[], key: string): string[] {
  const i = sorts.indexOf(key);
  if (i >= 0) return sorts.filter((s) => s !== key);
  return [key, ...sorts].slice(0, 3);
}
