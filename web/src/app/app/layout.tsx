import { redirect } from "next/navigation";

import { AnswersDock } from "@/components/shell/AnswersDock";
import { AppProvider } from "@/components/shell/AppProvider";
import { Sidebar } from "@/components/shell/Sidebar";
import { MobileBar, Topbar } from "@/components/shell/Topbar";
import { apiGetOr, authStatus, signInPath } from "@/lib/api";
import { getPrefs, getPrevVisit } from "@/lib/prefs";
import type { Answer, MarkCounts, SystemStatus } from "@/lib/types";

const NO_MARKS: MarkCounts = {
  saved: 0,
  archived: 0,
  applied: 0,
  applications_total: 0,
  applications_with_posting: 0,
  applications_without_posting: 0,
  open_applications: 0,
  by_status: {},
  application_by_status: {},
};

// The shell: sidebar, page header and the answers drawer. Layouts persist
// across navigation, so this is read once per visit and again on each
// refresh (a mark, or the two-minute live refresh). Only what every page
// needs; each page loads its own data.
export default async function AppLayout({ children }: LayoutProps<"/app">) {
  const [status, prefs, prevVisit, system, marks, answers] = await Promise.all([
    authStatus(),
    getPrefs(),
    getPrevVisit(),
    apiGetOr<SystemStatus | null>("/api/system", null),
    apiGetOr<MarkCounts>("/api/marks", NO_MARKS),
    apiGetOr<{ items: Answer[] }>("/api/answers", { items: [] }),
  ]);

  // The server decides; this only saves a round of empty pages. The
  // page asked for comes back after signing in.
  if (status && !status.signed_in) redirect(await signInPath());

  const counts: Record<string, number | null> = {
    "/app/applications": marks.applications_total || null,
    "/app/archive": marks.archived || null,
  };

  return (
    <AppProvider
      tz={prefs.tz}
      theme={prefs.theme}
      prevVisit={prevVisit ? prevVisit.getTime() : null}
      lastPoll={system?.scheduler.last_poll_at ?? null}
      marks={marks}
    >
      <a className="skip" href="#main">
        Skip to content
      </a>
      <div className="shell">
        <Sidebar counts={counts} email={status?.email ?? null} />
        <div className="shell-main">
          <Topbar />
          {status === null ? (
            <div className="down" role="alert">
              <b>ace&rsquo;s API is not answering</b>, so nothing below is real data. The web app looks for it at{" "}
              <code>{process.env.API_ORIGIN ?? "http://127.0.0.1:8000"}</code>. Start the API there, or restart the web
              app with API_ORIGIN pointing at it, then reload.
            </div>
          ) : null}
          <main className="main content" id="main">
            {children}
          </main>
        </div>
      </div>
      <MobileBar />
      <AnswersDock answers={answers.items} />
    </AppProvider>
  );
}
