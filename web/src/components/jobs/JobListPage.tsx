import Link from "next/link";

import { EmptyBox, StatusBadge } from "@/components/bits";
import { Icon } from "@/components/Icon";
import { LiveChip } from "@/components/shell/Live";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGet, apiGetOr } from "@/lib/api";
import { PAGE_SIZE, ago, clean, clock, dayName, shortDate } from "@/lib/format";
import {
  CLEARED,
  DEFAULT_SORTS,
  filterParams,
  jobsParams,
  listHref,
  parseListState,
  toggledSort,
  type ListPage,
  type RawParams,
} from "@/lib/listState";
import { getPrefs, getPrevVisit } from "@/lib/prefs";
import type { ExternalApplication, JobPage, PullsResponse, Stats } from "@/lib/types";

import { JobTable } from "./JobTable";
import { ListControls } from "./ListControls";
import { Pagination } from "./Pagination";
import { Tabs } from "./Tabs";

const TITLES: Record<ListPage, string> = {
  queue: "Opportunities",
  saved: "Saved",
  applied: "Applications",
  archive: "Archive",
};
const BASE: Record<ListPage, string> = {
  queue: "/app/opportunities",
  saved: "/app/saved",
  applied: "/app/applications",
  archive: "/app/archive",
};

/** One list of jobs: the Queue, or a page of marked jobs. Everything that
 *  shapes it is in the URL; this reads it, asks the API, and renders. */
export async function JobListPage({ page, searchParams }: { page: ListPage; searchParams: RawParams }) {
  const state = parseListState(searchParams, page);
  const base = BASE[page];
  const [prefs, prevVisit] = await Promise.all([getPrefs(), getPrevVisit()]);
  const tz = prefs.tz;

  const pulls = await apiGetOr<PullsResponse>(
    "/api/sessions",
    { last_poll_at: null, sessions: [] },
    { limit: "30" },
  );
  const latest = pulls.sessions[0] ?? null;

  const [jobs, stats, newCount, external] = await Promise.all([
    apiGet<JobPage>("/api/jobs", jobsParams(state, { prevVisit, latestPullId: latest?.id ?? null })),
    apiGetOr<Stats>("/api/stats", { last_poll_at: null }, filterParams(state)),
    page === "queue" && prevVisit
      ? apiGetOr<JobPage | null>("/api/jobs", null, { since: prevVisit.toISOString(), limit: "1" })
      : Promise.resolve(null),
    page === "applied"
      ? apiGetOr<{ items: ExternalApplication[] }>("/api/applications/external", { items: [] })
      : Promise.resolve({ items: [] as ExternalApplication[] }),
  ]);

  const newSince = newCount?.total ?? 0;
  const href = (change: Parameters<typeof listHref>[2]) => listHref(base, state, change);

  // New and Latest read newest first; leaving them restores the default.
  const keep = state.view === "new" || state.view === "latest" ? DEFAULT_SORTS : state.sorts;
  const tabs =
    page === "queue"
      ? [
          { key: "all", label: "All opportunities", count: stats.qualifying_active_jobs ?? null, href: href({ view: "all", sorts: keep }) },
          { key: "matched", label: "Strong matches", count: stats.match_high ?? null, href: href({ view: "matched", sorts: keep }) },
          { key: "new", label: "New since your last visit", count: newSince || null, href: href({ view: "new", sorts: ["newest"] }) },
          { key: "latest", label: "Latest discoveries", count: latest?.qualifying_open_now ?? null, href: href({ view: "latest", sorts: ["newest"], session: null }) },
        ]
      : [];

  const empty = emptyState({ page, state, stats, pulls, tz, href, lastPoll: stats.last_poll_at });

  return (
    <>
      <div className="head">
        <div className="head-row">
          <h1 className="h1">{TITLES[page]}</h1>
          <span className="h1-count">{jobs.total.toLocaleString("en-US")}</span>
          <span className="spacer" />
          {page === "applied" ? (
            <a
              className="btn btn-secondary btn-sm"
              href="/api/applications/export.csv"
              download
              title="Every application ace holds, as a spreadsheet"
            >
              <Icon name="download" size={14} />
              Export CSV
            </a>
          ) : null}
          {page === "queue" && newSince && prevVisit ? (
            <Link className="since-btn" href={href({ view: "all", sorts: ["newest"] })}>
              {newSince} new since {clock(prevVisit, tz)}
            </Link>
          ) : null}
          <LiveChip />
        </div>
        {page === "queue" ? <Tabs tabs={tabs} active={state.view} /> : null}
        <ListControls state={state} />
      </div>
      <ScrollArea list>
        {page === "applied" ? (
          <div className="ext-note" style={{ paddingTop: 12 }}>
            Everything you mark applied in ace, newest first. Set its status from the job page as it moves forward.
          </div>
        ) : null}
        <JobTable
          items={jobs.items}
          total={jobs.total}
          offset={jobs.offset}
          page={page}
          sorts={state.sorts}
          group={page === "queue"}
          emptyState={empty}
          sortLinks={
            page === "applied"
              ? {}
              : Object.fromEntries(
                  ["company", "new_grad_first", "best_match", "newest"].map((k) => [k, href({ sorts: toggledSort(state.sorts, k) })]),
                )
          }
        />
        {jobs.items.length ? (
          <Pagination
            current={state.pageNo}
            total={jobs.total}
            pageSize={PAGE_SIZE}
            shown={jobs.items.length}
            href={(p) => href({ pageNo: p })}
          />
        ) : null}
        {page === "applied" && external.items.length ? (
          <>
            <div className="ext-head">From your history</div>
            <div className="ext-note">
              Applications to postings ace never stored, because they were sent or closed{" "}
              {stats.corpus_started_at
                ? `before ace started watching on ${shortDate(stats.corpus_started_at, tz)}. `
                : "before ace started watching. "}
              There is no live posting to open, so these are a record only.
            </div>
            {external.items.map((a) => (
              <div className="ext-row" key={a.id}>
                <span className="co-name">{a.company}</span>
                <span>{clean(a.title)}</span>
                <span>{a.application_status ? <StatusBadge status={a.application_status} /> : null}</span>
                <span className="c-when">{a.applied_at ? shortDate(a.applied_at, tz) : ""}</span>
              </div>
            ))}
          </>
        ) : null}
      </ScrollArea>
    </>
  );
}

