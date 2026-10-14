"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { getJson } from "@/lib/client";
import { clean } from "@/lib/format";
import type { JobPage } from "@/lib/types";

import { useApp } from "./AppProvider";

interface Command {
  label: string;
  href?: string;
  run?: () => void;
}

/** Ctrl or Cmd+K: every destination and the common views, plus roles by
 *  company or title, by keyboard. */
export function CommandPalette() {
  const { paletteOpen } = useApp();
  // Mounted only while open, so every opening starts empty.
  return paletteOpen ? <PaletteDialog /> : null;
}

function PaletteDialog() {
  const { setPaletteOpen, setAnswersOpen, cycleTheme } = useApp();
  const router = useRouter();
  const [term, setTerm] = useState("");
  const [index, setIndex] = useState(0);

  const commands = useMemo<Command[]>(
    () => [
      { label: "Go to Opportunities", href: "/app/opportunities" },
      { label: "Go to Discovery activity", href: "/app/activity" },
      { label: "Go to Applications", href: "/app/applications" },
      { label: "Go to Archive", href: "/app/archive" },
      { label: "Go to Resume Studio", href: "/app/resume-studio" },
      { label: "Go to Skills", href: "/app/insights/skills" },
      { label: "Go to Answers", href: "/app/answers" },
      { label: "Show saved roles", href: "/app/saved" },
      { label: "Go to Coverage", href: "/app/coverage" },
      { label: "Go to Settings", href: "/app/settings" },
      { label: "Show all opportunities", href: "/app/opportunities" },
      { label: "Show strong matches", href: "/app/opportunities?view=matched" },
      { label: "Show new since your last visit", href: "/app/opportunities?view=new" },
      { label: "Show latest discoveries", href: "/app/opportunities?view=latest" },
      { label: "Filter to big tech", href: "/app/opportunities?tier=BIG_TECH" },
      { label: "Filter to big tech and top tier", href: "/app/opportunities?tier=BIG_TECH,TOP_TIER" },
      { label: "Sort by best match", href: "/app/opportunities?sort=best_match" },
      { label: "Sort new grad first, then best match", href: "/app/opportunities?sort=new_grad_first,best_match" },
      { label: "Sort roles that fit my experience first", href: "/app/opportunities?sort=experience_fit_first,unapplied_first,best_match" },
      { label: "Sort big tech first, then best match", href: "/app/opportunities?sort=big_tech_first,best_match" },
      { label: "Show early career only", href: "/app/opportunities?early=1" },
      { label: "Show new grad only", href: "/app/opportunities?newgrad=1" },
      { label: "Show the last 15 days only", href: "/app/opportunities?recent=1" },
      { label: "Include openings 30+ days old", href: "/app/opportunities?old=1" },
      { label: "Clear all filters", href: "/app/opportunities" },
      { label: "Open your answers", run: () => setAnswersOpen(true) },
      { label: "Edit your answers", href: "/app/answers" },
      { label: "Upload resume", href: "/app/resume-studio" },
      { label: "Switch theme", run: cycleTheme },
    ],
    [setAnswersOpen, cycleTheme],
  );

  // Roles matching what is typed, by company or title, under the commands.
  const [jobs, setJobs] = useState<Command[]>([]);
  useEffect(() => {
    const q = term.trim();
    if (q.length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setJobs([]);
      return;
    }
    const t = setTimeout(() => {
      getJson<JobPage>("/api/jobs", new URLSearchParams({ q, limit: "6", sort: "best_match" }))
        .then((d) =>
          setJobs(d.items.map((j) => ({ label: `Open ${j.company}, ${clean(j.title)}`, href: `/app/jobs/${j.id}` }))),
        )
        .catch(() => setJobs([]));
    }, 200);
    return () => clearTimeout(t);
  }, [term]);

  const hits = [...commands.filter((c) => c.label.toLowerCase().includes(term.toLowerCase())), ...jobs];
  const at = Math.min(index, Math.max(0, hits.length - 1));

  const run = (c: Command | undefined) => {
    setPaletteOpen(false);
    if (!c) return;
    if (c.href) router.push(c.href);
    c.run?.();
  };

  return (
    <div
      className="palette-wrap"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) setPaletteOpen(false);
      }}
    >
      <div className="palette" role="dialog" aria-modal="true" aria-label="Command palette">
        <input
          id="pal-q"
          autoFocus
          type="text"
          placeholder="Type a command, a company or a role"
          autoComplete="off"
          aria-label="Command"
          value={term}
          onChange={(e) => {
            setTerm(e.target.value);
            setIndex(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setIndex(Math.min(hits.length - 1, at + 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setIndex(Math.max(0, at - 1));
            } else if (e.key === "Enter") {
              e.preventDefault();
              run(hits[at]);
            } else if (e.key === "Escape") {
              e.preventDefault();
              e.stopPropagation();
              setPaletteOpen(false);
            }
          }}
        />
        <div className="palette-list">
          {hits.length ? (
            hits.map((c, i) => (
              <button key={`${c.label}|${c.href ?? ""}`} className={`pal-opt${i === at ? " on" : ""}`} onClick={() => run(c)}>
                {c.label}
              </button>
            ))
          ) : (
            <div className="pal-none">No matching command</div>
          )}
        </div>
      </div>
    </div>
  );
}
