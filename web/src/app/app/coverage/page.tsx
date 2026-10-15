import { AddSource } from "@/components/pages/AddSource";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGet } from "@/lib/api";
import { clean, shortDate } from "@/lib/format";
import { getPrefs } from "@/lib/prefs";
import type { Coverage, CoverageGap } from "@/lib/types";

export const metadata = { title: "Coverage · ace" };

// What is in the way, grouped by what would fix it. A flat list of 154
// names was a wall; "31 are on iCIMS" is a decision waiting to be made.
const GROUPS: [string, string, string][] = [
  ["other_ats", "Hire through an ATS ace cannot read yet", "Each needs an adapter. The name says which one, so the work is countable rather than open-ended."],
  ["no_board_found", "Publish no board ace recognises", "Usually a careers page that builds itself in the browser, or hiring software run in-house."],
  ["no_postings", "Readable, but nothing posted right now", "ace found and checked the board. There is simply nothing on it today."],
  ["refused", "Found a board, refused to trust it", "The board named a different company. A board under the wrong name is harder to notice than a gap, so it was left alone."],
  ["blocked", "Refuse automated access", "Their site answers and turns ace away. That is deliberate on their side and is respected rather than worked around, so these have to be found by hand. No adapter would change it."],
  ["site_unreachable", "No website answered", "The company may trade under another name. Pasting their careers link above fixes these outright."],
  ["unprobed", "Not looked at yet", "Run the coverage probe to find out."],
];

const LATE_BOARD_ADDED = "board added after the feed listed it";
const LATE_REPUBLISHED = "republished after the feed listed it";

function Names({ rows }: { rows: CoverageGap[] }) {
  return (
    <div className="cov-names">
      {rows.map((r) => (
        <span key={r.company} className="cov-name" title={r.detail || ""}>
          {r.company}
        </span>
      ))}
    </div>
  );
}

