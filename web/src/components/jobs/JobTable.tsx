"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CompanyCell, MatchCell, StatusBadge } from "@/components/bits";
import { Icon } from "@/components/Icon";
import { useApp, useNow, withPatch } from "@/components/shell/AppProvider";
import {
  EXPORT_NOTE,
  ago,
  beforeNote,
  clean,
  clock,
  expFit,
  exportCaveat,
  isDone,
  parseDate,
  shortDate,
  tierMove,
  unscoredReason,
} from "@/lib/format";
import type { Job } from "@/lib/types";

import { useMarks, type MarkKey } from "./useMarks";

// Several companies repost one role once per team or vertical. Each is a
// real, separately appliable posting, so nothing is discarded, but nine
// near-identical rows are one decision. Titles sharing a stem with two
// or more others on the page collapse under one header row.
const GROUP_MIN = 3;

function jobStem(title: string): string {
  // Split on the raw title: cleaning turns "Agent - Legal" into
  // "Agent, Legal", and the vertical is what varies between reposts.
  const raw = (title || "").replace(/\s*\([^)]*\)\s*$/, "").trim();
  const parts = raw.split(/\s+[-–—]\s+/);
  return clean(parts.length > 1 ? parts[0] : raw).toLowerCase();
}

function groupKey(j: Job): string {
  return `${j.company || ""}|${jobStem(j.title)}`;
}

function representative(members: Job[]): Job {
  return members.slice().sort((a, b) => {
    const am = a.match_score ?? -1;
    const bm = b.match_score ?? -1;
    if (bm !== am) return bm - am;
    return (parseDate(a.first_seen_at)?.getTime() ?? 0) - (parseDate(b.first_seen_at)?.getTime() ?? 0);
  })[0];
}

/** Everything listed is applicable; the line separates postings that say
 *  they suit an early-career engineer from ones that say nothing. */
function inBand(j: Job): boolean {
  return Boolean(j.is_early_career || (j.required_experience_years != null && j.required_experience_years < 4));
}

type Line =
  | { kind: "job"; job: Job; member?: boolean }
  | { kind: "group"; key: string; members: Job[]; lead: Job }
  | { kind: "read"; at: Date }
  | { kind: "band"; rest: number };

function BeforeBadge({ job, tz }: { job: Job; tz: string }) {
  return (
    <span className="badge before" title={beforeNote(job, tz)}>
      Applied before {"·"} {shortDate(job.applied_before!.applied_at, tz)}
    </span>
  );
}

function StatusCell({ job, prevVisit, tz }: { job: Job; prevVisit: Date | null; tz: string }) {
  if (job.application_status)
    return <StatusBadge status={job.application_status} suffix={job.applied_at ? shortDate(job.applied_at, tz) : undefined} />;
  if (job.applied_before) return <BeforeBadge job={job} tz={tz} />;
  const move = tierMove(job, prevVisit);
  if (move) return <span className="badge move">{move}</span>;
  const seen = parseDate(job.first_seen_at);
  if (prevVisit && seen && seen > prevVisit) return <span className="badge new">NEW</span>;
  if (job.is_saved) return <span className="badge saved">Saved</span>;
  if (job.review_state === "reviewed") return <span className="badge">Reviewed</span>;
  return null;
}

