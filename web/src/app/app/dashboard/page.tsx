import Link from "next/link";

import { ApplicationCount } from "@/components/applications/ApplicationCount";
import { ActionQueue } from "@/components/intelligence/ActionQueue";
import { Bars, DayColumns, Kpi } from "@/components/page/PageParts";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import { clean, familyLabel } from "@/lib/format";

export const metadata = { title: "Career Intelligence · ace" };

interface Intel {
  as_of: string; source: string; window_days: number; family: string | null; coverage: string;
  total_submitted: number; filtered_submitted: number; with_posting: number; without_posting: number;
  current_pending: number; current_status: Record<string, number>; confirmed_rejections: number;
  historical_events: Record<string, number>; meaningful_responses_recorded: number; undated: number;
  recruiter_response_rate: {numerator: number; denominator: number; value: number | null; status: string};
  interview_conversion: {numerator: number; denominator: number; value: number | null; status: string};
  median_days_to_first_response: {value: number | null; sample_size: number; status: string};
  today: {submitted: number; qualified_observed: number; email_review: number};
  available_families: string[];
  daily: {date: string; submitted: number}[];
  cohorts: {month: string; statuses: Record<string, number>; sample_size: number}[];
  roles: {family: string; submitted: number; currently_rejected?: number; recorded_responses: number; recorded_interviews: number; open_qualified: number}[];
  companies: {name: string; submitted?: number; open_qualified?: number}[];
  observed_qualified_by_family: {family: string; count: number}[];
  observed_skill_demand: {items: {skill: string; count: number}[]; sample_size: number; status: string};
  verified_petition_companies: number;
  metric_definitions: Record<string, string>;
}

const TABS = [
  ["overview", "Command Center"], ["outcomes", "Outcome Lab"], ["strategy", "Strategy Studio"],
  ["companies", "Company Radar"], ["market", "Market Signals"], ["international", "International Lens"],
  ["actions", "Action Center"],
] as const;

function num(value: number) { return value.toLocaleString("en-US"); }

function trendRows(rows: Intel["daily"], days: number): {date: string; n: number}[] {
  if (days <= 30) return rows.map((row) => ({date: row.date, n: row.submitted}));
  const grouped = new Map<string, number>();
  for (const row of rows) {
    const instant = new Date(`${row.date}T12:00:00Z`);
    if (days <= 90) instant.setUTCDate(instant.getUTCDate() - ((instant.getUTCDay() + 6) % 7));
    const key = days <= 90 ? instant.toISOString().slice(0, 10) : row.date.slice(0, 7);
    grouped.set(key, (grouped.get(key) ?? 0) + row.submitted);
  }
  return [...grouped].map(([date, n]) => ({date, n}));
}