function emptyState({
  page,
  state,
  stats,
  pulls,
  tz,
  href,
  lastPoll,
}: {
  page: ListPage;
  state: ReturnType<typeof parseListState>;
  stats: Stats;
  pulls: PullsResponse;
  tz: string;
  href: (change: Parameters<typeof listHref>[2]) => string;
  lastPoll: string | null;
}) {
  const button = (to: string, label: string, ghost = false) => (
    <Link className={`btn ${ghost ? "btn-ghost" : "btn-secondary"}`} href={to}>
      {label}
    </Link>
  );
  if (page === "saved") return <EmptyBox title="Nothing saved yet">Press s on any row, or use the star, to keep it here.</EmptyBox>;
  if (page === "applied")
    return (
      <EmptyBox title="No applications tracked here">
        Mark a job applied from the queue, or press a on a selected row, and it lands here.
      </EmptyBox>
    );
  if (page === "archive")
    return <EmptyBox title="Nothing archived">Jobs you mark reviewed or not relevant land here.</EmptyBox>;
  if (state.pageNo > 1)
    return (
      <EmptyBox title="This page is past the end" actions={button(href({ pageNo: 1 }), "Back to page 1")}>
        The list is shorter than it was when this link was made.
      </EmptyBox>
    );
  if (state.q)
    return (
      <EmptyBox title={`Nothing found for "${state.q}"`} actions={button(href({ q: "" }), "Clear search")}>
        No opportunities match this search.
      </EmptyBox>
    );
  if (state.tiers.length)
    return (
      <EmptyBox title="Nothing in these tiers" actions={button(href({ tiers: [] }), "Clear tier filter")}>
        No opportunities from the employer tiers you selected.
      </EmptyBox>
    );
  if (state.view === "matched")
    return (
      <EmptyBox title="No highly matched opportunities right now" actions={button(href({ view: "all" }), "View all")}>
        {stats.match_medium ?? 0} medium and {stats.match_minimal ?? 0} minimal matches are waiting in All.
      </EmptyBox>
    );
  if (state.view === "new")
    return (
      <EmptyBox title="Nothing new since your last visit" actions={button(href({ view: "all" }), "View all")}>
        ace last pulled {lastPoll ? `${ago(lastPoll)} ago` : "recently"}. You are up to date.
      </EmptyBox>
    );
  if (state.view === "latest") {
    const l = pulls.sessions[0];
    const prior = pulls.sessions.find((x) => x.qualifying_discovered > 0);
    return (
      <EmptyBox
        title={`Latest pull, ${l ? clock(l.started_at, tz) : "not recorded"}`}
        actions={
          <>
            {button("/app/pulls", "See all pulls")} {button(href({ view: "all" }), "Back to all", true)}
          </>
        }
      >
        {l ? `${l.jobs_discovered} opportunities found, none passed your filters.` : "No pull recorded yet."}
        {prior
          ? ` The last pull that added anything was ${dayName(prior.started_at, tz).toLowerCase()} at ${clock(prior.started_at, tz)}.`
          : ""}
      </EmptyBox>
    );
  }
  return (
    <EmptyBox title="Nothing here" actions={button(href({ ...CLEARED }), "Clear filters")}>
      No opportunities match the current filters.
    </EmptyBox>
  );
}