export function JobTable({
  items,
  total,
  offset,
  page,
  sorts,
  group,
  emptyState,
  sortLinks,
  bare = false,
}: {
  items: Job[];
  total: number;
  offset: number;
  page: string;
  sorts: string[];
  group: boolean;
  emptyState: React.ReactNode;
  /** Where clicking each sortable header leads: that sort toggled. */
  sortLinks: Record<string, string>;
  /** No header row, for a short list inside another page. */
  bare?: boolean;
}) {
  const router = useRouter();
  const { patches, hidden, prevVisit, tz } = useApp();
  const now = useNow();
  const { mark } = useMarks(page);
  const [selected, setSelected] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const rows = useMemo(
    () => items.filter((j) => !hidden.has(j.id)).map((j) => withPatch(j, patches)),
    [items, hidden, patches],
  );

  const lines = useMemo<Line[]>(() => {
    const groups: Record<string, Job[]> = {};
    if (group) for (const j of rows) (groups[groupKey(j)] ??= []).push(j);
    let readAt = -1;
    if (sorts[0] === "newest" && prevVisit)
      readAt = rows.findIndex((j) => (parseDate(j.first_seen_at)?.getTime() ?? 0) <= prevVisit.getTime());
    let bandAt = -1;
    if (sorts.includes("experience_fit_first"))
      for (let b = 1; b < rows.length; b++)
        if (inBand(rows[b - 1]) && !inBand(rows[b])) {
          bandAt = b;
          break;
        }
    const out: Line[] = [];
    const done = new Set<string>();
    rows.forEach((j, i) => {
      if (i === readAt && prevVisit) out.push({ kind: "read", at: prevVisit });
      if (i === bandAt) out.push({ kind: "band", rest: Math.max(0, total - offset - bandAt) });
      const key = groupKey(j);
      const members = groups[key];
      if (!members || members.length < GROUP_MIN) {
        out.push({ kind: "job", job: j });
        return;
      }
      if (done.has(key)) return;
      done.add(key);
      out.push({ kind: "group", key, members, lead: representative(members) });
      if (expanded[key]) members.forEach((m) => out.push({ kind: "job", job: m, member: true }));
    });
    return out;
  }, [rows, group, sorts, prevVisit, total, offset, expanded]);

  // The rows a person can see, in order: keyboard navigation walks
  // these, so "next" never lands inside a collapsed group.
  const visible = useMemo(
    () =>
      lines.flatMap((l) => (l.kind === "job" ? [l.job] : l.kind === "group" && !expanded[l.key] ? [l.lead] : [])),
    [lines, expanded],
  );

  const open = useCallback((id: number) => router.push(`/app/jobs/${id}`), [router]);

  const step = useCallback(
    (d: number) => {
      if (!visible.length) return;
      const i = visible.findIndex((j) => j.id === selected);
      const n = Math.max(0, Math.min(visible.length - 1, i < 0 ? 0 : i + d));
      setSelected(visible[n].id);
      requestAnimationFrame(() =>
        document.querySelector(`.row[data-id="${visible[n].id}"]`)?.scrollIntoView({ block: "nearest" }),
      );
    },
    [visible, selected],
  );

  useEffect(() => {
    if (bare) return;
    const onKey = (e: KeyboardEvent) => {
      if (/^(INPUT|TEXTAREA|SELECT)$/.test((e.target as Element)?.tagName ?? "")) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (document.querySelector(".palette-wrap,.pop,.ab")) return;
      const job = visible.find((j) => j.id === selected);
      const k = e.key;
      if (k === "ArrowDown" || k === "j") {
        e.preventDefault();
        step(1);
      } else if (k === "ArrowUp" || k === "k") {
        e.preventDefault();
        step(-1);
      } else if (!job) return;
      else if (k === "Enter") open(job.id);
      else if (k === "o") window.open(job.official_url, "_blank", "noopener");
      else if (k === "a") void mark(job, "applied");
      else if (k === "e" || k === "x") {
        const key: MarkKey = k === "e" ? "reviewed" : "dismissed";
        const was = job.review_state === key;
        void mark(job, key);
        if (!was) step(1);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [visible, selected, step, open, mark, bare]);

  if (!rows.length) return <>{emptyState}</>;

  const actions = (j: Job) => (
    <span className="acts">
      {(
        [
          ["reviewed", "check", "Reviewed", j.review_state === "reviewed"],
          ["dismissed", "x", "Not relevant", j.review_state === "dismissed"],
        ] as const
      ).map(([key, icon, label, on]) => (
        <button
          key={key}
          className={`iconbtn${on ? " on" : ""}`}
          data-mark={key}
          aria-label={label}
          onClick={(e) => {
            e.stopPropagation();
            void mark(j, key);
          }}
        >
          <Icon name={icon} />
        </button>
      ))}
      <button
        className={`iconbtn${j.applied_at ? " on" : ""}`}
        data-mark="applied"
        title={j.applied_at ? `Applied ${shortDate(j.applied_at, tz)}` : "Mark applied (a)"}
        aria-label="Mark applied"
        aria-pressed={Boolean(j.applied_at)}
        onClick={(e) => {
          e.stopPropagation();
          void mark(j, "applied");
        }}
      >
        <Icon name="briefcase" />
      </button>
      <a
        className="iconbtn"
        href={j.official_url}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Open posting"
        onClick={(e) => e.stopPropagation()}
      >
        <Icon name="ext" />
      </a>
    </span>
  );

  const head = (label: string, key: string | null, cls: string) => {
    if (!key || !sortLinks[key]) return <th className={cls}>{label}</th>;
    const i = sorts.indexOf(key);
    return (
      <th
        className={`sortable ${cls}${i >= 0 ? " th-on" : ""}`}
        onClick={() => router.push(sortLinks[key], { scroll: false })}
        aria-sort={i >= 0 ? "descending" : undefined}
      >
        {label}
        {i >= 0 ? <span className="th-i">{i + 1}</span> : null}
      </th>
    );
  };

  return (
    <table className={bare ? "tbl pl-tbl" : "tbl"} id={bare ? undefined : "main"}>
      <thead hidden={bare}>
        <tr>
          <th className="c-rail" />
          {head("Company", "company", "c-co")}
          {head("Role", null, "c-title")}
          {head("Location", null, "c-loc")}
          {head("Experience", "new_grad_first", "c-exp")}
          {head("Match", "best_match", "c-match")}
          {head("Status", null, "c-status")}
          {head("Seen", "newest", "c-when")}
          <th className="c-act" />
        </tr>
      </thead>
      <tbody>
        {lines.map((l) => {
          if (l.kind === "read")
            return (
              <tr className="readline" key="read">
                <td colSpan={9}>
                  <span>Last visit, {clock(l.at, tz)}</span>
                </td>
              </tr>
            );
          if (l.kind === "band")
            return (
              <tr className="bandline" key="band">
                <td colSpan={9}>
                  <span>
                    Below here, experience not stated{l.rest ? ` · ${l.rest.toLocaleString("en-US")} more` : ""}
                  </span>
                </td>
              </tr>
            );
          if (l.kind === "group") {
            const isOpen = Boolean(expanded[l.key]);
            const tier = l.lead.company_tier || "OTHER";
            const applied = l.members.filter((j) => j.applied_at || j.applied_before).length;
            return (
              <tr
                key={`g:${l.key}`}
                className={`row grp-head t-${tier}`}
                data-id={l.lead.id}
                tabIndex={0}
                aria-selected={selected === l.lead.id}
                aria-expanded={isOpen}
                onClick={() => setExpanded((x) => ({ ...x, [l.key]: !x[l.key] }))}
              >
                <td className="c-rail">
                  <div className={`rail t-${tier}`} />
                </td>
                <td className="c-co">
                  <CompanyCell name={l.lead.company} tier={tier} />
                </td>
                <td className="c-title" colSpan={6}>
                  <span className="grp-caret">{isOpen ? "▾" : "▸"}</span> {clean(l.lead.title)}
                  <span className="grp-n">{l.members.length} similar openings</span>
                  {applied ? (
                    <span
                      className="badge before grp-applied"
                      title={`${applied} of these ${l.members.length} openings are ones you applied to, or re-listings of one. Open the group to see which.`}
                    >
                      {applied} already applied
                    </span>
                  ) : null}
                </td>
                <td className="c-act" />
              </tr>
            );
          }
          const j = l.job;
          const fit = expFit(j);
          const tier = j.company_tier || "OTHER";
          return (
            <tr
              key={j.id}
              className={`row t-${tier}${isDone(j) ? " done" : ""}${l.member ? " grp-member" : ""}`}
              data-id={j.id}
              tabIndex={0}
              aria-selected={selected === j.id}
              onClick={() => open(j.id)}
              onFocus={() => setSelected(j.id)}
            >
              <td className="c-rail">
                <div className={`rail t-${tier}`} />
              </td>
              <td className="c-co">
                <CompanyCell name={j.company} tier={tier} />
              </td>
              <td className="c-title">
                <Link className="j-title" href={`/app/jobs/${j.id}`} onClick={(e) => e.stopPropagation()}>
                  {clean(j.title)}
                </Link>
                {exportCaveat(j) ? (
                  <span className="badge export" title={EXPORT_NOTE}>
                    Export check
                  </span>
                ) : null}
              </td>
              <td className="c-loc">{clean(j.location)}</td>
              <td className="c-exp">
                <span className={fit.cls}>{fit.text}</span>
              </td>
              <td className="c-match">
                <MatchCell score={j.match_score} reason={unscoredReason(j)} />
              </td>
              <td className="c-status">
                <StatusCell job={j} prevVisit={prevVisit} tz={tz} />
              </td>
              <td className="c-when" suppressHydrationWarning>
                {ago(j.first_seen_at, now)}
              </td>
              <td className="c-act">{actions(j)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

