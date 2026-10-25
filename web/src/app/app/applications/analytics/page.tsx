import Link from "next/link";
import { AnalyticsRefresh } from "@/components/analytics/AnalyticsRefresh";
import { CompanyLogo } from "@/components/CompanyLogo";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import type { ApplicationAnalyticsRecords } from "@/lib/analytics";
import { clean, familyLabel, STATUS_LABEL } from "@/lib/format";
import { getPrefs } from "@/lib/prefs";
import type { ApplicationStatus } from "@/lib/types";
import "../../analytics/analytics.css";

export const metadata={title:"Application records · ace"};
export default async function ApplicationAnalyticsRecordsPage({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}) {
  const sp=await searchParams;
  const prefs=await getPrefs();
  const query:Record<string,string>={records:"1",tz:prefs.tz};
  for(const key of ["days","start","end","family","company","status","evidence","eligible","timed","offset","tz"]) if(typeof sp[key]==="string")query[key]=sp[key];
  const data=await apiGetOr<ApplicationAnalyticsRecords|null>("/api/analytics",null,query);
  if(!data)return <div className="pg"><h1>Application records</h1><p role="alert">This selection could not be loaded. Check the filters or return to Analytics.</p><Link className="btn" href="/app/analytics">Back to Analytics</Link></div>;
  const analyticsQuery=new URLSearchParams();
  for(const key of ["days","start","end","family"])if(query[key])analyticsQuery.set(key,query[key]);
  const pageHref=(offset:number)=>{const next=new URLSearchParams(query);next.delete("records");next.set("offset",String(offset));return `/app/applications/analytics?${next}`;};
  const enabled=(value:string|undefined)=>value==="1"||value==="true";
  const selected=[query.family?familyLabel(query.family):null,query.company,query.status?STATUS_LABEL[query.status as ApplicationStatus]:null,query.evidence?`Recorded ${clean(query.evidence.replaceAll("_"," "))} evidence`:null,enabled(query.eligible)?"Submitted at least 30 days ago":null,enabled(query.timed)?"Reliable response timing":null].filter(Boolean);
  return <ScrollArea list><AnalyticsRefresh/><div className="an-page an-records-page"><div className="an-hero"><div><div className="an-eyebrow">Applications / Analytics selection</div><h1>Application records</h1><p>{data.record_total.toLocaleString("en-US")} unique applications · {data.days==="all"?"All time":`${data.start} to ${data.end}`} · {data.timezone}</p></div></div><div className="an-record-links"><Link className="btn" href={`/app/analytics?${analyticsQuery}`}>Back to Analytics</Link><Link className="btn" href="/app/applications">All applications and controls</Link><a className="btn" href="/api/applications/export.csv" download>Export full application history</a></div>{selected.length>0&&<p className="an-record-selection">{selected.join(" · ")}</p>}<section className="an-panel"><div className="an-panel-head"><div><h2>Applications in this selection</h2><p>Submission records and current stages. Open a stored job to use its existing application controls.</p></div></div><div className="an-table-wrap"><table className="an-table an-record-table"><thead><tr><th>Company and role</th><th>Submitted</th><th>Current status</th><th>Recorded outcome evidence</th><th>Application</th></tr></thead><tbody>{data.records.map(record=><tr key={record.key} className="an-record-row" data-status={record.status}><th><div className="an-record-company"><CompanyLogo name={record.company}/><strong>{clean(record.company)}</strong></div><span className="an-record-role">{clean(record.title)}</span><span className="an-record-key">{record.key} · {familyLabel(record.family)}</span></th><td data-label="Submitted">{record.submitted_at?new Date(record.submitted_at).toLocaleDateString("en-US",{timeZone:data.timezone}):"Not recorded"}</td><td data-label="Current status">{STATUS_LABEL[record.status as ApplicationStatus]??clean(record.status)}</td><td data-label="Recorded outcome evidence">{record.event_types.length?record.event_types.map(kind=>clean(kind.replaceAll("_"," "))).join(", "):"No recorded response"}</td><td data-label="Application">{record.href?<Link className="an-jump" href={record.href}>Open application</Link>:<span>External history record</span>}</td></tr>)}</tbody></table></div>{!data.records.length&&<p>No applications match this selection. No status or evidence has been inferred.</p>}<div className="an-record-pagination">{data.record_offset>0&&<Link className="btn" href={pageHref(Math.max(0,data.record_offset-data.record_limit))}>Previous records</Link>}<span>{data.record_total?`${data.record_offset+1} to ${Math.min(data.record_total,data.record_offset+data.records.length)} of ${data.record_total}`:"0 records"}</span>{data.record_offset+data.record_limit<data.record_total&&<Link className="btn" href={pageHref(data.record_offset+data.record_limit)}>Next records</Link>}</div></section><p className="an-foot">Each application appears once. Multiple verified events do not create extra applications. The lifetime Applied badge remains unchanged by filters.</p></div></ScrollArea>;
}
