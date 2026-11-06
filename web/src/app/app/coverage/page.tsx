import Link from "next/link";

import { Icon } from "@/components/Icon";
import { LeadsTab, ScoreboardTab, SourcesTab } from "@/components/coverage/CoverageTabs";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGet, apiGetOr } from "@/lib/api";
import { getPrefs } from "@/lib/prefs";
import type { Coverage, CoverageSummary, HostsReport, LeadsReport, SourcesReport } from "@/lib/types";
import "./coverage.css";

export const metadata = { title: "Coverage · ace" };

const TABS = [
  ["scoreboard", "Scoreboard"],
  ["leads", "Leads"],
  ["sources", "Sources"],
] as const;

export default async function CoveragePage({ searchParams }: PageProps<"/app/coverage">) {
  const sp = await searchParams;
  const one = (key: string) => (typeof sp[key] === "string" ? (sp[key] as string) : undefined);
  const tab = TABS.some(([key]) => key === one("tab")) ? (one("tab") as (typeof TABS)[number][0]) : "scoreboard";
  const q = one("q")?.trim() || undefined;
  const offset = Math.max(0, Number(one("offset")) || 0);
  const state = one("state");
  const show = one("show");

  const [{ tz }, summary] = await Promise.all([
    getPrefs(),
    apiGetOr<CoverageSummary>("/api/coverage/summary", { leads: 0, polling: 0, sources: 0 }),
  ]);

  const params: Record<string, string> = { offset: String(offset) };
  if (q) params.q = q;

  const count: Record<string, number> = { leads: summary.leads, sources: summary.sources };

  return (
    <>
      <div className="head">
        <div className="eyebrow">System</div>
        <div className="head-row">
          <h1 className="h1">Coverage</h1>
          <span className="spacer" />
          <Link className="btn btn-primary cov-add-link" href="/app/coverage?tab=leads#cov-input">
            <Icon name="plus" size={16} /> Add a job or company
          </Link>
        </div>
        <nav className="cov-tabs" aria-label="Coverage views">
          {TABS.map(([key, label]) => (
            <Link key={key} href={`/app/coverage?tab=${key}`} aria-current={tab === key ? "page" : undefined}>
              {label}
              {count[key] ? <span>{count[key].toLocaleString("en-US")}</span> : null}
            </Link>
          ))}
        </nav>
      </div>
      <ScrollArea>
        <div className="page">
          <div className="wrap cov-page">
            {tab === "scoreboard" ? (
              <ScoreboardTab
                c={await apiGet<Coverage>("/api/coverage")}
                leads={summary.leads}
                polling={summary.polling}
              />
            ) : tab === "leads" ? (
              <LeadsTab
                report={await apiGetOr<LeadsReport | null>("/api/coverage/leads", null, {
                  ...params,
                  ...(state ? { state } : {}),
                })}
                tz={tz}
                state={state}
                q={q}
                offset={offset}
              />
            ) : (
              <SourcesTab
                report={await apiGetOr<SourcesReport | null>("/api/coverage/sources", null, {
                  ...params,
                  ...(show ? { show } : {}),
                })}
                hosts={await apiGetOr<HostsReport | null>("/api/coverage/hosts", null)}
                tz={tz}
                show={show}
                q={q}
                offset={offset}
              />
            )}
          </div>
        </div>
      </ScrollArea>
    </>
  );
}
