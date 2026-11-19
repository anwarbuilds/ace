import Form from "next/form";
import Link from "next/link";
import type { ReactNode } from "react";

import { CompanyIdentity } from "@/components/CompanyIdentity";
import { AddCompany } from "@/components/coverage/AddCompany";
import { clean, shortDate } from "@/lib/format";
import type {
  CapacityReport,
  CountGroup,
  CountingReport,
  Coverage,
  CoverageGap,
  HostsReport,
  LeadState,
  LeadsReport,
  RecallMissed,
  RecallReport,
  ScheduleReport,
  SourcesReport,
} from "@/lib/types";

const n = (value: number) => value.toLocaleString("en-US");

const STATE_TONE: Record<LeadState, string> = {
  polling: "cov-good",
  waiting: "new",
  checking: "cov-plain",
  dormant: "cov-plain",
  noreader: "cov-warn",
  refused: "cov-bad",
  agency: "cov-plain",
};

const STATUS_TONE: Record<SourcesReport["rows"][number]["status"], string> = {
  working: "cov-good",
  first_read: "new",
  dark: "cov-bad",
  says_no: "cov-warn",
};

const TERMS: Record<HostsReport["groups"][number]["terms"]["verdict"], [string, string]> = {
  allowed: ["Allowed", "cov-good"],
  restricted: ["Restricted", "cov-bad"],
  unclear: ["Unclear", "cov-warn"],
  not_read: ["Not read", "cov-plain"],
};

function how(seconds: number | null): string {
  if (!seconds) return "";
  if (seconds <= 900) return "Every 15 min";
  if (seconds < 3600) return `Every ${Math.round(seconds / 60)} min`;
  if (seconds === 3600) return "Hourly";
  if (seconds < 86400) return `Every ${Math.round(seconds / 3600)} h`;
  return "Daily";
}

function readWhen(iso: string | null, tz: string): string {
  if (!iso) return "Not yet";
  const age = Date.now() - new Date(iso).getTime();
  if (age < 3_600_000) return `${Math.max(1, Math.round(age / 60_000))} min ago`;
  if (age < 86_400_000) return `${Math.round(age / 3_600_000)} h ago`;
  return shortDate(iso, tz);
}

function dayOf(iso: string | null, tz: string): string {
  if (!iso) return "Not yet";
  return new Date(iso).getTime() <= Date.now() ? "Today" : shortDate(iso, tz);
}

function Section({ id, title, intro, children }: { id: string; title: string; intro?: ReactNode; children: ReactNode }) {
  return (
    <section className="cov-section" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      {intro ? <p className="why">{intro}</p> : null}
      {children}
    </section>
  );
}

function Stat({ value, label, note, href }: { value: string; label: string; note?: string; href?: string }) {
  const body = (
    <>
      <strong>{value}</strong>
      <span>{label}</span>
      {note ? <small>{note}</small> : null}
    </>
  );
  return href ? (
    <Link className="cov-stat" href={href}>
      {body}
    </Link>
  ) : (
    <div className="cov-stat">{body}</div>
  );
}

function minutes(value: number): string {
  if (value < 60) return `${Math.max(1, Math.round(value))} min`;
  const hours = value / 60;
  return `${hours < 10 ? hours.toFixed(1) : Math.round(hours)} h`;
}

// Can ace keep up? Three numbers the scheduler already records, so the owner
// sees capacity before any board is added (OPS-05).
function Capacity({ c }: { c: CapacityReport | null }) {
  if (!c) {
    return <p className="why">Whether ace is keeping up could not be loaded just now. Refresh to try again.</p>;
  }
  const typical = c.new_jobs.typical_minutes;
  const nineInTen = c.new_jobs.nine_in_ten_minutes;
  return (
    <section className="cov-card cov-capacity" aria-labelledby="cov-capacity">
      <h2 id="cov-capacity">Can ace keep up?</h2>
      <p className="why">How much reading ace does, and how fast new jobs reach you. ace checks this before adding boards.</p>
      <div className="cov-stats">
        <Stat
          value={n(c.reads_last_hour)}
          label="Reads in the last hour"
          note={`Your boards ask for about ${n(c.reads_asked_per_hour)} an hour`}
        />
        <Stat
          value={`${n(c.boards_on_time)} of ${n(c.boards)}`}
          label="Boards read on time"
          note="Within one and a half times their planned gap"
        />
        <Stat
          value={typical === null ? "Not yet" : `About ${minutes(typical)}`}
          label="New jobs reach you in"
          note={
            typical === null || nineInTen === null
              ? "Too few new jobs with a real posting time in the last day to tell"
              : `Typical. 9 in 10 within ${minutes(nineInTen)}, on boards that give a real posting time`
          }
        />
      </div>
      <p className={`cov-capacity-line ${c.keeping_up ? "cov-good" : "cov-warn"}`}>{c.status_label}</p>
    </section>
  );
}

