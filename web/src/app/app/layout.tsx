import { AnswersDock } from "@/components/shell/AnswersDock";
import { AppProvider } from "@/components/shell/AppProvider";
import { SiteFooter } from "@/components/shell/SiteFooter";
import { SiteHeader } from "@/components/shell/SiteHeader";
import { apiGetOr, authStatus } from "@/lib/api";
import { getPrefs, getPrevVisit } from "@/lib/prefs";
import type { Answer, MarkCounts, SystemStatus } from "@/lib/types";

const NO_MARKS: MarkCounts = { saved: 0, archived: 0, applied: 0, open_applications: 0, by_status: {} };

// The shell: the top navigation's counts, the live indicator and the answers drawer.
// Layouts persist across navigation, so this is read once per visit and
// again on each refresh (a mark, or the two-minute live refresh).
export default async function AppLayout({ children }: LayoutProps<"/app">) {
  // Only what every page needs: who is signed in, when ace last
  // checked, the marks for the nav count and the answers drawer. Each
  // page loads its own data; the shell must stay cheap because it runs
  // on every navigation.
  const [status, prefs, prevVisit, system, marks, answers] = await Promise.all([
    authStatus(),
    getPrefs(),
    getPrevVisit(),
    apiGetOr<SystemStatus | null>("/api/system", null),
    apiGetOr<MarkCounts>("/api/marks", NO_MARKS),
    apiGetOr<{ items: Answer[] }>("/api/answers", { items: [] }),
  ]);

  return (
    <AppProvider
      tz={prefs.tz}
      theme={prefs.theme}
      prevVisit={prevVisit ? prevVisit.getTime() : null}
      lastPoll={system?.scheduler.last_poll_at ?? null}
      marks={marks}
    >
      <div className="app">
        <SiteHeader answersFilled={answers.items.filter((a) => a.value).length} />
        {status === null ? (
          <div className="down" role="alert">
            <b>ace&rsquo;s API is not answering</b>, so nothing below is real data. The web app looks for it at{" "}
            <code>{process.env.API_ORIGIN ?? "http://127.0.0.1:8000"}</code>. Start the API there, or restart the web
            app with API_ORIGIN pointing at it, then reload.
          </div>
        ) : null}
        <main className="main" id="main">
          {children}
        </main>
        <SiteFooter />
      </div>
      <AnswersDock answers={answers.items} />
    </AppProvider>
  );
}
