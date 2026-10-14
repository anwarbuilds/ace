// The groups the site is browsed by, like a shop's departments. Each one
// is its own route (/app/browse/<slug>) and a row on the home page; each
// is just a saved /api/jobs query, so nothing is hidden that the full
// Opportunities list would show.

export interface BrowseGroup {
  slug: string;
  title: string;
  blurb: string;
  params: Record<string, string>;
}

const BY_FIT = "unapplied_first,new_grad_first,best_match";

export const GROUPS: BrowseGroup[] = [
  {
    slug: "strong-matches",
    title: "Strong matches",
    blurb: "Roles where your resume shows most of what the posting asks for.",
    params: { min_match: "70", sort: "unapplied_first,best_match" },
  },
  {
    slug: "new-today",
    title: "New today",
    blurb: "Found by ace in the last 24 hours, newest first.",
    params: { max_detected_age_days: "1", sort: "newest" },
  },
  {
    slug: "new-grad",
    title: "New grad",
    blurb: "Roles written for new graduates, your primary target.",
    params: { new_grad_only: "true", sort: "unapplied_first,best_match" },
  },
  {
    slug: "big-tech",
    title: "Big tech",
    blurb: "Open roles at the largest technology employers.",
    params: { tier: "BIG_TECH", sort: BY_FIT },
  },
  {
    slug: "top-tier",
    title: "Top tier",
    blurb: "Strong engineering companies below big tech.",
    params: { tier: "TOP_TIER", sort: BY_FIT },
  },
  {
    slug: "machine-learning",
    title: "Machine learning",
    blurb: "Machine learning and AI engineering roles.",
    params: { family: "AI_ML_ENGINEERING", sort: BY_FIT },
  },
  {
    slug: "forward-deployed",
    title: "Forward deployed",
    blurb: "Forward deployed and customer-facing engineering roles.",
    params: { family: "FORWARD_DEPLOYED_ENGINEERING", sort: BY_FIT },
  },
  {
    slug: "software-engineering",
    title: "Software engineering",
    blurb: "Backend, frontend, full stack and platform roles.",
    params: { family: "SOFTWARE_ENGINEERING", sort: BY_FIT },
  },
  {
    slug: "remote",
    title: "Remote",
    blurb: "Roles that say they can be done remotely in the US.",
    params: { q: "remote", sort: BY_FIT },
  },
];

export function groupBySlug(slug: string): BrowseGroup | undefined {
  return GROUPS.find((g) => g.slug === slug);
}

export const BROWSE_SORTS: [string, string][] = [
  ["fit", "Best for you"],
  ["newest", "Newest"],
  ["best_match", "Best match"],
  ["company", "Company"],
];

export function sortParam(key: string, group: BrowseGroup): string {
  if (key === "newest") return "newest";
  if (key === "best_match") return "best_match";
  if (key === "company") return "company";
  return group.params.sort ?? BY_FIT;
}

export function companyHref(name: string): string {
  return `/app/companies/${encodeURIComponent(name)}`;
}
