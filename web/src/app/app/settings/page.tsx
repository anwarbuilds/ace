import { ThemeChips } from "@/components/pages/ThemeChips";
import { UploadResume } from "@/components/pages/UploadResume";
import { LiveChip } from "@/components/shell/Live";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import type { Facets, MarkCounts, ResumeResponse } from "@/lib/types";

export const metadata = { title: "Settings · ace" };

export default async function SettingsPage() {
  const [facets, data, m] = await Promise.all([
    apiGetOr<Facets | null>("/api/facets", null),
    apiGetOr<ResumeResponse>("/api/resume", { resume: null, skills_gap: [] }),
    apiGetOr<MarkCounts | null>("/api/marks", null),
  ]);
  const r = data.resume;
  const sources = facets?.sources ?? [];
  const stat = (n: number | undefined, label: string) => (
    <div className="stat">
      <div className="stat-n">{n ?? 0}</div>
      <div className="stat-l">{label}</div>
    </div>
  );

  return (
    <>
      <div className="head">
        <div className="head-row">
          <h1 className="h1">Settings</h1>
          <span className="spacer" />
          <LiveChip />
        </div>
      </div>
      <ScrollArea>
        <div className="page">
          <div className="wrap">
            <div className="sect">
              <p className="eyebrow">Appearance</p>
              <ThemeChips />
              <p className="why">Night is anthracite grey, Day its light version. System follows your operating system.</p>
            </div>
            <div className="sect">
              <p className="eyebrow">Your pipeline</p>
              <div className="cards3">
                {stat(m?.applied, "Applied")}
                {stat(m?.open_applications, "Still open")}
                {stat(m?.by_status.rejected, "Rejected")}
                {stat(m?.saved, "Saved")}
              </div>
            </div>
            <div className="sect">
              <p className="eyebrow">Active resume</p>
              {r ? (
                <div className="gaprow">
                  <span>{r.label}</span>
                  <span className="gap-n">{r.skills.length} skills</span>
                  <UploadResume label="Replace" link />
                </div>
              ) : (
                <p className="why">No resume stored. Matching is unavailable until one is uploaded.</p>
              )}
            </div>
            <div className="sect">
              <p className="eyebrow">Sources, {sources.length} reporting</p>
              <dl className="kv">
                {sources.map((o) => (
                  <div key={o.value} style={{ display: "contents" }}>
                    <dt>{o.value}</dt>
                    <dd>{o.count}</dd>
                  </div>
                ))}
              </dl>
              <p className="why" style={{ marginTop: 10 }}>
                Counts are qualifying opportunities currently open.
              </p>
            </div>
            <div className="note">Press Ctrl or Command plus K for the command palette.</div>
          </div>
        </div>
      </ScrollArea>
    </>
  );
}
