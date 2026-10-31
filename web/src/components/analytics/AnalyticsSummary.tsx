import Link from "next/link";
import { coverageText } from "@/lib/inboxSync";
import { NavIcon } from "@/components/shell/NavIcon";
import { applicationRecordsHref, emailRecordsHref, type AnalyticsData, type InboxConnection } from "@/lib/analytics";
import { ANALYTICS_WEEK_TIMEZONE, localDate, mondayOf, type AnalyticsSupplement, type SubmissionTrend } from "@/lib/analyticsCalculations";

const INBOX = "/app/applications/inbox";
const number = (value: number) => value.toLocaleString("en-US");
function SummaryIcon({ kind }: { kind: string }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{kind === "calendar" ? <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 2v6M17 2v6M3 11h18" /></> : kind === "reply" ? <path d="M7 3h10a6 6 0 0 1 6 6v2a6 6 0 0 1-6 6h-3l-4 4v-4H7a6 6 0 0 1-6-6V9a6 6 0 0 1 6-6Z" /> : kind === "people" ? <><circle cx="9" cy="7" r="3" /><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 5v2" /></> : kind === "mail" ? <><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m3 6 9 7 9-7" /></> : kind === "file" ? <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h8" /></> : <path d="m22 2-7 20-4-9-9-4zM22 2 11 13" />}</svg>;
}
function Trend({ value, reason }: { value?: SubmissionTrend | null; reason: string }) {
  if (!value) return <span className="an-trend-missing" title={reason} aria-label={reason}>ⓘ</span>;
  return <span className={`an-trend ${value.percent !== null && value.percent < 0 ? "an-trend-down" : ""}`} title={`${value.description} Current ${value.current}; previous ${value.previous}.`}><span aria-hidden="true">{value.percent !== null ? value.percent < 0 ? "↓" : value.percent > 0 ? "↑" : "" : ""}</span>{value.label}</span>;
}
export function currentWeekHref(d: AnalyticsData, supplement?: AnalyticsSupplement | null) {
  const today = supplement?.weekToday ?? localDate(d.as_of, ANALYTICS_WEEK_TIMEZONE);
  return applicationRecordsHref({ ...d, timezone: ANALYTICS_WEEK_TIMEZONE, days: "custom", start: mondayOf(today), end: today });
}
export function ApplicationMetrics({ d, supplement, company }: { d: AnalyticsData; supplement?: AnalyticsSupplement | null; company?: string }) {
  const outcomeCount = (value: number) => value || d.has_outcome_evidence ? value : null;
  const comparisonMissing = "Comparison unavailable: complete, comparable outcome observation is not recorded.";
  const rows = [
    { icon: "send", label: "Applications sent", value: d.submitted, foot: "Unique submissions", href: applicationRecordsHref(d), trend: supplement?.submissionTrend, reason: d.days === "all" ? "All time has no preceding equivalent interval." : "Submission comparison could not be verified." },
    { icon: "calendar", label: "This week", value: supplement?.currentWeekTotal ?? (d.timezone === ANALYTICS_WEEK_TIMEZONE ? d.week_total : null), foot: "Current calendar week", href: currentWeekHref(d, supplement), trend: supplement?.weekTrend, reason: "Week comparison could not be verified." },
    { icon: "reply", label: "Meaningful replies", value: outcomeCount(d.positive), foot: "Recorded positive employer responses", href: applicationRecordsHref(d, { evidence: "positive" }), reason: comparisonMissing },
    { icon: "file", label: "Online assessments", value: outcomeCount(d.assessments), foot: "Recorded stages reached, including later rejections", href: applicationRecordsHref(d, { evidence: "online_assessment" }), reason: comparisonMissing },
    { icon: "people", label: "Interview invitations", value: d.classified_email_evidence?.categories.interview ?? null, foot: "Invitation emails by receipt date", href: emailRecordsHref(d, { email_kind: "interview", ...(company ? { company } : {}) }), reason: "Comparison unavailable: comparable interview email observation is not recorded." },
  ];
  return <section className="an-metrics" aria-label="Application metrics">{rows.map(row => <Link href={row.href} key={row.label} className="an-metric"><span className="an-icon-tile"><SummaryIcon kind={row.icon} /></span><div><span className="an-metric-label">{row.label}</span><div className="an-metric-number"><strong className={row.value == null ? "an-metric-na" : "an-metric-value"}>{row.value == null ? "Unavailable" : number(row.value)}</strong><Trend value={row.trend} reason={row.reason} /></div><p>{row.foot}</p></div></Link>)}</section>;
}
export function InboxBand({ d, connection, expanded }: { d: AnalyticsData; connection: InboxConnection | null; expanded: boolean }) {
  const pending = d.review.needs_review + d.review.exact_preview + (d.review.deferred ?? 0);
  const active = connection?.connected && connection.state === "ready";
  const status = !connection ? "Status unavailable" : !connection.connected ? "Not connected" : connection.state === "ready" ? "Connected" : connection.state === "paused" ? "Paused" : "Needs attention";
  const synced = active && Boolean(connection?.last_synced_at);
  return <section className={`an-inbox-band${expanded ? " an-inbox-expanded" : ""}`} aria-label="Inbox Intelligence connection"><span className="an-icon-tile"><SummaryIcon kind="mail" /></span><div className="an-inbox-copy"><h2>Inbox Intelligence <span className={active ? "an-connected" : "an-disconnected"}>{status}</span></h2><p>{!connection ? "Connection status could not be loaded." : !connection.connected ? "Read-only Gmail can link employer responses to your applications." : connection.state !== "ready" ? "Open Inbox Intelligence to check the connection." : connection.last_synced_at ? `Last checked ${new Date(connection.last_synced_at).toLocaleString("en-US", { timeZone: d.timezone, month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}. ${number(pending)} messages await review.` : "Read-only Gmail connected. No sync recorded yet."}</p></div>
    {expanded && <div className="an-inbox-workflow" aria-label="Recorded evidence workflow">{[
      { label: "Sync", detail: synced ? "Gmail checked" : "Not verified", done: synced },
      { label: "Match", detail: pending ? `${number(pending)} awaiting review` : "Review in Inbox", done: false },
      { label: "Verify", detail: d.has_outcome_evidence ? "Evidence recorded" : "Not recorded", done: d.has_outcome_evidence },
      { label: "Identity", detail: "Application records", done: false },
    ].map(step => <span key={step.label} title={step.label === "Sync" ? "A check timestamp does not certify complete mailbox coverage." : step.label === "Verify" ? "Individual recorded outcomes do not establish complete response coverage." : step.detail}><i className={step.done ? "an-step-recorded" : ""} aria-hidden="true">{step.done ? "✓" : "·"}</i><span><strong>{step.label}</strong><small>{step.detail}</small></span></span>)}</div>}
    {expanded ? <Link className="an-band-coverage" href={INBOX} title="Complete comparable email observation coverage is not recorded. Open Inbox Intelligence."><span>Coverage ({d.days === "all" ? "All time" : d.days === "custom" ? "custom" : `${d.days} days`})</span><strong>Unavailable <NavIcon name="info" size="sm"/></strong><small>{!connection?.connected && connection?.available ? "Connect Gmail" : "Open Inbox"}</small></Link> : <Link className="an-band-cta" href={INBOX}>{!connection?.connected && connection?.available ? "Connect Gmail" : "Open Inbox Intelligence"}<NavIcon name="right" size="sm" /></Link>}</section>;
}
export function AnalyticsEvidenceNote({ d, connection }: { d: AnalyticsData; connection?: InboxConnection | null }) {
  const excluded = Object.values(d.inbox_audit?.excluded_events ?? {}).reduce((sum, value) => sum + value, 0);
  return <details className="an-audit-note"><summary>About these metrics and evidence</summary><p>Counts separate recorded applications, confirmed stage history and recognized email correspondence, as of {new Date(d.as_of).toLocaleString("en-US", { timeZone: d.timezone })}. Unanswered applications remain pending.</p><p>{connection?.coverage ? coverageText(connection.coverage) : "Gmail coverage has not been verified. Open Inbox Intelligence to check recorded coverage."}</p>{d.inbox_audit && <p>{number(d.inbox_audit.stored_messages)} {d.evidence_scope?"emails in the current email history":"emails imported in total"}; {number(d.inbox_audit.pending_messages)} await your decision; {number(d.inbox_audit.stale_messages)} need a re-read under newer rules. {excluded > 0 && <>{number(excluded)} outcome {excluded === 1 ? "event in this selection is" : "events in this selection are"} excluded from verified email evidence. </>}<Link href={applicationRecordsHref(d)}>Review application evidence</Link></p>}<p>Interview invitations count distinct recognized Inbox emails by receipt date, including emails without a verified application link. They do not assign an application stage. <Link href={applicationRecordsHref(d, { evidence: "interview" })}>Verified application interview stages: {number(d.interviews)}</Link></p><p>Meaningful replies and online assessments describe confirmed application evidence in the selected submission cohort, rather than an email-received interval. Meaningful replies exclude receipts. Outcome effectiveness rates and trends require complete comparable observation, which is not recorded.</p><p>Submission trends compare equivalent local calendar intervals with the same time on their final day. This week compares only the elapsed part of the current week. All-time has no prior comparison. Undated applications never enter dated charts or age-qualified cohorts.</p><Link href={INBOX}>Inspect Inbox evidence and audit history <NavIcon name="right" size="sm" /></Link></details>;
}