export default async function DashboardPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const tab = TABS.some(([id]) => id === sp.tab) ? String(sp.tab) : "overview";
  const days = ["7", "30", "90", "365"].includes(String(sp.days)) ? String(sp.days) : "90";
  const family = typeof sp.family === "string" ? sp.family : "";
  const data = await apiGetOr<Intel | null>("/api/intelligence", null, { days, ...(family ? {family} : {}) });
  const href = (nextTab: string, nextDays = days, nextFamily = family) => `/app/dashboard?${new URLSearchParams({tab: nextTab, days: nextDays, ...(nextFamily ? {family: nextFamily} : {})})}`;
  const event = (kind: string) => data?.historical_events[kind] ?? 0;
  const trend = data ? trendRows(data.daily, Number(days)) : [];
  return <ScrollArea><div className="pg intelligence-page">
    <div className="page-hero"><div><div className="eyebrow">Your daily decision advantage</div><h1 className="h1">Career Intelligence</h1><p className="subtitle">Know what is moving, what is working and what matters next.</p></div>
      <form action="/app/dashboard" className="intelligence-filters"><input type="hidden" name="tab" value={tab}/><label>Period<select name="days" defaultValue={days}><option value="7">7 days</option><option value="30">30 days</option><option value="90">90 days</option><option value="365">1 year</option></select></label><label>Role family<select name="family" defaultValue={family}><option value="">All role families</option>{data?.available_families.map((role) => <option key={role} value={role}>{familyLabel(role)}</option>)}</select></label><button className="btn" type="submit">Apply</button></form>
    </div>
    {!data ? <section className="panel"><p>Decision intelligence could not be loaded. Reload to try again.</p></section> : <>
      <div className="intelligence-freshness">ACE records as of {new Date(data.as_of).toLocaleString("en-US")}. Source: {data.source}. Historical event coverage: {data.coverage === "partial" ? "Partial" : "Recorded"}.</div>
      <nav className="intelligence-tabs" aria-label="Decision intelligence views">{TABS.map(([id,label]) => <Link key={id} className={tab === id ? "on" : ""} href={href(id)} aria-current={tab === id ? "page" : undefined}>{label}</Link>)}</nav>
      {tab === "overview" && <>
        <section className="intelligence-brief"><div><div className="eyebrow">Decision intelligence · morning brief</div><h2>Where should your next hour go?</h2><p>{num(data.today.qualified_observed)} qualifying opportunities were first seen today. {num(data.today.submitted)} applications were submitted today. {num(data.today.email_review)} emails need review. {data.current_pending ? `${num(data.current_pending)} applications have no confirmed terminal outcome.` : "No pending applications are recorded."}</p></div><div className="intelligence-brief-count"><strong>{num(data.current_pending)}</strong><span>pending</span></div></section>
        <div className="intelligence-kpis"><Kpi label={family ? "Applications in role" : "Applications"} value={family ? num(data.filtered_submitted) : <ApplicationCount />} foot={family ? `${num(data.total_submitted)} lifetime across all roles` : `${num(data.with_posting)} with a posting, ${num(data.without_posting)} external`} href="/app/applications"/><Kpi label="Recorded meaningful responses" value={num(data.meaningful_responses_recorded)} foot={data.coverage === "partial" ? "Partial historical coverage" : "Distinct applications"} href="/app/applications/inbox"/><Kpi label="Current rejections" value={num(data.confirmed_rejections)} foot="Still counted in submitted total" href="/app/applications"/><Kpi label="Recorded interviews" value={num(event("interview"))} foot="Historical event records" href="/app/applications/inbox"/><Kpi label="Awaiting confirmed outcome" value={num(data.current_pending)} foot="Silence is not rejection" href="/app/applications"/></div>
        <div className="intelligence-grid"><section className="panel"><div className="section-head"><h2>From opportunities to actual outcomes</h2><Link href={href("outcomes")}>Analyze outcomes</Link></div><div className="intelligence-journey"><div><small>01 · Observed qualified</small><strong>{num(data.observed_qualified_by_family.reduce((n,r)=>n+r.count,0))}</strong><span>First seen in selected period</span></div><div><small>02 · Submitted</small><strong>{num(data.total_submitted)}</strong><span>Lifetime, including external</span></div><div><small>03 · Recorded response</small><strong>{num(data.meaningful_responses_recorded)}</strong><span>Partial history where noted</span></div><div><small>04 · Interview</small><strong>{num(event("interview"))}</strong><span>Recorded event</span></div></div><p className="quiet-note">Discovery and submitted applications are different populations. External applications remain in the submitted count.</p></section><section className="panel"><div className="section-head"><h2>Attention queue</h2><Link href={href("actions")}>See all actions</Link></div><p><Link href="/app/pulls">Review fresh qualifying Pulls</Link></p><p><Link href="/app/applications">Inspect {num(data.current_pending)} pending applications</Link></p><p><Link href="/app/applications/inbox">Review unmatched email evidence</Link></p></section></div>
        <section className="panel"><h2>Application pace over time</h2><p>Submitted applications by {Number(days) <= 30 ? "day" : Number(days) <= 90 ? "week" : "month"} in the selected period.</p><DayColumns days={trend} label="Submitted applications over time"/><p className="quiet-note">{num(data.undated)} applications have no recorded submission date.</p><details><summary>View exact trend values</summary><table><thead><tr><th>Period</th><th>Submitted</th></tr></thead><tbody>{trend.map((row)=><tr key={row.date}><td>{row.date}</td><td>{row.n}</td></tr>)}</tbody></table></details></section>
      </>}
      {tab === "outcomes" && <><div className="intelligence-kpis"><Kpi label="Response rate" value={data.recruiter_response_rate.value == null ? "Not available" : `${Math.round(100*data.recruiter_response_rate.value)}%`} foot={`${num(data.recruiter_response_rate.numerator)} of ${num(data.recruiter_response_rate.denominator)} submissions at least 30 days old. ${data.recruiter_response_rate.status} coverage.`}/><Kpi label="Interview conversion" value={data.interview_conversion.value == null ? "Not available" : `${Math.round(100*data.interview_conversion.value)}%`} foot={`${num(data.interview_conversion.numerator)} of ${num(data.interview_conversion.denominator)} submitted. ${data.interview_conversion.status} coverage.`}/><Kpi label="Median first response" value={data.median_days_to_first_response.value == null ? "Not available" : `${data.median_days_to_first_response.value.toFixed(1)} days`} foot={`${num(data.median_days_to_first_response.sample_size)} dated response events`}/></div><div className="intelligence-grid"><section className="panel"><h2>Application cohorts</h2><p>Month submitted and current state. Pending applications remain open to future outcomes.</p><div className="intelligence-table"><div className="intelligence-tr head"><span>Submitted month</span><span>Sample</span><span>Pending</span><span>Rejected</span></div>{data.cohorts.map((c)=><div className="intelligence-tr" key={c.month}><span>{c.month}</span><span>{num(c.sample_size)}</span><span>{num(c.sample_size-(c.statuses.rejected??0)-(c.statuses.accepted??0)-(c.statuses.withdrawn??0))}</span><span>{num(c.statuses.rejected??0)}</span></div>)}</div>{!data.cohorts.length && <p>No dated applications in this cohort view.</p>}</section><section className="panel"><h2>Outcome evidence</h2><Bars empty="No event history has been recorded yet." rows={[["Recruiter replies","recruiter_reply"],["Online assessments","online_assessment"],["Interviews","interview"],["Offers","offer"]].map(([label,key])=>({label,n:event(key)}))}/><p className="quiet-note">One application can have an assessment, interview and later rejection. Older stages without an event timestamp cannot be reconstructed.</p></section></div></>}
      {tab === "strategy" && <div className="intelligence-grid"><section className="panel"><h2>Role strategy</h2><p>Current openings and lifetime submissions by role. Responses and interviews use the recorded event ledger.</p><div className="intelligence-table"><div className="intelligence-tr five head"><span>Role family</span><span>Open</span><span>Submitted</span><span>Responses</span><span>Interviews</span></div>{data.roles.map((r)=><div className="intelligence-tr five" key={r.family}><span>{familyLabel(r.family)}</span><span>{num(r.open_qualified)}</span><span>{num(r.submitted)}</span><span>{num(r.recorded_responses)}</span><span>{num(r.recorded_interviews)}</span></div>)}</div>{!data.roles.length&&<p>No applications with a role family are recorded.</p>}</section><section className="panel"><h2>Submitted resume comparisons</h2><p>Not available for historical applications without a recorded submitted resume version. A current resume in Resume Studio does not identify the version sent with an application.</p><p>Role counts show sample sizes. They do not establish that a resume caused an outcome.</p></section></div>}
      {tab === "companies" && <div className="intelligence-grid"><section className="panel"><h2>Employer radar</h2><p>Companies with recorded applications or current qualifying openings. Open each company to inspect official evidence.</p>{data.companies.map((c)=><Link className="intelligence-company" href={`/app/company/${encodeURIComponent(c.name)}`} key={c.name}><strong>{clean(c.name)}</strong><span>{num(c.open_qualified??0)} open · {num(c.submitted??0)} submitted</span></Link>)}{!data.companies.length&&<p>No company activity is recorded.</p>}</section><section className="panel"><h2>Sponsorship evidence</h2><p>{num(data.verified_petition_companies)} companies have verified official petition reports connected to their legal entity.</p><p>A certified DOL LCA is not a visa grant. An employer petition approval rate is not a job-specific sponsorship probability.</p></section></div>}
      {tab === "market" && <div className="intelligence-grid"><section className="panel"><h2>Observed role demand</h2><Bars empty="No qualifying postings were first observed in this period." rows={data.observed_qualified_by_family.map((r)=>({label:familyLabel(r.family),n:r.count,href:`/app/opportunities?family=${encodeURIComponent(r.family)}`}))}/><p className="quiet-note">ACE observed employer postings within selected source coverage, not the national labor market.</p></section><section className="panel"><h2>Skills named in ACE postings</h2><Bars empty="No named skills were found in the sampled qualifying postings." rows={data.observed_skill_demand.items.map((r)=>({label:r.skill,n:r.count}))}/><p className="quiet-note">{num(data.observed_skill_demand.sample_size)} newest qualifying postings sampled. {data.observed_skill_demand.status === "partial" ? "More postings exist outside this sample." : "All observed postings in this period were sampled."}</p><p><Link href="/app/coverage">Inspect source health and coverage</Link>. Source changes can affect these counts.</p></section></div>}
      {tab === "international" && <div className="intelligence-grid"><section className="panel"><h2>International student evidence</h2><p>Company petition reports are shown only after official source and legal entity verification. Unknown work authorization language stays unknown.</p><p>Verified company histories: {num(data.verified_petition_companies)}.</p></section><section className="panel"><h2>How to read H-1B evidence</h2><p>USCIS I-129 petition decisions and DOL LCA certifications are separate measurements. Neither establishes an individual offer or visa outcome. Company workforce sponsorship rate is unavailable without a verified denominator.</p></section></div>}
      {tab === "actions" && <><div className="intelligence-grid"><section className="panel"><h2>Daily action center</h2><p><Link href="/app/pulls">Review newly qualifying opportunities</Link> from the latest Pulls.</p><p><Link href="/app/applications">Review {num(data.current_pending)} pending applications</Link>. Follow-up timing requires a reliable application date.</p><p><Link href="/app/applications/inbox">Review inbox reconciliation</Link> for ambiguous messages.</p></section><section className="panel"><h2>Data quality actions</h2><p>{num(data.undated)} applications have no recorded submission date. ACE does not invent historical dates.</p><p>Recorded response coverage: {data.coverage === "partial" ? "Partial" : "Complete for events recorded since the ledger began"}.</p></section></div><ActionQueue /></>}
      <details className="panel intelligence-definitions"><summary>Source freshness and metric definitions</summary><p>As of {new Date(data.as_of).toLocaleString("en-US")}. Window: {data.window_days} days. Sample: {num(data.filtered_submitted)} applications in the selected role filter.</p>{Object.entries(data.metric_definitions).map(([key,value])=><p key={key}><strong>{key.replaceAll("_"," ")}: </strong>{value}</p>)}</details>
    </>}
  </div></ScrollArea>;
}
