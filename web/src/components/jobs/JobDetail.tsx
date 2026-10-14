"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Avatar, ScoreRing } from "@/components/bits";
import { Icon } from "@/components/Icon";
import { useApp, withPatch } from "@/components/shell/AppProvider";
import { Popover, usePopover } from "@/components/shell/Popover";
import {
  EXPORT_NOTE,
  STATUSES,
  STATUS_LABEL,
  TIER_LABEL,
  beforeNote,
  clean,
  dateTime,
  expFit,
  exportCaveat,
  familyLabel,
  shortDate,
  tierLabel,
  tierOf,
  UNSCORED,
  unscoredReason,
} from "@/lib/format";
import type { Job } from "@/lib/types";

import { useMarks, type MarkKey } from "./useMarks";

/** Back to the list this job was opened from, as it was left. */
function useBack() {
  const router = useRouter();
  const [target, setTarget] = useState("/app/opportunities");
  useEffect(() => {
    try {
      const last = sessionStorage.getItem("ace.lastList");
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (last) setTarget(last.replace(/\?$/, ""));
    } catch {}
  }, []);
  const label = target.startsWith("/app/activity")
    ? "activity"
    : target.startsWith("/app/saved")
      ? "saved roles"
      : target.startsWith("/app/applications")
        ? "applications"
        : target.startsWith("/app/archive")
          ? "archive"
          : "opportunities";
  return { go: () => router.push(target, { scroll: false }), label };
}

