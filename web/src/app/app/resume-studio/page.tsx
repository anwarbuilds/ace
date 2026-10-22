import Link from "next/link";

import { EmptyBox } from "@/components/bits";
import { Kpi } from "@/components/page/PageParts";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { ScoreDial } from "@/components/studio/AssessmentView";
import { ResumeDocumentPreview } from "@/components/studio/ResumeDocumentPreview";
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
  const previewDocument = o
    ? (primary?.document_id ? o.documents.find((document) => document.id === primary.document_id) : null) ??
      o.documents.find((document) => document.kind === "resume")
    : null;

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
          <div className="kpis studio-v2-kpis">
            <Kpi
              label="Base resume"
              value={primary ? "1" : "0"}
              foot={primary ? `${primary.label}, under your control` : "Choose a version for matching"}
              href="/app/resume-studio/documents"
            />
            <Kpi
              label="Resume versions"
              value={o.versions.length.toLocaleString("en-US")}
              foot={`${o.documents.length.toLocaleString("en-US")} source files stored`}
              href="/app/resume-studio/documents"
            />
            <Kpi
              label="Skills represented"
              value={(r?.skills.length ?? 0).toLocaleString("en-US")}
              foot={`${(f.verified ?? 0).toLocaleString("en-US")} verified facts in your profile`}
              href="/app/resume-studio/facts?kind=skill"
            />
            <Kpi
              label="Review status"
              value={review ? review.toLocaleString("en-US") : "Ready"}
              foot={review ? "Suggestions waiting for your review" : "You approve every change"}
              tone={review ? "warn" : "good"}
              href="/app/resume-studio/facts?status=review"
            />
          </div>

          <div className="studio-v2-grid">
            <div className="studio-v2-column">
              <section className="panel studio-v2-panel">
                <div className="section-head">
                  <h2>Resume library</h2>
                  <Link className="link-btn" href="/app/resume-studio/documents">
                    View all
                  </Link>
                </div>
                <div className="studio-v2-library">
                  {o.versions.slice(0, 4).map((version) => (
                    <Link
                      className={`studio-v2-entry${version.is_primary ? " selected" : ""}`}
                      href="/app/resume-studio/documents"
                      key={version.id}
                    >
                      <strong>{version.label}</strong>
                      <small>
                        {version.is_primary ? "Primary, source of truth" : version.kind === "master" ? "Master version" : "Tailored draft"}
                      </small>
                    </Link>
                  ))}
                </div>
                <div className="studio-v2-actions">
                  <StudioUpload label="Upload a resume" />
                  <StudioUpload kind="template" label="Upload a DOCX template" />
                </div>
              </section>

              <section className="panel studio-v2-panel">
                <div className="section-head">
                  <h2>Target role</h2>
                  <Link className="link-btn" href="/app/resume-studio/history">
                    History
                  </Link>
                </div>
                {o.recent[0] ? (
                  <>
                    <p className="studio-v2-role">
                      <strong>{clean(o.recent[0].job_title) || "Saved opportunity"}</strong>
                      <span>{o.recent[0].job_company || "Pasted job description"}</span>
                    </p>
                    <div className="studio-v2-match">
                      <ScoreDial value={o.recent[0].aggregate} size={76} />
                      <div>
                        <b>Estimated compatibility</b>
                        <p>Explainable skill and experience fit based on your verified resume.</p>
                      </div>
                    </div>
                  </>
                ) : (
                  <p className="why">Choose an opportunity to create your first evidence-based resume check.</p>
                )}
                <Link className="btn btn-primary btn-sm studio-v2-wide" href="/app/resume-studio/check">
                  Check against a job
                </Link>
              </section>
            </div>

            <section className="studio-v2-preview">
              <div className="section-head">
                <h2>Resume preview</h2>
                <span className="section-sub">Resume used for matching</span>
              </div>
              {previewDocument ? (
                <ResumeDocumentPreview
                  documentId={previewDocument.id}
                  filename={previewDocument.filename}
                  mediaType={previewDocument.media_type}
                />
              ) : (
                <div className="studio-v2-document-unavailable">
                  <strong>No source file is attached to this version</strong>
                  <p>Upload the original resume to preview it here.</p>
                  <StudioUpload label="Upload resume" primary />
                </div>
              )}
              <p className="studio-v2-note">Showing the original resume stored in Resume Studio.</p>
            </section>
          </div>

          <div className="sect studio-v2-knowledge">
            <div className="section-head">
              <div>
                <p className="eyebrow">Knowledge base</p>
                <h2 className="st-h2">Facts you control</h2>
              </div>
              {review ? (
                <Link className="btn btn-primary btn-sm" href="/app/resume-studio/facts?status=review">
                  Review {review} suggested
                </Link>
              ) : null}
            </div>
            <p className="why">
              Facts are kept apart from wording. ace suggests them from your resume; only the ones you verify count as
              evidence.
            </p>
            <div className="st-kinds">
              {Object.entries(o.facts.by_kind).map(([kind, count]) => (
                <Link key={kind} className="st-kind" href={`/app/resume-studio/facts?kind=${kind}`}>
                  <span>{kind}</span>
                  <span className="st-kind-n">{count}</span>
                </Link>
              ))}
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
