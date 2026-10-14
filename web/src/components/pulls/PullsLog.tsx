"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyBox } from "@/components/bits";
import { JobTable } from "@/components/jobs/JobTable";
import { useApp, useNow } from "@/components/shell/AppProvider";
import { getJson } from "@/lib/client";
import { ago, clock, dayName } from "@/lib/format";
import type { Pull, PullsResponse } from "@/lib/types";

const PAGE = 30;

/** What a pull read as well as what was new in it. "31 postings seen"
 *  was once read as ace having looked at 31 postings, when it had read
 *  483 boards and 31 of their postings were new. */
function checked(s: Pull): string {
  const n = s.jobs_discovered || 0;
  if (!s.boards_checked) return n ? `${n.toLocaleString("en-US")} new posting${n === 1 ? "" : "s"}` : "nothing new to read";
  return (
    `${n.toLocaleString("en-US")} new · ${s.boards_checked.toLocaleString("en-US")} board${s.boards_checked === 1 ? "" : "s"}, ` +
    `${(s.postings_checked || 0).toLocaleString("en-US")} postings checked`
  );
}

function AlertsButton() {
  const { toast } = useApp();
  const [state, setState] = useState<"unsupported" | "on" | "off" | null>(null);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState(typeof Notification !== "function" ? "unsupported" : Notification.permission === "granted" ? "on" : "off");
  }, []);
  if (state === null || state === "unsupported") return null;
  if (state === "on") return <span className="pl-alerts on">Desktop alerts on</span>;
  return (
    <button
      className="btn pl-alerts"
      onClick={async () => {
        const p = await Notification.requestPermission();
        setState(p === "granted" ? "on" : "off");
        toast(
          p === "granted"
            ? "Desktop alerts on. Keep an ace tab open, in the background is fine."
            : "Alerts are blocked for this site in the browser's settings.",
        );
      }}
    >
      Turn on desktop alerts
    </button>
  );
}

export function PullsAlerts() {
  return <AlertsButton />;
}

export function PullsLog({ initial }: { initial: Pull[] }) {
  const { tz } = useApp();
  const now = useNow();
  const [sessions, setSessions] = useState(initial);
  const [exhausted, setExhausted] = useState(initial.length < PAGE);
  const [loading, setLoading] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setSessions((s) => [...initial, ...s.slice(initial.length)]), [initial]);

  const loadOlder = async () => {
    const oldest = sessions[sessions.length - 1]?.started_at;
    if (!oldest || loading) return;
    setLoading(true);
    try {
      const d = await getJson<PullsResponse>(
        "/api/sessions",
        new URLSearchParams({ limit: String(PAGE), jobs_per_session: "6", before: oldest }),
      );
      setSessions((s) => [...s, ...d.sessions]);
      setExhausted(d.sessions.length < PAGE);
    } finally {
      setLoading(false);
    }
  };

  if (!sessions.length)
    return <EmptyBox title="Nothing recorded yet">ace records a check once it has looked at its sources.</EmptyBox>;

  const days: { day: string; rows: Pull[] }[] = [];
  for (const s of sessions) {
    const d = dayName(s.started_at, tz, now);
    if (!days.length || days[days.length - 1].day !== d) days.push({ day: d, rows: [] });
    days[days.length - 1].rows.push(s);
  }

  return (
    <>
      {days.map((g) => {
        const seen = g.rows.reduce((a, b) => a + b.jobs_discovered, 0);
        const qual = g.rows.reduce((a, b) => a + b.qualifying_discovered, 0);
        return (
          <section className="pl-day" key={g.day}>
            <header className="pl-day-h">
              <h2 className="pl-day-t">{g.day}</h2>
              <span className="pl-day-m">
                {g.rows.length} check{g.rows.length === 1 ? "" : "s"}
              </span>
              <span className="pl-day-m">{seen.toLocaleString("en-US")} new postings</span>
              <span className="pl-day-m strong">{qual} passed your filters</span>
            </header>
            <div className="pl-runs">
              {g.rows.map((s) => {
                const jobs = s.jobs || [];
                const counted = s.qualifying_discovered > 0;
                // Expandable only when something is behind it now; the
                // count is history and cannot change.
                const hit = counted && jobs.length > 0;
                const open = openId === s.id;
                const hidden = Math.max(0, s.qualifying_discovered - jobs.length);
                const label = counted
                  ? `${s.qualifying_discovered} passed`
                  : s.jobs_discovered
                    ? "nothing new"
                    : "no new postings";
                return (
                  <div key={s.id} className={`pl-run${counted ? " hit" : ""}${open ? " open" : ""}`}>
                    <button className="pl-row" disabled={!hit} onClick={() => setOpenId(open ? null : s.id)}>
                      <span className="pl-caret">{hit ? (open ? "▾" : "▸") : "·"}</span>
                      <span className="pl-time">
                        {clock(s.started_at, tz)}
                        <span className="pl-since"> + 15m</span>
                      </span>
                      <span className={`pl-badge${counted ? " hit" : ""}`}>{label}</span>
                      <span className="pl-seen">{checked(s)}</span>
                      <span className="pl-ago" suppressHydrationWarning>
                        {ago(s.finished_at || s.started_at, now)}
                      </span>
                    </button>
                    {open ? (
                      <div className="pl-jobs">
                        <JobTable
                          items={jobs}
                          total={jobs.length}
                          offset={0}
                          page="pulls"
                          sorts={[]}
                          group={false}
                          emptyState={null}
                          sortLinks={{}}
                          bare
                        />
                        <div className="pl-actions">
                          <Link className="link-btn" href={`/app/opportunities?view=latest&session=${s.id}`}>
                            {hidden > 0 ? `Show ${hidden} more in the Queue` : "Open these in the Queue"}
                          </Link>
                        </div>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}
      {exhausted ? (
        <div className="tail">End of recorded activity</div>
      ) : (
        <button className="link-btn pl-loadmore" onClick={loadOlder}>
          {loading ? "Loading…" : "Load older activity"}
        </button>
      )}
    </>
  );
}
