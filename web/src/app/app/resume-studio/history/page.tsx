import Link from "next/link";
import { CompanyIdentity } from "@/components/CompanyIdentity";

import { ScrollArea } from "@/components/shell/ScrollArea";
import { ScoreDial } from "@/components/studio/AssessmentView";
import { apiGetOr } from "@/lib/api";
import { clean, clock, shortDate } from "@/lib/format";
import { getPrefs } from "@/lib/prefs";
import { COMPONENT_LABEL, STATE_LABEL, type AssessmentSummary, type Component, type StudioOverview } from "@/lib/studio";

export const metadata = { title: "Check history · ace" };

const COMPS: Component[] = ["requirements", "parseability", "quality", "fit"];

export default async function HistoryPage() {
  const [{ tz }, { items }, o] = await Promise.all([
    getPrefs(),
    apiGetOr<{ items: AssessmentSummary[] }>("/api/studio/assessments", { items: [] }),
    apiGetOr<StudioOverview | null>("/api/studio", null),
  ]);
  const names = new Map((o?.versions ?? []).map((v) => [v.id, v.label]));
  return (
    <ScrollArea>
      <div className="page">
        <div className="wrap">
          {items.length ? (
            <div className="st-history">
              {items.map((a) => (
                <Link className="st-hrow" key={a.id} href={`/app/resume-studio/history/${a.id}`}>
                  <ScoreDial value={a.aggregate} size={40} />
                  <span className="st-hrow-t">
                    <b>{a.job_company ? <CompanyIdentity name={a.job_company} /> : (a.job_source === "pasted" ? "Pasted job" : "Job")}</b>
                    <span>{clean(a.job_title)}</span>
                  </span>
                  <span className="st-hrow-comps">
                    {COMPS.map((k) => (
                      <span key={k} title={COMPONENT_LABEL[k]}>
                        {COMPONENT_LABEL[k].split(" ")[0]} {a.components[k] ?? "?"}
                      </span>
                    ))}
                  </span>
                  <span className="st-muted">{names.get(a.version_id) ?? ""}</span>
                  <span className="st-chip">{STATE_LABEL[a.state]}</span>
                  <span className="st-muted">
                    {shortDate(a.created_at, tz)} {clock(a.created_at, tz)}
                  </span>
                </Link>
              ))}
            </div>
          ) : (
            <div className="empty">
              <h3>No checks yet</h3>
              <p>Run the ATS checker against a job, and every result is kept here to compare versions over time.</p>
              <Link className="btn btn-primary btn-sm" href="/app/resume-studio/check">
                Open the checker
              </Link>
            </div>
          )}
        </div>
      </div>
    </ScrollArea>
  );
}
