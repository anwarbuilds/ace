import { AnswersDock } from "@/components/shell/AnswersDock";
import { AppProvider } from "@/components/shell/AppProvider";
import { CommandPalette } from "@/components/shell/CommandPalette";
import { SiteHeader } from "@/components/shell/SiteHeader";
import { apiGetOr } from "@/lib/api";
import { getPrefs, getPrevVisit } from "@/lib/prefs";
import type { Answer, Coverage, ExternalApplication, MarkCounts, Stats } from "@/lib/types";

const NO_MARKS: MarkCounts = { saved: 0, archived: 0, applied: 0, open_applications: 0, by_status: {} };

// The shell: the top navigation's counts, the live indicator and the answers drawer.
// Layouts persist across navigation, so this is read once per visit and
// again on each refresh (a mark, or the two-minute live refresh).
export default async function AppLayout({ children }: LayoutProps<"/app">) {
  const [prefs, prevVisit, stats, marks, answers, coverage, external] = await Promise.all([
    getPrefs(),
    getPrevVisit(),
    apiGetOr<Stats>("/api/stats", { last_poll_at: null }),
    apiGetOr<MarkCounts>("/api/marks", NO_MARKS),
    apiGetOr<{ items: Answer[] }>("/api/answers", { items: [] }),
    apiGetOr<Coverage | null>("/api/coverage", null),
    apiGetOr<{ items: ExternalApplication[] }>("/api/applications/external", { items: [] }),
  ]);

  return (
    <AppProvider
      tz={prefs.tz}
      theme={prefs.theme}
      prevVisit={prevVisit ? prevVisit.getTime() : null}
      lastPoll={stats.last_poll_at}
      marks={marks}
    >
      <div className="app">
        <SiteHeader
          queueCount={stats.qualifying_active_jobs ?? 0}
          externalCount={external.items.length}
          answersFilled={answers.items.filter((a) => a.value).length}
          coverageGaps={coverage?.unreached.length ?? 0}
        />
        <main className="main" id="main">
          {children}
        </main>
      </div>
      <AnswersDock answers={answers.items} />
      <CommandPalette />
    </AppProvider>
  );
}
