"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Avatar, EmptyBox } from "@/components/bits";
import { useMarks } from "@/components/jobs/useMarks";
import { useApp, withPatch } from "@/components/shell/AppProvider";
import { NavIcon } from "@/components/shell/NavIcon";
import { getJson } from "@/lib/client";
import { ago, clean, clock, expFit, familyLabel, timeRange, unscoredReason, UNSCORED } from "@/lib/format";
import type { Job, JobPage, PullBucket, PullFilter } from "@/lib/types";

const SHOWN = 20;

function n(value: number): string {
  return value.toLocaleString("en-US");
}

function plural(count: number, one: string, many: string): string {
  return `${n(count)} ${count === 1 ? one : many}`;
}

function title(b: PullBucket): string {
  if (b.outcome === "opportunities") return `${plural(b.new_qualifying, "relevant opportunity", "relevant opportunities")} surfaced`;
  if (b.outcome === "new_postings") return `${plural(b.new_postings, "new posting", "new postings")}, none for you`;
  return "Checked, nothing new";
}

function description(b: PullBucket): string {
  const parts: string[] = [];
  if (b.outcome === "opportunities") {
    const closed = b.new_qualifying - b.qualifying_open_now;
    parts.push(
      closed > 0
        ? `${n(b.qualifying_open_now)} still open, ${n(closed)} closed since.`
        : "New qualifying roles are ready for review.",
    );
  } else if (b.outcome === "new_postings") {
    parts.push("New postings arrived, and none passed your filters.");
  } else {
    parts.push("Sources answered. No new posting appeared in this window.");
  }
  if (b.failed_checks) parts.push(`${plural(b.failed_checks, "source", "sources")} failed or refused in this window.`);
  if (b.telemetry === "partial") parts.push("Attempts and failures were not recorded for this window.");
  return parts.join(" ");
}

function JobLine({ job, tz }: { job: Job; tz: string }) {
  const { mark } = useMarks();
  const fit = expFit(job);
  const applied = Boolean(job.applied_at);
  const dismissed = job.review_state === "dismissed";
  return (
    <div className={`job-line${dismissed ? " dim" : ""}`}>
      <Avatar name={job.company} />
      <div className="job-copy">
        <Link className="job-title" href={`/app/jobs/${job.id}`}>
          {clean(job.title)}
        </Link>
        <div className="job-meta">
          {[job.company, clean(job.location), familyLabel(job.role_family), fit.text === "Not stated" ? "Experience not stated" : fit.text].filter(Boolean).join(" · ")}
          {job.requirements_verified ? "" : " · requirements unverified"}
          {" · detected "}
          {clock(job.first_seen_at, tz)}
          {job.applied_before ? " · applied before" : ""}
        </div>
      </div>
      {job.match_score == null ? (
        <span className="pscore dim" title={UNSCORED[unscoredReason(job)].long}>
          {UNSCORED[unscoredReason(job)].short}
        </span>
      ) : (
        <span className={`pscore${job.match_score >= 70 ? "" : " mid"}`}>{job.match_score}%</span>
      )}
      <div className="job-actions">
        {applied ? <span className="tag green">Applied</span> : null}
        <a className="sub-btn icon" href={job.official_url} target="_blank" rel="noreferrer" title="Open the official posting" aria-label={`Open the official posting for ${clean(job.title)}`}>
          <NavIcon name="external" size="sm" />
        </a>
        <button
          className={`sub-btn${applied ? " on" : ""}`}
          onClick={() => mark(job, "applied")}
          aria-pressed={applied}
          title={applied ? "Clear applied" : "Mark applied"}
          aria-label={applied ? "Clear applied" : "Mark applied"}
        >
          <NavIcon name="check" size="sm" />
          <span className="sub-t">{applied ? "Applied" : "Applied?"}</span>
        </button>
        <button
          className={`sub-btn${dismissed ? " on" : ""}`}
          onClick={() => mark(job, "dismissed")}
          aria-pressed={dismissed}
          title={dismissed ? "Restore" : "Not relevant"}
          aria-label={dismissed ? "Restore" : "Not relevant"}
        >
          <NavIcon name="x" size="sm" />
        </button>
        <Link className="sub-btn" href={`/app/jobs/${job.id}`}>
          <span className="sub-t">Details</span> <NavIcon name="right" size="sm" />
        </Link>
      </div>
    </div>
  );
}

