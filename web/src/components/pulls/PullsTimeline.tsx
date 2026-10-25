"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Avatar, EmptyBox } from "@/components/bits";
import { useMarks } from "@/components/jobs/useMarks";
import { useApp, withPatch } from "@/components/shell/AppProvider";
import { NavIcon } from "@/components/shell/NavIcon";
import { getJson } from "@/lib/client";
import { ago, beforeNote, clean, clock, expFit, familyLabel, shortDate, timeRange, unscoredReason, UNSCORED } from "@/lib/format";
import type { Job, JobPage, PullBucket, PullFilter } from "@/lib/types";

const SHOWN = 20;

interface CompanyEvidence { period: string; source: string; source_uri: string; metric_definition: string; approvals: number | null; denials: number | null; last_checked_at: string }
interface CompanyDetail { company: string; status: string; petition_history: (CompanyEvidence & {legal_entity: string; report_version: string; first_seen_at: string; approval_rate: number | null})[] }

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

function JobLine({ job, tz, evidence, onCompanySelect }: { job: Job; tz: string; evidence?: CompanyEvidence; onCompanySelect: (name: string) => void }) {
  const { mark } = useMarks();
  const fit = expFit(job);
  const applied = Boolean(job.applied_at);
  const dismissed = job.review_state === "dismissed";
  return (
    <div className={`job-line${dismissed ? " dim" : ""}`}>
      <Avatar name={job.company} />
      <div className="job-copy">
        <button className="job-company" onClick={() => onCompanySelect(job.company)}>
          {clean(job.company)}
        </button>
        <Link className="job-title" href={`/app/jobs/${job.id}`} prefetch={false}>{clean(job.title)}</Link>
        <div className="job-meta">
          {[clean(job.location), familyLabel(job.role_family)].filter(Boolean).join(" · ")}
          {job.requirements_verified ? "" : " · requirements unverified"}
          {" · detected "}
          {clock(job.first_seen_at, tz)}
        </div>
        <div className="job-tags">
          <span className={fit.cls}>{fit.text}</span>
          {job.applied_before && !applied ? (
            <span className="badge before" title={beforeNote(job, tz)}>
              Applied before {"·"} {shortDate(job.applied_before.applied_at, tz)}
            </span>
          ) : null}
        </div>
        <div className="job-evidence">{evidence ? `${clean(evidence.period)} USCIS petition decisions: ${evidence.approvals ?? "Not available"} approved, ${evidence.denials ?? "Not available"} denied. Source: ${clean(evidence.source)}.` : "H-1B history: Not available"} <button onClick={() => onCompanySelect(job.company)}>Company insights</button></div>
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
        <Link className="sub-btn" href={`/app/jobs/${job.id}`} prefetch={false}>
          <span className="sub-t">Details</span> <NavIcon name="right" size="sm" />
        </Link>
      </div>
    </div>
  );
}

function Results({ bucket, tz, onCompanySelect }: { bucket: PullBucket; tz: string; onCompanySelect: (name: string) => void }) {
  const { patches, hidden } = useApp();
  const [page, setPage] = useState<JobPage | null>(null);
  const [failed, setFailed] = useState(false);
  const [evidence, setEvidence] = useState<Record<string, CompanyEvidence>>({});

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

  useEffect(() => {
    if (!page?.items.length) return;
    let live = true;
    const params = new URLSearchParams();
    for (const name of new Set(page.items.map((item) => item.company))) params.append("name", name);
    getJson<{items: Record<string, CompanyEvidence>}>("/api/company-intelligence/batch", params)
      .then((data) => { if (live) setEvidence(data.items); })
      .catch(() => { if (live) setEvidence({}); });
    return () => { live = false; };
  }, [page]);

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
        jobs.map((j) => <JobLine key={j.id} job={j} tz={tz} evidence={evidence[j.company]} onCompanySelect={onCompanySelect} />)
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

function CompanyInsightDialog({ company, onClose }: { company: string; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [detail, setDetail] = useState<CompanyDetail | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (element && !element.open) element.showModal();
  }, []);
  useEffect(() => {
    let live = true;
    getJson<CompanyDetail>("/api/company-intelligence", new URLSearchParams({ name: company }))
      .then((value) => { if (live) setDetail(value); })
      .catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [company]);
  return <dialog ref={ref} className="company-dialog" onClose={onClose} aria-label={`Company intelligence for ${clean(company)}`}>
    <div className="company-dialog-head"><div><div className="eyebrow">Company intelligence</div><h2>{clean(company)}</h2></div><button className="btn ghost" onClick={() => ref.current?.close()} aria-label="Close company intelligence">Close</button></div>
    {failed ? <p>Company evidence could not be loaded. Try again later.</p> : !detail ? <p>Loading verified company evidence</p> : detail.petition_history.length ? <>
      {detail.petition_history.map((report) => <div className="company-report" key={`${report.source_uri}:${report.period}:${report.report_version}`}><h3>{clean(report.legal_entity)} · {clean(report.period)}</h3><p>{clean(report.metric_definition)}. Approved: {report.approvals ?? "Not available"}. Denied: {report.denials ?? "Not available"}. Approval rate: {report.approval_rate == null ? "Not available" : `${Math.round(report.approval_rate * 100)}%`}.</p><p>Source: <a href={report.source_uri} rel="noreferrer" target="_blank">{clean(report.source)}</a>. Checked: {new Date(report.last_checked_at).toLocaleDateString("en-US")}.</p></div>)}
    </> : <p>H-1B petition history: Not available. No verified official report is connected to this company.</p>}
    <p>Company workforce sponsorship rate: Not available. Petition decisions do not predict sponsorship for a specific job.</p>
    <Link className="btn" href={`/app/company/${encodeURIComponent(company)}`}>Open company page</Link>
  </dialog>;
}

/** The windows, newest first. Each opens to the jobs it found, loaded
 *  when opened, so the page itself stays one request. */
export function PullsTimeline({
  buckets,
  tz,
  filter,
  isToday,
  date,
}: {
  buckets: PullBucket[];
  tz: string;
  filter: PullFilter;
  isToday: boolean;
  date: string;
}) {
  const firstHit = buckets.find((b) => b.new_qualifying > 0);
  const [open, setOpen] = useState<Set<number>>(() => new Set(firstHit && isToday ? [firstHit.id] : []));
  const [restored, setRestored] = useState(false);
  const storageKey = `ace.pulls.open:${date}`;
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);

  // Keep the exact windows the owner left open, including an intentionally
  // closed latest window. A new pull must not discard an earlier open one.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw !== null) {
        const saved: unknown = JSON.parse(raw);
        if (Array.isArray(saved)) {
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setOpen(new Set(saved.filter((id): id is number => Number.isSafeInteger(id) && id > 0)));
        }
      }
    } catch {}
    setRestored(true);
  }, [storageKey]);

  useEffect(() => {
    if (!restored) return;
    try { localStorage.setItem(storageKey, JSON.stringify([...open])); } catch {}
  }, [open, restored, storageKey]);

  const toggle = useCallback((id: number) => {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

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
                      <b>{n(b.sources_succeeded)}</b> boards read
                    </span>
                    {b.sources_attempted != null ? (
                      <span>
                        <b>{n(b.sources_attempted)}</b> attempted
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
                  <Results bucket={b} tz={tz} onCompanySelect={setSelectedCompany} />
                </div>
              ) : null}
            </section>
          </div>
        );
      })}
      {selectedCompany ? <CompanyInsightDialog key={selectedCompany} company={selectedCompany} onClose={() => setSelectedCompany(null)} /> : null}
    </div>
  );
}