export function JobDetail({ job: served, resumeLabel }: { job: Job; resumeLabel: string | null }) {
  const { patches, tz } = useApp();
  const job = withPatch(served, patches);
  const { mark, setStatus } = useMarks();
  const back = useBack();
  const info = usePopover();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (/^(INPUT|TEXTAREA|SELECT)$/.test((e.target as Element)?.tagName ?? "")) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (document.querySelector(".palette-wrap,.pop,.ab")) return;
      if (e.key === "Escape") back.go();
      else if (e.key === "Enter") window.open(job.official_url, "_blank", "noopener");
      else if (e.key === "a") void mark(job, "applied");
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [job, mark, back]);

  const t = tierOf(job.match_score);
  const fit = expFit(job);
  const tier = job.company_tier || "OTHER";
  const applied = Boolean(job.applied_at);
  const status = job.application_status;
  const why: string[] = [];
  if (job.role_family) why.push(familyLabel(job.role_family));
  if (job.is_early_career) why.push("Labelled early career");
  else if (job.required_experience_years != null) why.push(`${job.required_experience_years} years or less required`);
  why.push("No eligibility blocker found");

  const markBtn = (key: MarkKey, icon: "star" | "check" | "x" | "briefcase", label: string, on: boolean) => (
    <button className={`btn btn-ghost btn-sm${on ? " on" : ""}`} data-mark={key} onClick={() => void mark(job, key)}>
      <Icon name={icon} size={14} />
      {label}
    </button>
  );

  return (
    <div className="jp">
      <header className="jp-hero">
        <div className="jp-in">
          <button className="jp-back" onClick={back.go}>
            <Icon name="left" size={14} />
            Back to {back.label}
          </button>
          <div className="jp-head">
            <Avatar name={job.company} large />
            <div className="jp-headtxt">
              {TIER_LABEL[tier] ? <div className={`jp-tier tier-${tier}`}>{TIER_LABEL[tier]}</div> : null}
              <h1 className="jp-title">{clean(job.title)}</h1>
              <div className="jp-meta">
                <span className="jp-co">{job.company}</span>
                <span>{clean(job.location)}</span>
                <span className={fit.cls}>{fit.text}</span>
                {status ? (
                  <span className={`badge ${status}`}>
                    {STATUS_LABEL[status]}
                    {job.applied_at ? ` · ${shortDate(job.applied_at, tz)}` : ""}
                  </span>
                ) : null}
                {job.applied_before && !applied ? (
                  <span className="badge before" title={beforeNote(job, tz)}>
                    Applied before {"·"} {shortDate(job.applied_before.applied_at, tz)}
                  </span>
                ) : null}
                {exportCaveat(job) ? (
                  <span className="badge export" title={EXPORT_NOTE}>
                    Export check
                  </span>
                ) : null}
                {!job.is_active ? <span className="badge rejected">Closed</span> : null}
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="jp-in">
        <div className="jp-grid">
          <div>
            <div className="card match">
              <p className="eyebrow">Resume match</p>
              <div className="score-row">
                <ScoreRing score={job.match_score} />
                <div>
                  <div className="score-meta">
                    {t === "unscored" ? (
                      UNSCORED[unscoredReason(job)].long
                    ) : (
                      <>
                        <b className={`m-${t}`}>{tierLabel(t)}</b> match against {resumeLabel ?? "your resume"}
                      </>
                    )}{" "}
                    <button className="info" onClick={(e) => info.open(e.currentTarget)} aria-label="What this means">
                      i
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {job.matched_skills.length ? (
              <div className="card">
                <p className="eyebrow">Skills you have</p>
                <div className="skills">
                  {job.matched_skills.map((s) => (
                    <span key={s} className="sk have">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {job.related_skills.length ? (
              <div className="card">
                <p className="eyebrow">Counted as partial credit</p>
                <div className="rel">
                  {job.related_skills.map((s) => {
                    const ev = job.related_evidence.find((e) => e.skill === s);
                    return (
                      <div key={s} className="rel-row">
                        <span className="sk">{s}</span>
                        <span className="rel-via">{ev ? `via your ${ev.via}` : "related to your experience"}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {job.missing_skills.length ? (
              <div className="card">
                <p className="eyebrow">Not on your resume</p>
                <div className="skills">
                  {job.missing_skills.map((s) => (
                    <span key={s} className="sk miss">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="card">
              <p className="eyebrow">Why this is in your queue</p>
              <p className="why">
                {why.join(" · ")}.
                <br />
                No sponsorship language was found in this posting.
              </p>
            </div>
          </div>

          <div className="jp-aside">
            <div className="card">
              <div className="acts-col">
                <a className="btn btn-primary" href={job.official_url} target="_blank" rel="noopener noreferrer">
                  Open official posting
                  <Icon name="ext" />
                </a>
                <div className="status-grid">
                  {markBtn("reviewed", "check", "Reviewed", job.review_state === "reviewed")}
                  {markBtn("dismissed", "x", "Not relevant", job.review_state === "dismissed")}
                  <div style={{ gridColumn: "1 / -1", display: "grid" }}>{markBtn("applied", "briefcase", "Applied", applied)}</div>
                </div>
              </div>
            </div>

            <div className="card">
              <p className="eyebrow">Application status</p>
              {applied ? (
                <p className="why" style={{ margin: "0 0 12px" }}>
                  <b>{STATUS_LABEL[status ?? "applied"]}</b>
                  {job.applied_at ? `, applied ${shortDate(job.applied_at, tz)}` : ""}
                  {job.status_changed_at && status && status !== "applied" ? (
                    <>
                      <br />
                      Updated {shortDate(job.status_changed_at, tz)}
                    </>
                  ) : null}
                </p>
              ) : job.applied_before ? (
                <p className="why" style={{ margin: "0 0 12px" }}>
                  <b>Applied before.</b> {beforeNote(job, tz)} This posting is not marked applied.{" "}
                  <Link className="link-btn" href={`/app/jobs/${job.applied_before.job_id}`}>
                    See that application
                  </Link>
                </p>
              ) : (
                <p className="why" style={{ margin: "0 0 12px" }}>
                  Not applied yet.
                </p>
              )}
              <div className="status-grid">
                {STATUSES.map((st) => (
                  <button
                    key={st}
                    className={`btn btn-ghost btn-sm${status === st ? " on" : ""}`}
                    data-status={st}
                    onClick={() => void setStatus(job, st)}
                  >
                    {STATUS_LABEL[st]}
                  </button>
                ))}
              </div>
            </div>

            <div className="card">
              <p className="eyebrow">Details</p>
              <dl className="kv">
                <dt>First detected</dt>
                <dd>{dateTime(job.first_seen_at, tz)}</dd>
                <dt>Last confirmed</dt>
                <dd>{dateTime(job.last_seen_at, tz)}</dd>
                <dt>Source</dt>
                <dd>
                  {job.source}
                  {job.requirements_verified ? ", verified" : ", not readable"}
                </dd>
                {exportCaveat(job) ? (
                  <>
                    <dt>Export control</dt>
                    <dd>{EXPORT_NOTE}</dd>
                  </>
                ) : null}
                {job.requisition_id ? (
                  <>
                    <dt>Requisition</dt>
                    <dd>{job.requisition_id}</dd>
                  </>
                ) : null}
              </dl>
            </div>
          </div>
        </div>
      </div>

      <Popover anchor={info.anchor} onClose={info.close}>
        <h4>Match score</h4>
        <p>
          How much of this posting&rsquo;s stated requirements your active resume already evidences. Related skills
          count as a partial match.
        </p>
        <p>It helps you decide what to read first. It does not predict whether you will be hired.</p>
      </Popover>
    </div>
  );
}
