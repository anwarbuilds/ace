import Link from "next/link";

import { EmptyBox } from "@/components/bits";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { ScoreDial } from "@/components/studio/AssessmentView";
import { StudioUpload } from "@/components/studio/StudioUpload";
import { apiGetOr } from "@/lib/api";
import { clean, shortDate } from "@/lib/format";
import { getPrefs } from "@/lib/prefs";
import { STATE_LABEL, type StudioOverview } from "@/lib/studio";
import type { ResumeResponse, Stats } from "@/lib/types";

export const metadata = { title: "Resume Studio · ace" };

function Bar({ label, n, total, cls = "" }: { label: string; n: number; total: number; cls?: string }) {
  const pct = total ? Math.round((n / total) * 100) : 0;
  return (
    <div className="bar">
      <span>{label}</span>
      <span className="bar-t">
        <span className={`bar-f ${cls}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="bar-n">{n}</span>
    </div>
  );
}

export default async function StudioOverviewPage() {
  const [{ tz }, o, data, s] = await Promise.all([
    getPrefs(),
    apiGetOr<StudioOverview | null>("/api/studio", null),
    apiGetOr<ResumeResponse>("/api/resume", { resume: null, skills_gap: [] }),
    apiGetOr<Stats>("/api/stats", { last_poll_at: null }),
  ]);
  const f = o?.facts.by_status ?? {};
  const review = (f.suggested ?? 0) + (f.needs_clarification ?? 0);
  const total = (s.match_high ?? 0) + (s.match_medium ?? 0) + (s.match_minimal ?? 0) + (s.match_unscored ?? 0);
  const primary = o?.primary;
  const r = data.resume;

  if (!o || (!o.documents.length && !primary)) {
    return (
      <ScrollArea>
        <div className="page">
          <div className="wrap">
            <EmptyBox title="Start with your resume" actions={<StudioUpload label="Upload resume" primary />}>
              ace reads it, suggests the facts in it for you to confirm, and checks it against any job. Nothing is
              invented and nothing is sent anywhere.
            </EmptyBox>
          </div>
        </div>
      </ScrollArea>
    );
  }

  return (
    <ScrollArea>
      <div className="page">
        <div className="wrap">
          <div className="cards3 sect">
            <Link className="stat st-stat" href="/app/resume-studio/facts?status=verified">
              <div className="stat-n m-high">{f.verified ?? 0}</div>
              <div className="stat-l">Verified facts</div>
            </Link>
            <Link className="stat st-stat" href="/app/resume-studio/facts?status=review">
              <div className="stat-n">{review}</div>
              <div className="stat-l">Waiting for your review</div>
            </Link>
            <Link className="stat st-stat" href="/app/resume-studio/documents">
              <div className="stat-n">{o.versions.length}</div>
              <div className="stat-l">Resume versions</div>
            </Link>
            <Link className="stat st-stat" href="/app/resume-studio/history">
              <div className="stat-n">{o.recent.length}</div>
              <div className="stat-l">Recent checks</div>
            </Link>
          </div>

          <div className="sect st-split">
            <div className="card st-card">
              <p className="eyebrow">Resume used for matching</p>
              {primary ? (
                <>
                  <h2 className="st-h2">{primary.label}</h2>
                  <p className="why">
                    Ranks every opportunity. Approved {shortDate(primary.approved_at ?? primary.created_at, tz)}.
                  </p>
                </>
              ) : (
                <p className="why">No version is used for matching yet. Choose one under Documents and versions.</p>
              )}
              <div className="controls" style={{ paddingLeft: 0 }}>
                <StudioUpload label="Upload a resume" />
                <StudioUpload kind="template" label="Upload a DOCX template" />
                <Link className="btn btn-secondary btn-sm" href="/app/resume-studio/check">
                  Check against a job
                </Link>
              </div>
            </div>
            <div className="card st-card">
              <p className="eyebrow">Knowledge base</p>
              <p className="why">
                Facts are kept apart from wording. ace suggests them from your resume; only the ones you verify count
                as evidence.
              </p>
              <div className="st-kinds">
                {Object.entries(o.facts.by_kind).map(([k, n]) => (
                  <Link key={k} className="st-kind" href={`/app/resume-studio/facts?kind=${k}`}>
                    <span>{k}</span>
                    <span className="st-kind-n">{n}</span>
                  </Link>
                ))}
              </div>
              {review ? (
                <Link className="btn btn-primary btn-sm" href="/app/resume-studio/facts?status=review">
                  Review {review} suggested
                </Link>
              ) : null}
            </div>
          </div>

          {o.recent.length ? (
            <div className="sect">
              <p className="eyebrow">Recent checks</p>
              <div className="st-history">
                {o.recent.map((a) => (
                  <Link className="st-hrow" key={a.id} href={`/app/resume-studio/history/${a.id}`}>
                    <ScoreDial value={a.aggregate} size={40} />
                    <span className="st-hrow-t">
                      <b>{a.job_company || "Pasted job"}</b>
                      <span>{clean(a.job_title)}</span>
                    </span>
                    <span className="st-chip">{STATE_LABEL[a.state]}</span>
                    <span className="st-muted">{shortDate(a.created_at, tz)}</span>
                  </Link>
                ))}
              </div>
            </div>
          ) : null}

          {r ? (
            <>
              <div className="sect">
                <p className="eyebrow">How the matching resume ranks your opportunities</p>
                <div className="bars">
                  <Bar label="HIGH" n={s.match_high ?? 0} total={total} cls="gold" />
                  <Bar label="MEDIUM" n={s.match_medium ?? 0} total={total} />
                  <Bar label="MINIMAL" n={s.match_minimal ?? 0} total={total} />
                  <Bar label="Not scored" n={s.match_unscored ?? 0} total={total} cls="dot" />
                </div>
              </div>
              <div className="sect">
                <p className="eyebrow">Most requested, missing from this resume</p>
                {data.skills_gap.length ? (
                  data.skills_gap.slice(0, 6).map((g) => (
                    <div className="gaprow" key={g.skill}>
                      <span>{g.skill}</span>
                      <span className="gap-n">in {g.count} opportunities</span>
                      <Link className="link-btn" href={`/app/opportunities?q=${encodeURIComponent(g.skill)}`}>
                        View jobs
                      </Link>
                    </div>
                  ))
                ) : (
                  <p className="why">No gaps recorded yet.</p>
                )}
                <p className="why" style={{ marginTop: 10 }}>
                  A gap is a fact you may not have, not a word to add. Add it to the knowledge base only if it is true.{" "}
                  <Link className="link-btn" href="/app/insights/skills">
                    All skills
                  </Link>
                </p>
              </div>
            </>
          ) : null}
        </div>
      </div>
    </ScrollArea>
  );
}