function Results({ bucket, tz }: { bucket: PullBucket; tz: string }) {
  const { patches, hidden } = useApp();
  const [page, setPage] = useState<JobPage | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (bucket.new_qualifying === 0) return;
    let live = true;
    getJson<JobPage>(
      "/api/jobs",
      new URLSearchParams({ session_id: String(bucket.id), limit: String(SHOWN), sort: "best_match" }),
    )
      .then((d) => live && setPage(d))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [bucket.id, bucket.new_qualifying]);

  if (bucket.new_qualifying === 0)
    return (
      <div className="pull-empty">
        {bucket.outcome === "new_postings"
          ? `${plural(bucket.new_postings, "new posting", "new postings")} arrived and none passed your filters, so there is nothing to review.`
          : "Nothing to review. The scheduler still ran."}
      </div>
    );
  if (failed) return <div className="pull-empty">These jobs could not be loaded. Reload to try again.</div>;
  if (!page)
    return (
      <div className="pull-empty" aria-busy="true">
        Loading the jobs from this window
      </div>
    );

  const jobs = page.items.filter((j) => !hidden.has(j.id)).map((j) => withPatch(j, patches));
  const more = page.total - page.items.length;
  return (
    <>
      {jobs.length ? (
        jobs.map((j) => <JobLine key={j.id} job={j} tz={tz} />)
      ) : (
        <div className="pull-empty">
          {bucket.qualifying_open_now === 0
            ? "Every role from this window has closed since."
            : "These roles are hidden by your marks."}
        </div>
      )}
      {more > 0 ? (
        <div className="pull-more">
          <Link className="link-btn" href={`/app/opportunities?view=latest&session=${bucket.id}`}>
            Show {n(more)} more in Opportunities
          </Link>
        </div>
      ) : null}
    </>
  );
}

/** The windows, newest first. Each opens to the jobs it found, loaded
 *  when opened, so the page itself stays one request. */
export function PullsTimeline({
  buckets,
  tz,
  filter,
  isToday,
}: {
  buckets: PullBucket[];
  tz: string;
  filter: PullFilter;
  isToday: boolean;
}) {
  const firstHit = buckets.find((b) => b.new_qualifying > 0);
  const [open, setOpen] = useState<Set<number>>(() => new Set(firstHit && isToday ? [firstHit.id] : []));
  const toggle = useCallback(
    (id: number) =>
      setOpen((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      }),
    [],
  );

  // "Latest pull" in the header jumps here and opens it.
  useEffect(() => {
    const onHash = () => {
      const m = /^#pull-(\d+)$/.exec(window.location.hash);
      if (m) setOpen((prev) => new Set(prev).add(Number(m[1])));
    };
    onHash();
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (!buckets.length)
    return (
      <EmptyBox title={filter === "all" ? "Nothing recorded for this day" : "No windows match this filter"}>
        {filter === "all"
          ? "ace records a window once it has finished checking a source in it."
          : "Switch to All activity to see every window."}
      </EmptyBox>
    );

  return (
    <div className="timeline">
      {buckets.map((b, i) => {
        const isOpen = open.has(b.id);
        const checked = b.sources_attempted ?? b.sources_succeeded;
        return (
          <div className={`pull-entry${b.new_qualifying ? "" : " quiet"}${b.failed_checks ? " warn" : ""}`} key={b.id} id={`pull-${b.id}`}>
            <div className="pull-when">
              <span>{clock(b.start, tz)}</span>
            </div>
            <section className="pull-card">
              <button
                className="pull-summary"
                aria-expanded={isOpen}
                aria-controls={`pull-results-${b.id}`}
                onClick={() => toggle(b.id)}
              >
                <div className="pull-copy">
                  <div className="pull-title">{title(b)}</div>
                  <div className="pull-range">{timeRange(b.start, b.end, tz)}</div>
                  <div className="pull-description">{description(b)}</div>
                  <div className="pull-stats">
                    <span>
                      <b>{n(checked)}</b> {b.sources_attempted == null ? "sources answered" : "sources checked"}
                    </span>
                    {b.sources_attempted != null ? (
                      <span>
                        <b>{n(b.sources_succeeded)}</b> answered
                      </span>
                    ) : null}
                    {b.failed_checks != null ? (
                      <span className={b.failed_checks ? "bad" : undefined}>
                        <b>{n(b.failed_checks)}</b> failed
                      </span>
                    ) : null}
                    {b.poll_attempts != null ? (
                      <span>
                        <b>{n(b.poll_attempts)}</b> attempts
                      </span>
                    ) : null}
                    <span>
                      <b>{n(b.postings_observed)}</b> postings observed
                    </span>
                    <span>
                      <b>{n(b.new_postings)}</b> new
                    </span>
                    <span className={b.new_qualifying ? "good" : undefined}>
                      <b>{n(b.new_qualifying)}</b> relevant
                    </span>
                  </div>
                </div>
                <div className="pull-side">
                  {i === 0 && isToday && filter === "all" ? <span className="tag green">Latest</span> : null}
                  {b.failed_checks ? <span className="tag orange">Partial</span> : null}
                  <span className="pull-ago" suppressHydrationWarning>
                    {ago(b.last_activity_at ?? b.end)}
                  </span>
                  <span className={`chev${isOpen ? " up" : ""}`}>
                    <NavIcon name="chevron" />
                  </span>
                </div>
              </button>
              {isOpen ? (
                <div className="pull-results" id={`pull-results-${b.id}`}>
                  <Results bucket={b} tz={tz} />
                </div>
              ) : null}
            </section>
          </div>
        );
      })}
    </div>
  );
}