export default async function CoveragePage() {
  const [{ tz }, c] = await Promise.all([getPrefs(), apiGet<Coverage>("/api/coverage")]);
  const pct = c.total ? Math.round((100 * c.reached) / c.total) : 0;
  const by: Record<string, CoverageGap[]> = {};
  for (const r of c.unreached) (by[r.outcome] ??= []).push(r);
  const known = new Set(GROUPS.map(([k]) => k));
  const late = c.caught_late;
  const sponsorTotal = c.sponsorship.reduce((n, r) => n + r.refusing, 0);
  const sponsorAll = c.sponsorship.filter((r) => r.share >= 1).length;
  const feedTotal = c.feed_only.reduce((n, r) => n + r.passing, 0);

  return (
    <>
      <div className="head">
        <div className="eyebrow">System</div>
        <div className="head-row">
          <h1 className="h1">Coverage</h1>
          <span className="h1-count">
            {c.reached} of {c.total}
          </span>
          <span className="spacer" />
        </div>
      </div>
      <ScrollArea>
        <div className="page">
          <div className="wrap">
            <p className="why" style={{ maxWidth: "74ch" }}>
              ace polls {c.sources} boards and reaches{" "}
              <b>
                {c.reached} of {c.total}
              </b>{" "}
              companies on your list ({pct}%). The rest are below, grouped by what is actually in the way. Hover a name
              for the detail.
            </p>
            <div className="ans-sec">Add a company</div>
            <p className="why" style={{ margin: 0 }}>
              Paste a job link, a careers page, or just a company name. ace works out which board it is, checks the
              board really belongs to them, and starts polling. It never registers a board it cannot verify.
            </p>
            <AddSource />

            {c.dark.length ? (
              <>
                <div className="ans-sec">Stopped answering ({c.dark.length})</div>
                <p className="why" style={{ maxWidth: "74ch" }}>
                  ace polls these boards but has had no answer for a day or more, so anything new they post is not
                  reaching you. Every six hours ace looks for where each company has moved and switches over by itself
                  when it finds the new board; these are the ones it has not found yet.
                </p>
                <div className="cov-grid cov-dark">
                  {c.dark.map((r) => (
                    <div className="cov-row" key={`${r.source_type}/${r.source_account}`} title={`${r.source_type}, ${r.source_account}`}>
                      <span className="cov-name">{r.company}</span>
                      <span className="cov-n">{r.source_type}</span>
                      <span className="cov-pct">{r.last_success_at ? `since ${shortDate(r.last_success_at, tz)}` : "never answered"}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : null}

            {late && late.count ? (
              <>
                <div className="ans-sec">Caught late ({late.count} in 14 days)</div>
                <p className="why" style={{ maxWidth: "74ch" }}>
                  Roles that passed your filters but reached a curated feed before ace saw them on the employer&rsquo;s
                  own board. <b>{late.board_added_later}</b> were on a board ace only started reading after the feed
                  listed them. <b>{late.seen_late}</b> were on a board ace was already reading and saw late; those are
                  ace&rsquo;s mistakes to fix.
                  {late.republished ? (
                    <>
                      {" "}
                      <b>{late.republished}</b> were republished by the employer after the feed listed them, so they
                      are not misses.
                    </>
                  ) : null}
                </p>
                <div className="cov-grid cov-late">
                  {late.rows.map((x, i) => (
                    <div className="cov-row" key={i} title={x.cause}>
                      <span className="cov-name">
                        {x.company}, {clean(x.title)}
                      </span>
                      <span className="cov-n">
                        {x.cause === LATE_BOARD_ADDED ? "board added late" : x.cause === LATE_REPUBLISHED ? "republished" : "seen late"}
                      </span>
                      <span className="cov-pct">{x.lag_hours} h</span>
                    </div>
                  ))}
                </div>
              </>
            ) : null}

            {c.feed_only.length ? (
              <>
                <div className="ans-sec">Known only through a feed ({c.feed_only.length})</div>
                <p className="why" style={{ maxWidth: "74ch" }}>
                  {feedTotal} roles that pass your filters reach ace only from a feed, whose description is a
                  placeholder until ace reads the employer&rsquo;s page.
                </p>
                <div className="cov-grid cov-feedonly">
                  {c.feed_only.map((r) => (
                    <div className="cov-row" key={r.company}>
                      <span className="cov-name">{r.company}</span>
                      <span className="cov-n">{r.board_read ? "board read, role missing" : "no board yet"}</span>
                      <span className="cov-pct">{r.passing}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : null}

            <div className="ans-sec">Cannot reach ({c.unreached.length})</div>
            {c.unreached.length ? (
              <>
                {GROUPS.filter(([k]) => by[k]).map(([k, title, note]) => (
                  <div className="cov-group" key={k}>
                    <div className="cov-group-h">
                      {title} <span className="cov-group-n">{by[k].length}</span>
                    </div>
                    <p className="why" style={{ margin: "0 0 8px" }}>
                      {note}
                    </p>
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
              <p className="why">ace reaches every company on your list.</p>
            )}

            {c.sponsorship.length ? (
              <>
                <div className="ans-sec">Will not sponsor ({c.sponsorship.length})</div>
                <p className="why" style={{ maxWidth: "74ch" }}>
                  These employers state on their own postings that they will not sponsor a work visa, which rules you
                  out. ace already rejects each of these jobs; this is the same fact said once instead of {sponsorTotal}{" "}
                  times.{" "}
                  {sponsorAll ? (
                    <>
                      <b>{sponsorAll}</b> refuse on every readable posting.
                    </>
                  ) : null}
                </p>
                <div className="cov-grid cov-sponsor">
                  {c.sponsorship.map((r) => (
                    <div
                      key={r.company}
                      className={`cov-row${r.share >= 1 ? " cov-row-all" : ""}`}
                      title={`${r.refusing} of ${r.readable} readable postings say no sponsorship`}
                    >
                      <span className="cov-name">{r.company}</span>
                      <span className="cov-n">
                        {r.refusing} of {r.readable}
                      </span>
                      <span className="cov-pct">{Math.round(r.share * 100)}%</span>
                    </div>
                  ))}
                </div>
              </>
            ) : null}
          </div>
        </div>
      </ScrollArea>
    </>
  );
}
