import Link from "next/link";

import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import { HIGH, familyLabel } from "@/lib/format";
import type { Facets, ResumeResponse, Stats } from "@/lib/types";

export const metadata = { title: "Skills · ace" };

function href(family: string, min: string): string {
  const p = new URLSearchParams();
  if (family) p.set("family", family);
  if (min) p.set("min", min);
  const q = p.toString();
  return q ? `/app/insights/skills?${q}` : "/app/insights/skills";
}

// "What am I missing for backend roles" and "what am I missing for the
// roles I already fit" are different questions; the chips ask them.
export default async function SkillsPage(props: PageProps<"/app/insights/skills">) {
  const sp = await props.searchParams;
  const family = typeof sp.family === "string" ? sp.family : "";
  const min = sp.min === String(HIGH) ? String(HIGH) : "";
  const gapParams: Record<string, string> = {};
  if (family) gapParams.family = family;
  if (min) gapParams.min_match = min;
  const [data, s, facets] = await Promise.all([
    apiGetOr<ResumeResponse>("/api/resume", { resume: null, skills_gap: [] }, gapParams),
    apiGetOr<Stats>("/api/stats", { last_poll_at: null }),
    apiGetOr<Facets | null>("/api/facets", null),
  ]);
  const have = data.resume?.skills ?? [];
  const gap = data.skills_gap;
  const max = gap.length ? gap[0].count : 1;
  const fams: [string, string][] = [["", "All roles"], ...(facets?.families ?? []).map((f) => [f.value, familyLabel(f.value)] as [string, string])];
  const total = (s.match_high ?? 0) + (s.match_medium ?? 0) + (s.match_minimal ?? 0) + (s.match_unscored ?? 0);

  return (
    <>
      <div className="head">
        <div className="eyebrow">Resume Studio</div>
        <div className="head-row">
          <h1 className="h1">Skills</h1>
          <span className="h1-count">across {s.qualifying_active_jobs ?? 0}</span>
          <span className="spacer" />
        </div>
        <div className="controls">
          {fams.map(([v, label]) => (
            <Link key={v || "all"} className={`chip${family === v ? " on" : ""}`} href={href(v, min)} scroll={false}>
              {label}
            </Link>
          ))}
          <span className="ctl-label">Match</span>
          <Link className={`chip${!min ? " on" : ""}`} href={href(family, "")} scroll={false}>
            All
          </Link>
          <Link className={`chip${min ? " on" : ""}`} href={href(family, String(HIGH))} scroll={false}>
            Roles I already fit
          </Link>
        </div>
      </div>
      <ScrollArea>
        <div className="page">
          <div className="wrap">
            <div className="sect">
              <p className="eyebrow">On your resume</p>
              <div className="skills">
                {have.length ? (
                  have.map((k) => (
                    <span key={k} className="sk have">
                      {k}
                    </span>
                  ))
                ) : (
                  <span className="rel-via">No resume uploaded.</span>
                )}
              </div>
            </div>
            <div className="sect">
              <p className="eyebrow">Gaps, ranked by demand</p>
              <div className="bars">
                {gap.length ? (
                  gap.slice(0, 14).map((g) => (
                    <div className="bar" key={g.skill}>
                      <span>{g.skill}</span>
                      <span className="bar-t">
                        <span className="bar-f" style={{ width: `${Math.round((g.count / max) * 100)}%` }} />
                      </span>
                      <span className="bar-n">{g.count}</span>
                    </div>
                  ))
                ) : (
                  <p className="why">Upload a resume to see what your queue asks for.</p>
                )}
              </div>
              {gap.length ? (
                <div className="controls" style={{ paddingLeft: 0 }}>
                  {gap.slice(0, 6).map((g) => (
                    <Link key={g.skill} className="chip" href={`/app/opportunities?q=${encodeURIComponent(g.skill)}`}>
                      {g.skill}
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="note">
              Counted from postings ace could read. {s.match_unscored ?? 0} of {total} have no score.
            </div>
          </div>
        </div>
      </ScrollArea>
    </>
  );
}