const pct = (part: number, whole: number) => (whole ? Math.round((part / whole) * 100) : 0);

const GOAL = 98;

function monthDay(day: string | null): string {
  if (!day) return "";
  const [, month, date] = day.split("-").map(Number);
  return new Date(Date.UTC(2000, month - 1, date)).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

function Trend({ points }: { points: { day: string; listed: number; found: number }[] }) {
  const shares = points.map((p) => (p.listed ? (p.found / p.listed) * 100 : 0));
  if (shares.length < 2) {
    return <p className="why">The line starts once ace has checked on two days.</p>;
  }
  const low = Math.max(0, Math.min(...shares, GOAL) - 2);
  const y = (share: number) => 66 - ((share - low) / (100 - low)) * 60;
  const x = (i: number) => (i / (shares.length - 1)) * 260;
  const first = shares[0];
  const last = shares[shares.length - 1];
  return (
    <div className="cov-recall-trend">
      <span>Score each day, last {points.length} days</span>
      <svg viewBox="0 0 260 70" role="img" aria-label={`Daily score from ${Math.round(first)}% to ${Math.round(last)}% over ${points.length} days`}>
        <line x1="0" x2="260" y1={y(GOAL)} y2={y(GOAL)} className="cov-recall-goal" />
        <polyline points={shares.map((s, i) => `${x(i).toFixed(1)},${y(s).toFixed(1)}`).join(" ")} className="cov-recall-line" />
      </svg>
      <div className="cov-recall-axis">
        <span>
          {monthDay(points[0].day)}: {Math.round(first)}%
        </span>
        <span>dashed line: goal</span>
        <span>Today: {Math.round(last)}%</span>
      </div>
    </div>
  );
}

// Did ace find the jobs on the test lists? Two public new grad lists ace
// never reads act as an answer key, checked once a day (REC-01, REC-03).
function Recall({ r, tz }: { r: RecallReport | null; tz: string }) {
  if (!r) {
    return <p className="why">The test list score could not be loaded just now. Refresh to try again.</p>;
  }
  if (!r.checked) {
    return (
      <section className="cov-card cov-recall" aria-labelledby="cov-recall">
        <h2 id="cov-recall">Did ace find the jobs on the test lists?</h2>
        <p className="why">
          Two public new grad lists that ace never reads are used only to check ace. The first check runs this morning.
        </p>
      </section>
    );
  }
  const t = r.total;
  const share = pct(t.found, t.listed);
  const separate = !r.leaks.boards && !r.leaks.jobs && !r.leaks.leads;
  const unreadable = r.lists.filter((l) => l.error);
  const shown = r.missed.slice(0, 8);
  const rest = r.missed.slice(8);
  const row = (m: RecallMissed, i: number) => (
    <div className="cov-row cov-recall-miss" key={`${m.list}-${m.company}-${m.title}-${i}`}>
      <span className="cov-name">
        <CompanyIdentity name={m.company}>
          <b>{m.company}</b>, {clean(m.title)}
        </CompanyIdentity>
      </span>
      <span className="cov-n">
        {r.lists.find((l) => l.key === m.list)?.label ?? m.list}
        {m.listed_on ? `, ${monthDay(m.listed_on)}` : ""}
      </span>
      <span className="cov-recall-why">{m.reason}</span>
    </div>
  );
  return (
    <section className="cov-card cov-recall" aria-labelledby="cov-recall">
      <div className="cov-recall-head">
        <div>
          <h2 id="cov-recall">Did ace find the jobs on the test lists?</h2>
          <p className="why">
            Two public new grad lists that ace never reads. They are used only to check ace, so the score is honest. Checked
            once a day, last {readWhen(r.checked_at, tz)}.
          </p>
        </div>
        <div className="cov-recall-goaltext">
          Goal
          <b>{GOAL}% within a day</b>
        </div>
      </div>

      <div className="cov-recall-top">
        <div className="cov-recall-score">
          <div className="cov-recall-big">
            <strong>
              {n(t.found)} of {n(t.listed)}
            </strong>
            <span>
              roles found <b>({share}%)</b>
            </span>
          </div>
          <div
            className="cov-recall-bar"
            role="img"
            aria-label={`${n(t.board)} from the employer's board, ${n(t.feed)} only as a feed copy, ${n(t.missed)} missed`}
          >
            <i className="is-board" style={{ width: `${(t.board / Math.max(1, t.listed)) * 100}%` }} />
            <i className="is-feed" style={{ width: `${(t.feed / Math.max(1, t.listed)) * 100}%` }} />
            <i className="is-missed" style={{ width: `${(t.missed / Math.max(1, t.listed)) * 100}%` }} />
          </div>
          <div className="cov-recall-legend">
            <div>
              <b>
                <i className="is-board" aria-hidden="true" />
                {n(t.board)}
              </b>
              <span>From the employer&rsquo;s board</span>
              <small>ace has it from the company&rsquo;s own job board. The best case.</small>
            </div>
            <div>
              <b>
                <i className="is-feed" aria-hidden="true" />
                {n(t.feed)}
              </b>
              <span>Only as a feed copy</span>
              <small>ace has it only because a list it reads (Simplify or Zapply) showed it.</small>
            </div>
            <div>
              <b>
                <i className="is-missed" aria-hidden="true" />
                {n(t.missed)}
              </b>
              <span>Missed</span>
              <small>ace does not have it at all. Listed below with the reason.</small>
            </div>
          </div>
        </div>
        <Trend points={r.trend} />
      </div>

      <div className="cov-stats">
        <Stat
          value={t.timed ? `${n(t.within_day)} of ${n(t.timed)}` : "Not yet"}
          label="Found within a day of the list"
          note={
            t.timed
              ? `Roles listed in the last two weeks. ace saw ${n(t.seen_first)} before the list did.`
              : "No role listed in the last two weeks yet"
          }
        />
        <Stat
          value={`${n(t.hidden)} of ${n(t.found)}`}
          label="Found, then hidden by your filters"
          note={t.hidden_reasons[0] ? `Most often: ${t.hidden_reasons[0].reason}` : "None hidden"}
        />
        <Stat
          value={separate ? "Yes" : "No"}
          label="Test lists kept separate"
          note={separate ? "ace never read either list to find jobs." : "A board, job or lead came from a test list. The score is not honest until it is removed."}
        />
      </div>

      <div className="cov-recall-lists">
        <h3>By list</h3>
        {r.lists.map((l) => (
          <div className="cov-row" key={l.key}>
            <span className="cov-name">{l.label}</span>
            <span className="cov-n">{l.links === "employer" ? "links the employer's own posting" : "short links, matched by company and title"}</span>
            <span className="cov-pct">{l.error ? "Could not be read today" : `${n(l.found ?? 0)} of ${n(l.listed ?? 0)}`}</span>
          </div>
        ))}
        {unreadable.length ? (
          <p className="why">A list that could not be read is left out of today&rsquo;s score, never counted as misses.</p>
        ) : null}
      </div>

      <div className="cov-recall-lists">
        <h3>Missed roles ({n(r.missed.length)})</h3>
        {r.missed.length ? (
          <>
            {shown.map(row)}
            {rest.length ? (
              <details className="cov-recall-more">
                <summary>Show all {n(r.missed.length)} missed roles</summary>
                {rest.map((m, i) => row(m, i + shown.length))}
              </details>
            ) : null}
          </>
        ) : (
          <p className="why">ace found every role on both lists today.</p>
        )}
      </div>
    </section>
  );
}

function Split({ id, title, total, groups, tones }: { id: string; title: string; total: number; groups: CountGroup[]; tones: Record<string, string> }) {
  return (
    <div className="cov-count">
      <h3 id={id}>
        {title} <span>{n(total)}</span>
      </h3>
      <div
        className="cov-count-bar"
        role="img"
        aria-label={`${title}: ${groups.map((g) => `${n(g.count)} ${g.label.toLowerCase()}`).join(", ")}`}
      >
        {groups
          .filter((g) => g.count)
          .map((g) => (
            <i key={g.key} className={tones[g.key] ?? "is-other"} style={{ width: `${(g.count / Math.max(1, total)) * 100}%` }} />
          ))}
      </div>
      <div className="cov-count-rows">
        {groups.map((g) => (
          <div className="cov-count-row" key={g.key} title={g.meaning}>
            <i className={tones[g.key] ?? "is-other"} aria-hidden="true" />
            <span className="cov-count-label">{g.label}</span>
            <span className="cov-count-meaning">{g.meaning}</span>
            <b>{n(g.count)}</b>
          </div>
        ))}
      </div>
    </div>
  );
}

const BOARD_TONES: Record<string, string> = {
  working: "is-good",
  stale: "is-warn",
  unread: "is-quiet",
  refused: "is-bad",
  off: "is-off",
};

const COMPANY_TONES: Record<string, string> = {
  polling: "is-good",
  waiting: "is-new",
  dormant: "is-quiet",
  checking: "is-quiet",
  noreader: "is-warn",
  refused: "is-bad",
  agency: "is-off",
};

// Every board and every company in exactly one group, so the parts always add
// up to the total shown. Jobs are counted apart (REC-05).
function Counts({ c, tz }: { c: CountingReport | null; tz: string }) {
  if (!c) return <p className="why">The counts could not be loaded just now. Refresh to try again.</p>;
  return (
    <section className="cov-card cov-counts" aria-labelledby="cov-counts">
      <h2 id="cov-counts">Every board, counted once</h2>
      <p className="why">
        Each board and each company sits in exactly one group, so the groups always add up to the total. Companies, boards and
        jobs are counted apart and never added together. Counted {readWhen(c.counted_at, tz)} from ace&rsquo;s own records.
      </p>
      <div className="cov-counts-grid">
        <Split id="cov-count-boards" title="Job boards" total={c.boards.total} groups={c.boards.groups} tones={BOARD_TONES} />
        <Split id="cov-count-companies" title="Companies" total={c.companies.total} groups={c.companies.groups} tones={COMPANY_TONES} />
      </div>
      <p className="cov-note">
        Jobs, counted apart: <b>{n(c.jobs.open)}</b> open jobs on these boards, of which <b>{n(c.jobs.passing)}</b> pass your
        filters.{" "}
        {c.feeds ? (
          <>
            ace also reads {n(c.feeds)} public {c.feeds === 1 ? "list" : "lists"} of many employers&rsquo; jobs, which are not boards
            and are not counted above.
          </>
        ) : null}
      </p>
    </section>
  );
}

// Is reading on schedule? Each hiring site's working boards against their
// planned gap, from what the scheduler already records (FRS-02).
function Schedule({ s }: { s: ScheduleReport | null }) {
  if (!s) return <p className="why">Whether reading is on schedule could not be loaded just now. Refresh to try again.</p>;
  const ago = (value: number) => (value < 1 ? "under 1 min" : minutes(value));
  return (
    <section className="cov-section" aria-labelledby="cov-schedule">
      <h2 id="cov-schedule">Is reading on schedule?</h2>
      <p className="why">
        Each board has a plan, such as every 15 minutes. This is how long ago each site&rsquo;s working boards were last read,
        right now. A board is late after one and a half planned gaps. Boards not read in two days are on the Scoreboard instead.
      </p>
      <p className={`cov-capacity-line ${s.late ? "cov-warn" : "cov-good"}`}>
        Right now {n(s.due_now)} of {n(s.working_boards)} working boards are due and waiting their turn
        {s.due_now ? `; the longest has waited ${ago(s.longest_wait_minutes)} past its plan` : ""}. {n(s.late)} are late.
      </p>
      {s.sites.length ? (
        <div className="cov-table">
          <table>
            <thead>
              <tr>
                <th scope="col">Hiring site</th>
                <th scope="col" className="cov-num">Boards</th>
                <th scope="col">Plan</th>
                <th scope="col" className="cov-num">Typical last read</th>
                <th scope="col" className="cov-num">19 in 20 within</th>
                <th scope="col" className="cov-num">99 in 100 within</th>
                <th scope="col" className="cov-num">Late</th>
              </tr>
            </thead>
            <tbody>
              {s.sites.map((row) => (
                <tr key={row.site}>
                  <th scope="row">{row.site}</th>
                  <td className="cov-num">{n(row.boards)}</td>
                  <td>{row.plan}</td>
                  <td className="cov-num">{ago(row.typical_minutes)} ago</td>
                  <td className="cov-num">{ago(row.p95_minutes)}</td>
                  <td className="cov-num">{ago(row.p99_minutes)}</td>
                  <td className={`cov-num ${row.late ? "cov-late" : ""}`}>{n(row.late)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="why">No board has been read yet.</p>
      )}
    </section>
  );
}

function Pager({ total, offset, limit, href }: { total: number; offset: number; limit: number; href: (offset: number) => string }) {
  if (!total) return null;
  const last = Math.min(offset + limit, total);
  return (
    <div className="cov-pager">
      <span>
        Showing {n(offset + 1)} to {n(last)} of {n(total)}
      </span>
      {offset > 0 ? (
        <Link className="btn btn-secondary" href={href(Math.max(0, offset - limit))}>
          Previous
        </Link>
      ) : null}
      {last < total ? (
        <Link className="btn btn-secondary" href={href(offset + limit)}>
          Next
        </Link>
      ) : null}
    </div>
  );
}

function Finder({ tab, query, kept, label }: { tab: string; query?: string; kept: Record<string, string>; label: string }) {
  return (
    <Form action="/app/coverage" className="cov-find" role="search">
      <input type="hidden" name="tab" value={tab} />
      {Object.entries(kept).map(([key, value]) => (
        <input key={key} type="hidden" name={key} value={value} />
      ))}
      <label className="sr-only" htmlFor={`cov-find-${tab}`}>
        {label}
      </label>
      <input id={`cov-find-${tab}`} type="search" name="q" autoComplete="off" defaultValue={query} placeholder={label} />
      <button className="btn btn-secondary" type="submit">
        Find
      </button>
    </Form>
  );
}

// What is in the way, grouped by what would fix it. A flat list of 154
// names was a wall; "31 are on iCIMS" is a decision waiting to be made.
const GROUPS: [string, string, string][] = [
  ["other_ats", "Use a hiring site ace can't read yet", "Each needs a new reader. The name of the site is shown, so the work is countable."],
  ["no_board_found", "No job board ace recognises", "Usually a careers page that builds itself in the browser, or hiring software run in-house."],
  ["no_postings", "Board is readable, nothing posted today", "ace found and checked the board. It looks again by itself."],
  ["refused", "Found a board, and it named someone else", "A board under the wrong name is harder to notice than a gap, so ace left it alone."],
  ["blocked", "The site turned ace away", "That is their choice, and ace respects it, so these need checking by hand."],
  ["site_unreachable", "No website answered", "They may use another name. Pasting their careers link usually fixes it."],
  ["unprobed", "Not looked at yet", "ace looks at these by itself."],
];

const LATE_BOARD_ADDED = "board added after the feed listed it";
const LATE_REPUBLISHED = "republished after the feed listed it";

function Names({ rows }: { rows: CoverageGap[] }) {
  return (
    <div className="cov-names">
      {rows.map((r) => (
        <span key={r.company} className="cov-name" title={r.detail || ""}>
          <CompanyIdentity name={r.company} />
        </span>
      ))}
    </div>
  );
}

export function ScoreboardTab({
  c,
  leads,
  polling,
  recall,
  counts,
  tz,
}: {
  c: Coverage;
  leads: number;
  polling: number;
  recall: RecallReport | null;
  counts: CountingReport | null;
  tz: string;
}) {
  const by: Record<string, CoverageGap[]> = {};
  for (const r of c.unreached) (by[r.outcome] ??= []).push(r);
  const known = new Set(GROUPS.map(([k]) => k));
  const late = c.caught_late;
  const sponsorAll = c.sponsorship.filter((r) => r.share >= 1).length;

  return (
    <>
      <p className="why cov-lead">
        <b>How well is ace doing?</b> This page is a report card. You don&rsquo;t need to do anything here unless a
        number looks wrong.
      </p>

      <Recall r={recall} tz={tz} />

      <section className="cov-card" aria-labelledby="cov-how">
        <h2 id="cov-how">How ace finds jobs</h2>
        <div className="cov-how">
          <Link href="/app/coverage?tab=leads">
            <small>Step 1</small>
            <strong>Leads</strong>
            <span>Companies ace has heard about, from lists, startup networks and you. This is where you add one.</span>
          </Link>
          <Link href="/app/coverage?tab=sources">
            <small>Step 2</small>
            <strong>Sources</strong>
            <span>The job boards ace really reads, all day. A lead becomes a source once ace can read its board.</span>
          </Link>
          <Link href="/app/opportunities">
            <small>Step 3</small>
            <strong>Pulls and Opportunities</strong>
            <span>New jobs from those boards that pass your filters. This is where you apply.</span>
          </Link>
        </div>
      </section>

      <div className="cov-stats">
        <Stat value={n(leads)} label="Companies ace has heard of" note="Open Leads" href="/app/coverage?tab=leads" />
        <Stat value={n(polling)} label="Companies ace reads" note="Open Sources" href="/app/coverage?tab=sources" />
        <Stat value={`${n(c.reached)} of ${n(c.total)}`} label="Companies on your list ace reads" note="The rest are listed below" />
        <Stat value={n(c.dark.length)} label="Boards that stopped answering" note="Open Sources" href="/app/coverage?tab=sources&show=dark" />
      </div>

      <Counts c={counts} tz={tz} />

      <Section id="cov-gaps" title={`Companies on your list ace can't read yet (${n(c.unreached.length)})`} intro="Grouped by what is in the way, so you can see what would fix each one. Hover a name for the detail.">
        {c.unreached.length ? (
          <>
            {GROUPS.filter(([k]) => by[k]).map(([k, title, note]) => (
              <div className="cov-group" key={k}>
                <div className="cov-group-h">
                  {title} <span className="cov-group-n">{by[k].length}</span>
                </div>
                <p className="why">{note}</p>
                <Names rows={by[k]} />
              </div>
            ))}
            {Object.keys(by)
              .filter((k) => !known.has(k))
              .map((k) => (
                <div className="cov-group" key={k}>
                  <div className="cov-group-h">
                    {k} <span className="cov-group-n">{by[k].length}</span>
                  </div>
                  <Names rows={by[k]} />
                </div>
              ))}
          </>
        ) : (
          <p className="why">ace reads every company on your list.</p>
        )}
      </Section>

      {late && late.count ? (
        <Section
          id="cov-late"
          title={`Jobs ace saw late (${n(late.count)} in the last 14 days)`}
          intro={
            <>
              A public list showed these jobs before ace saw them on the company&rsquo;s own board. Fewer is better.{" "}
              <b>{late.board_added_later}</b> were on a board ace only started reading afterwards, and{" "}
              <b>{late.seen_late}</b> were on a board ace already read, which are ace&rsquo;s to fix.
              {late.republished ? (
                <>
                  {" "}
                  <b>{late.republished}</b> were posted again by the employer, so they are not misses.
                </>
              ) : null}
            </>
          }
        >
          <div className="cov-grid">
            {late.rows.map((x, i) => (
              <div className="cov-row" key={i} title={x.cause}>
                <span className="cov-name">
                  <CompanyIdentity name={x.company}>
                    {x.company}, {clean(x.title)}
                  </CompanyIdentity>
                </span>
                <span className="cov-n">
                  {x.cause === LATE_BOARD_ADDED ? "Board added late" : x.cause === LATE_REPUBLISHED ? "Posted again" : "Saw it late"}
                </span>
                <span className="cov-pct">{x.lag_hours} h</span>
              </div>
            ))}
          </div>
        </Section>
      ) : null}

      {c.feed_only.length ? (
        <Section
          id="cov-feed"
          title={`Jobs ace knows only from public lists (${n(c.feed_only.length)} companies)`}
          intro="ace doesn't read these companies' own boards yet, so it only knows what a public list says."
        >
          <div className="cov-grid">
            {c.feed_only.map((r) => (
              <div className="cov-row" key={r.company}>
                <span className="cov-name">
                  <CompanyIdentity name={r.company} />
                </span>
                <span className="cov-n">{r.board_read ? "Board read, job missing" : "No board yet"}</span>
                <span className="cov-pct">{r.passing}</span>
              </div>
            ))}
          </div>
        </Section>
      ) : null}

      {c.sponsorship.length ? (
        <Section
          id="cov-sponsor"
          title={`Companies that say they won't sponsor a visa (${n(c.sponsorship.length)})`}
          intro={
            <>
              These employers say so on their own postings. ace already filters those jobs out, and this is the same fact
              said once.{sponsorAll ? <> <b>{sponsorAll}</b> say it on every posting ace could read.</> : null}
            </>
          }
        >
          <div className="cov-grid">
            {c.sponsorship.map((r) => (
              <div
                key={r.company}
                className={`cov-row${r.share >= 1 ? " cov-row-all" : ""}`}
                title={`${r.refusing} of ${r.readable} readable postings say no sponsorship`}
              >
                <span className="cov-name">
                  <CompanyIdentity name={r.company} />
                </span>
                <span className="cov-n">
                  {r.refusing} of {r.readable}
                </span>
                <span className="cov-pct">{Math.round(r.share * 100)}%</span>
              </div>
            ))}
          </div>
        </Section>
      ) : null}
    </>
  );
}

export function LeadsTab({ report, tz, state, q, offset }: { report: LeadsReport | null; tz: string; state?: string; q?: string; offset: number }) {
  const href = (next: { state?: string | null; offset?: number }) => {
    const params = new URLSearchParams({ tab: "leads" });
    const chosen = next.state === undefined ? state : next.state;
    if (chosen) params.set("state", chosen);
    if (q) params.set("q", q);
    if (next.offset) params.set("offset", String(next.offset));
    return `/app/coverage?${params.toString()}`;
  };

  return (
    <>
      <p className="why cov-lead">
        <b>Which companies does ace know about?</b> A lead is any company ace has heard of. ace may already read it, or
        it may still need a look. Nothing here is forgotten.
      </p>

      <AddCompany tz={tz} />

      {!report ? (
        <p className="why">The list of companies could not be loaded just now. Refresh to try again.</p>
      ) : (
        <>
          {report.added.length ? (
            <Section id="cov-mine" title="Added by you" intro="Everything you added, and where it is now.">
              <div className="cov-table">
                <table>
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Added</th>
                      <th>Now</th>
                      <th>What&rsquo;s happening</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.added.map((row) => (
                      <tr key={row.company}>
                        <th scope="row">
                          <CompanyIdentity name={row.company} />
                        </th>
                        <td>{shortDate(row.added_at, tz)}</td>
                        <td>
                          <span className={`badge ${STATE_TONE[row.state]}`}>{row.state_label}</span>
                        </td>
                        <td>
                          {row.state === "polling"
                            ? row.last_read_at
                              ? `Read ${readWhen(row.last_read_at, tz)}. ${n(row.jobs)} ${row.jobs === 1 ? "job" : "jobs"}, ${n(row.passing)} ${row.passing === 1 ? "passes" : "pass"} your filters.`
                              : "First read soon."
                            : `${clean(row.reason)} ace looks again on ${shortDate(row.next_check_at, tz)}.`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          ) : null}

          <section className="cov-section" aria-labelledby="cov-ledger">
            <div className="cov-section-head">
              <h2 id="cov-ledger">All companies ace has heard of</h2>
              <Finder tab="leads" query={q} kept={state ? { state } : {}} label="Find a company" />
            </div>
            <nav className="cov-chips" aria-label="Filter by status">
              <Link aria-current={!state ? "true" : undefined} href={href({ state: null })}>
                All <span>{n(report.total)}</span>
              </Link>
              {report.states.map((item) => (
                <Link key={item.state} aria-current={state === item.state ? "true" : undefined} href={href({ state: item.state })}>
                  {item.label} <span>{n(item.leads)}</span>
                </Link>
              ))}
            </nav>
            {report.rows.length ? (
              <div className="cov-table">
                <table>
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Heard from</th>
                      <th>Status</th>
                      <th>What&rsquo;s happening</th>
                      <th>Last looked</th>
                      <th>Next look</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.rows.map((row) => (
                      <tr key={row.company}>
                        <th scope="row">
                          <CompanyIdentity name={row.company} />
                        </th>
                        <td>{row.origin_label}</td>
                        <td>
                          <span className={`badge ${STATE_TONE[row.state]}`}>{row.state_label}</span>
                        </td>
                        <td>{clean(row.reason)}</td>
                        <td className="cov-num">{row.last_checked_at ? readWhen(row.last_checked_at, tz) : "Never"}</td>
                        <td className="cov-num">{row.state === "polling" ? how(row.poll_interval_seconds) || "Today" : dayOf(row.next_check_at, tz)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="why">{report.total ? "No companies match this filter." : "ace fills this list within 30 minutes of its first run."}</p>
            )}
            <Pager total={report.matched} offset={offset} limit={report.limit} href={(next) => href({ offset: next })} />
            <details className="cov-details">
              <summary>What do these statuses mean?</summary>
              <dl>
                {report.states.map((item) => (
                  <div key={item.state}>
                    <dt>{item.label}</dt>
                    <dd>{item.meaning}</dd>
                  </div>
                ))}
              </dl>
            </details>
          </section>

          {report.origins.length ? (
            <Section id="cov-from" title="Where leads come from">
              <div className="cov-table cov-table-narrow">
                <table>
                  <thead>
                    <tr>
                      <th>From</th>
                      <th className="cov-right">Leads</th>
                      <th className="cov-right">ace reads</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.origins.map((row) => (
                      <tr key={row.origin}>
                        <th scope="row">
                          {row.label}
                          <small>{row.note}</small>
                        </th>
                        <td className="cov-right cov-num">{n(row.leads)}</td>
                        <td className="cov-right cov-num">{n(row.polling)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          ) : null}
        </>
      )}
    </>
  );
}

export function SourcesTab({
  report,
  hosts,
  capacity,
  schedule,
  tz,
  show,
  q,
  offset,
}: {
  report: SourcesReport | null;
  hosts: HostsReport | null;
  capacity: CapacityReport | null;
  schedule: ScheduleReport | null;
  tz: string;
  show?: string;
  q?: string;
  offset: number;
}) {
  const href = (next: { show?: string | null; offset?: number }) => {
    const params = new URLSearchParams({ tab: "sources" });
    const chosen = next.show === undefined ? show : next.show;
    if (chosen) params.set("show", chosen);
    if (q) params.set("q", q);
    if (next.offset) params.set("offset", String(next.offset));
    return `/app/coverage?${params.toString()}`;
  };

  return (
    <>
      <p className="why cov-lead">
        <b>Which job boards does ace really read, and are they working?</b> A source is a company&rsquo;s job board that
        ace reads all day. New jobs from here go to Pulls and Opportunities.
      </p>

      {!report ? (
        <p className="why">The list of boards could not be loaded just now. Refresh to try again.</p>
      ) : (
        <>
          <div className="cov-stats">
            <Stat value={n(report.counts.total)} label="Boards ace reads" />
            <Stat value={n(report.counts.working)} label="Working" />
            <Stat value={n(report.counts.dark)} label="Stopped answering" note={report.counts.dark ? "Listed below" : undefined} />
            <Stat value={n(report.counts.says_no)} label="On sites that say no" note={report.counts.says_no ? "Listed below" : undefined} />
          </div>

          <Capacity c={capacity} />

          <Schedule s={schedule} />

          <section className="cov-section" aria-labelledby="cov-all">
            <div className="cov-section-head">
              <h2 id="cov-all">All boards ace reads</h2>
              <Finder tab="sources" query={q} kept={show ? { show } : {}} label="Find a company" />
            </div>
            <nav className="cov-chips" aria-label="Filter boards">
              {(
                [
                  [null, "All", report.counts.total],
                  ["mine", "Added by you", report.counts.mine],
                  ["dark", "Stopped answering", report.counts.dark],
                  ["says_no", "Site says no", report.counts.says_no],
                ] as const
              ).map(([key, label, count]) => (
                <Link key={label} aria-current={(show ?? null) === key ? "true" : undefined} href={href({ show: key })}>
                  {label} <span>{n(count)}</span>
                </Link>
              ))}
            </nav>
            {report.rows.length ? (
              <div className="cov-table">
                <table>
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Hiring site</th>
                      <th>Last read</th>
                      <th>How often</th>
                      <th className="cov-right">Jobs</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.rows.map((row) => (
                      <tr key={`${row.source_type}/${row.source_account}`} title={`${row.source_type}, ${row.source_account}`}>
                        <th scope="row">
                          <span className="cov-company">
                            <CompanyIdentity name={row.company} />
                            {row.added_by_you ? <span className="badge new">Added by you</span> : null}
                          </span>
                        </th>
                        <td>{row.site}</td>
                        <td className="cov-num">{readWhen(row.last_read_at, tz)}</td>
                        <td>{how(row.poll_interval_seconds)}</td>
                        <td className="cov-right cov-num">{row.jobs === null ? "" : n(row.jobs)}</td>
                        <td>
                          <span className={`badge ${STATUS_TONE[row.status]}`}>{row.status_label}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="why">No boards match this filter.</p>
            )}
            <Pager total={report.matched} offset={offset} limit={report.limit} href={(next) => href({ offset: next })} />
          </section>

          {report.dark.length ? (
            <Section
              id="cov-dark"
              title={`Stopped answering (${n(report.dark.length)})`}
              intro="ace has had no answer from these boards for a day or more, so new jobs there are not reaching you. Every six hours ace looks for where each company has moved, and switches over by itself when it finds the new board."
            >
              <div className="cov-grid">
                {report.dark.map((r) => (
                  <div className="cov-row" key={`${r.source_type}/${r.source_account}`} title={`${r.source_type}, ${r.source_account}`}>
                    <span className="cov-name">
                      <CompanyIdentity name={r.company} />
                    </span>
                    <span className="cov-n">{r.site}</span>
                    <span className="cov-pct">{r.last_success_at ? `since ${shortDate(r.last_success_at, tz)}` : "never answered"}</span>
                  </div>
                ))}
              </div>
            </Section>
          ) : null}
        </>
      )}

      {!hosts ? (
        <p className="why">Whether each site allows reading could not be loaded just now. Refresh to try again.</p>
      ) : (
        <>
          <Section
            id="cov-allowed"
            title="Is ace allowed to read each site?"
            intro="Every website publishes rules for automated readers, in a file called robots. ace reads those rules and checks them again every month. Terms of use are a person's dated note, not legal advice."
          >
            {hosts.groups.length ? (
              <div className="cov-table">
                <table>
                  <thead>
                    <tr>
                      <th>Hiring site</th>
                      <th className="cov-right">Sites</th>
                      <th>Robots rules</th>
                      <th>Terms of use</th>
                      <th>Note</th>
                      <th>Checked</th>
                      <th>Next</th>
                    </tr>
                  </thead>
                  <tbody>
                    {hosts.groups.map((group) => {
                      const [terms, tone] = TERMS[group.terms.verdict];
                      return (
                        <tr key={group.platform}>
                          <th scope="row">{group.label}</th>
                          <td className="cov-right cov-num">{n(group.hosts)}</td>
                          <td>
                            {group.refused ? (
                              <span className="badge cov-bad">{n(group.refused)} say no</span>
                            ) : group.unknown ? (
                              <span className="badge cov-plain">{n(group.unknown)} not checked yet</span>
                            ) : (
                              <span className="badge cov-good">Allowed</span>
                            )}
                          </td>
                          <td>
                            <span className={`badge ${tone}`}>{terms}</span>
                          </td>
                          <td>{clean(group.terms.note).replace(/\bACE\b/g, "ace")}</td>
                          <td className="cov-num">{group.oldest_checked_at ? shortDate(group.oldest_checked_at, tz) : "Not yet"}</td>
                          <td className="cov-num">{dayOf(group.next_check_at, tz)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="why">ace has not checked any site yet. Its first check runs within 30 minutes.</p>
            )}
          </Section>

          {hosts.refused_hosts.length ? (
            <Section id="cov-no" title={`Sites that say no (${n(hosts.refused_hosts.length)})`}>
              <p className="cov-info">
                {hosts.enforcing
                  ? "ace has stopped reading these sites."
                  : "ace still reads the boards it already read on these sites, so that you can decide. It adds nothing new from them."}
              </p>
              <div className="cov-table">
                <table>
                  <thead>
                    <tr>
                      <th>Site</th>
                      <th>Why</th>
                      <th className="cov-right">Boards</th>
                      <th>Checked</th>
                      <th>Next</th>
                    </tr>
                  </thead>
                  <tbody>
                    {hosts.refused_hosts.map((row) => (
                      <tr key={row.host}>
                        <th scope="row">{row.host}</th>
                        <td>{clean(row.detail).replace(/\bACE\b/g, "ace")}</td>
                        <td className="cov-right cov-num">{n(row.sources)}</td>
                        <td className="cov-num">{row.checked_at ? shortDate(row.checked_at, tz) : "Not yet"}</td>
                        <td className="cov-num">{dayOf(row.next_check_at, tz)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          ) : null}
        </>
      )}
    </>
  );
}
