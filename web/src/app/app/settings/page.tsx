import { ThemeChips } from "@/components/pages/ThemeChips";
import { SecuritySettings, type SessionRow, type TokenRow } from "@/components/pages/SecuritySettings";
import { UploadResume } from "@/components/pages/UploadResume";
import { LiveChip } from "@/components/shell/Live";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr, authStatus } from "@/lib/api";
import { clock, shortDate } from "@/lib/format";
import { getPrefs } from "@/lib/prefs";
import type { Facets, MarkCounts, ResumeResponse, SystemStatus } from "@/lib/types";

export const metadata = { title: "Settings · ace" };

export default async function SettingsPage() {
  const [facets, data, m, system, { tz }, auth, sessions, tokens] = await Promise.all([
    apiGetOr<Facets | null>("/api/facets", null),
    apiGetOr<ResumeResponse>("/api/resume", { resume: null, skills_gap: [] }),
    apiGetOr<MarkCounts | null>("/api/marks", null),
    apiGetOr<SystemStatus | null>("/api/system", null),
    getPrefs(),
    authStatus(),
    apiGetOr<{ items: SessionRow[] }>("/api/auth/sessions", { items: [] }),
    apiGetOr<{ items: TokenRow[] }>("/api/extension/tokens", { items: [] }),
  ]);
  // Dates are formatted here, in the reader's zone, so the client renders
  // exactly what the server did.
  const when: Record<string, string> = {};
  for (const iso of [
    ...sessions.items.map((s) => s.last_seen_at),
    ...tokens.items.flatMap((t) => (t.last_used_at ? [t.last_used_at] : [])),
  ]) {
    when[iso] = `${shortDate(iso, tz)} ${clock(iso, tz)}`;
  }
  const a = system?.alerts;
  const week = a ? Object.entries(a.last_7_days).map(([k, n]) => `${n} ${k}`).join(", ") : "";
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
            {auth?.kind === "session" && auth.email ? (
              <SecuritySettings email={auth.email} sessions={sessions.items} tokens={tokens.items} when={when} />
            ) : auth?.kind === "local" ? (
              <div className="sect">
                <p className="eyebrow">Sign-in</p>
                <p className="why">
                  Sign-in is switched off (ACE_AUTH=disabled), so ace answers only on this computer. Remove that line
                  from .env and restart to turn it back on.
                </p>
              </div>
            ) : null}
            <div className="sect">
              <p className="eyebrow">Your pipeline</p>
              <div className="cards3">
                {stat(m?.applied, "Applied")}
                {stat(m?.open_applications, "Still open")}
                {stat(m?.by_status.rejected, "Rejected")}
                {stat(m?.by_status.interviewing, "Interviewing")}
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
            <div className="sect">
              <p className="eyebrow">Service health</p>
              {system ? (
                <dl className="kv">
                  <dt>Discovery</dt>
                  <dd>
                    {system.scheduler.stale ? "Not updating" : "Live"}
                    {system.scheduler.last_poll_at
                      ? `, last check ${shortDate(system.scheduler.last_poll_at, tz)} ${clock(system.scheduler.last_poll_at, tz)}`
                      : ", no check recorded"}
                  </dd>
                  <dt>Boards watched</dt>
                  <dd>{system.scheduler.sources_enabled}</dd>
                  <dt>Resume scoring</dt>
                  <dd>
                    {system.scoring.resume_active
                      ? `${system.scoring.queue_jobs - system.scoring.queue_unscored} of ${system.scoring.queue_jobs} open roles scored`
                      : "no resume uploaded"}
                  </dd>
                  <dt>Email alerts</dt>
                  <dd>
                    {!a!.address_set
                      ? "off, no ALERT_EMAIL in .env"
                      : !a!.provider_configured
                        ? "composed but not delivered: no RESEND_API_KEY in .env"
                        : a!.last_sent_at
                          ? `delivering, last sent ${shortDate(a!.last_sent_at, tz)} ${clock(a!.last_sent_at, tz)}`
                          : "configured, nothing sent yet"}
                  </dd>
                  {week ? (
                    <>
                      <dt>Alerts, 7 days</dt>
                      <dd>{week}</dd>
                    </>
                  ) : null}
                  <dt>Targeting</dt>
                  <dd>
                    {system.profile.key === "sde2"
                      ? `new grad first, SDE II included: up to ${system.profile.max_open_ended_years - 1}+ years`
                      : `early career: up to ${system.profile.max_open_ended_years - 1} years, "3+" left out`}
                    {`, ${system.profile.experience_years} years of experience`}
                  </dd>
                  <dt>Rule versions</dt>
                  <dd>
                    gate {system.versions.gate}, matching {system.versions.matching}
                  </dd>
                  <dt>Dates shown in</dt>
                  <dd>{tz}</dd>
                </dl>
              ) : (
                <p className="why">The ace API did not answer, so its health is unknown.</p>
              )}
            </div>
            <div className="sect">
              <p className="eyebrow">Your data</p>
              <p className="why">
                Everything you entered by hand, in one file: marks, statuses and notes, answers, work and education
                history, applications without a stored posting, and resume versions. Jobs are not included; ace
                reads them again from the boards.
              </p>
              <div className="controls" style={{ paddingLeft: 0 }}>
                <a className="btn btn-secondary btn-sm" href="/api/export.json" download>
                  Download everything (JSON)
                </a>
                <a className="btn btn-secondary btn-sm" href="/api/applications/export.csv" download>
                  Applications (CSV)
                </a>
              </div>
            </div>
            <div className="note">Press Ctrl or Command plus K for the command palette.</div>
          </div>
        </div>
      </ScrollArea>
    </>
  );
}
