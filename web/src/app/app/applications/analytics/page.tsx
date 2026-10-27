import Form from "next/form";
import Link from "next/link";
import { AnalyticsRefresh } from "@/components/analytics/AnalyticsRefresh";
import { CompanyLogo } from "@/components/CompanyLogo";
import { ScrollArea } from "@/components/shell/ScrollArea";
import { apiGetOr } from "@/lib/api";
import type { ApplicationAnalyticsRecords } from "@/lib/analytics";
import { clean, familyLabel, STATUS_LABEL } from "@/lib/format";
import { getPrefs } from "@/lib/prefs";
import type { ApplicationStatus } from "@/lib/types";
import { KIND, STATE } from "@/lib/inboxLabels";
import "../../analytics/analytics.css";

export const metadata={title:"Application records · ace"};
const FILTERS=["days","start","end","family","company","status","evidence","eligible","timed","offset","limit","q","tz"];
const SIZES=[25,50,100];
const EXCLUDED:Record<string,string>={before_application_window:"Email predates the application window",future_timestamp:"Outcome date is in the future",missing_email:"Stored email is missing",conflicting_targets:"Email has conflicting application links",email_not_confirmed_for_application:"Email is not confirmed for this application",unconfirmed_actor:"Outcome is not owner-confirmed or verified"};
const EVIDENCE:Record<string,string>={rejection:"Rejection",online_assessment:"Online assessment",interview:"Interview",interviewing:"Interview",recruiter_reply:"Recruiter reply",screening:"Screening",offer:"Offer",accepted:"Accepted"};

/** Page numbers to show: the first, the last and two either side of the current one. */
function pageNumbers(current:number,pages:number):(number|null)[] {
  const shown=[...new Set([1,pages,...[-2,-1,0,1,2].map(step=>current+step)])].filter(page=>page>=1&&page<=pages).sort((a,b)=>a-b);
  return shown.flatMap((page,index)=>index&&page-shown[index-1]>1?[null,page]:[page]);
}

export default async function ApplicationAnalyticsRecordsPage({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}) {
  const sp=await searchParams;
  const prefs=await getPrefs();
  const query:Record<string,string>={records:"1",tz:prefs.tz};
  for(const key of FILTERS) if(typeof sp[key]==="string"&&sp[key])query[key]=sp[key];
  if(query.evidence==="rejection"&&!query.days&&!query.start&&!query.end)query.days="all";
  const data=await apiGetOr<ApplicationAnalyticsRecords|null>("/api/analytics",null,query);
  if(!data)return <div className="pg"><h1>Application records</h1><p role="alert">This selection could not be loaded. Check the filters or return to Analytics.</p><Link className="btn" href="/app/analytics">Back to Analytics</Link></div>;
  const analyticsQuery=new URLSearchParams();
  for(const key of ["days","start","end","family"])if(query[key])analyticsQuery.set(key,query[key]);
  // Rejected companies live on the Companies tab; return there from them.
  if(query.evidence==="rejection")analyticsQuery.set("tab","companies");
  const href=(changes:Record<string,string|null>)=>{const next=new URLSearchParams(query);next.delete("records");for(const [key,value] of Object.entries(changes)){if(value)next.set(key,value);else next.delete(key);}return `/app/applications/analytics?${next}`;};
  const limit=data.record_limit;
  const pages=Math.max(1,Math.ceil(data.record_total/limit));
  const current=Math.min(pages,Math.floor(data.record_offset/limit)+1);
  const pageHref=(page:number)=>href({offset:page>1?String((page-1)*limit):null});
  const enabled=(value:string|undefined)=>value==="1"||value==="true";
  const rejected=query.evidence==="rejection";
  const day=(iso:string)=>new Date(iso).toLocaleDateString("en-US",{timeZone:data.timezone,month:"short",day:"numeric",year:"numeric"});
  const selected=[query.family?familyLabel(query.family):null,query.company,query.status?STATUS_LABEL[query.status as ApplicationStatus]:null,query.evidence&&!rejected?`Recorded ${clean(query.evidence.replaceAll("_"," "))} evidence`:null,enabled(query.eligible)?"Submitted at least 30 days ago":null,enabled(query.timed)?"Reliable response timing":null].filter(Boolean);
  const kept=Object.entries(query).filter(([key])=>!["records","q","offset"].includes(key));
  const shownFrom=data.record_total?data.record_offset+1:0;
  const shownTo=Math.min(data.record_total,data.record_offset+data.records.length);
  return <ScrollArea list><AnalyticsRefresh/><div className="an-page an-records-page">
    <div className="an-hero"><div><div className="an-eyebrow">Applications / Analytics selection</div><h1>{rejected?"Rejected applications":"Application records"}</h1><p>{data.record_total.toLocaleString("en-US")} unique {data.record_total===1?"application":"applications"} ·{data.days==="all"?"All time":`${data.start} to ${data.end}`} · {data.timezone}</p></div></div>
    <div className="an-record-links"><Link className="btn" href={href({days:"all",start:null,end:null,offset:null})}>All time</Link><Link className="btn" href={`/app/analytics?${analyticsQuery}`}>Back to Analytics</Link><Link className="btn" href="/app/applications">All applications and controls</Link><a className="btn" href="/api/applications/export.csv" download>Export full application history</a></div>
    {selected.length>0&&<p className="an-record-selection">{selected.join(" · ")}</p>}
    <section className="an-panel">
      <div className="an-panel-head"><div><h2>{rejected?"Rejections in this selection":"Applications in this selection"}</h2><p>{rejected?"Newest rejection first. A date and View email appear when an email recorded it.":"Submission records and current stages. Open a stored job to use its existing application controls."}</p></div></div>
      <Form action="/app/applications/analytics" className="an-record-search" role="search">
        {kept.map(([key,value])=><input key={key} type="hidden" name={key} value={value}/>)}
        <label>Search {rejected?"rejected applications":"these applications"}<input type="search" name="q" defaultValue={data.record_query} placeholder="Company, role or job ID" autoComplete="off"/></label>
        <button className="btn primary" type="submit">Search</button>
        {data.record_query&&<Link className="btn" href={href({q:null,offset:null})}>Clear search</Link>}
        <span className="an-page-size">Per page {SIZES.map(size=><Link key={size} href={href({limit:size===50?null:String(size),offset:null})} aria-current={size===limit?"true":undefined}>{size}</Link>)}</span>
      </Form>
      {data.record_query&&<p className="an-record-selection">{data.record_total?`${data.record_total.toLocaleString("en-US")} ${data.record_total===1?"match":"matches"}`:"No matches"} for &ldquo;{data.record_query}&rdquo;.</p>}
      <div className="an-table-wrap"><table className="an-table an-record-table"><thead><tr><th>Company and role</th><th>Submitted</th><th>Current status</th><th>Recorded outcome evidence</th><th>Application</th></tr></thead><tbody>{data.records.map(record=><tr key={record.key} className="an-record-row" data-status={record.status}>
        <th><div className="an-record-company"><CompanyLogo name={record.company}/><strong>{clean(record.company)}</strong></div><span className="an-record-role">{clean(record.title)}</span><span className="an-record-key">{record.key} · {familyLabel(record.family)}{record.requisition_id?` · Job ID ${clean(record.requisition_id)}`:""}</span></th>
        <td data-label="Submitted">{record.submitted_at?new Date(record.submitted_at).toLocaleDateString("en-US",{timeZone:data.timezone}):"Not recorded"}</td>
        <td data-label="Current status">{STATUS_LABEL[record.status as ApplicationStatus]??clean(record.status)}</td>
        <td data-label="Recorded outcome evidence">{record.evidence.length?<ul className="an-evidence-list">{record.evidence.map(item=><li key={item.kind}><span>{EVIDENCE[item.kind]??clean(item.kind.replaceAll("_"," "))}</span>{item.at?<time dateTime={item.at}>{day(item.at)}</time>:<small>no date</small>}{item.predates_mark&&<small>Email received before the ACE application mark; response time unavailable</small>}{item.message_id?<Link className="an-jump" href={`/app/applications/inbox?message=${item.message_id}`}>View email</Link>:null}</li>)}</ul>:"No recorded response"}{record.excluded_evidence?.map((item,index)=><p key={`${item.message_id}:${index}`}><small>{EXCLUDED[item.reason]??"Email evidence needs review"}. Not counted as verified email evidence.</small> <Link className="an-jump" href={`/app/applications/inbox?message=${item.message_id}`}>Review excluded email</Link></p>)}</td>
        <td data-label="Application">{record.href?<Link className="an-jump" href={record.href}>Open application</Link>:<span>External history record</span>}</td>
      </tr>)}</tbody></table></div>
      {!data.records.length&&<p>{data.record_query?"No applications in this selection match that search. Check the spelling or clear the search.":"No applications match this selection. No status or evidence has been inferred."}</p>}
      {!data.record_total&&data.record_query&&<section className="an-panel" aria-label="Where is my application?">
        <h2>Where is my application?</h2>
        <p>This list uses submission dates and the selected status, role and evidence filters. An email may be imported without a recorded rejection.</p>
        <Link className="an-jump" href={href({days:"all",start:null,end:null,offset:null,evidence:null,status:null,family:null,company:null,eligible:null,timed:null})}>Search all applications, all time</Link>
        <h3>Applications across all dates and statuses</h3>
        <p>{data.not_listed?.application_total??0} found{(data.not_listed?.application_total??0)>25?", showing the newest 25":""}.</p>
        {data.not_listed?.applications.map(record=><div className="an-record-selection" key={record.key}>
          <div className="an-record-company"><CompanyLogo name={record.company}/><strong>{clean(record.company)}</strong></div>
          <p>{clean(record.title)} · {STATUS_LABEL[record.status as ApplicationStatus]??clean(record.status)} · Submitted {record.submitted_at?day(record.submitted_at):"date not recorded"}{record.outside_range?" · Outside the selected submission dates":record.submitted_at?" · Within the selected submission dates":" · Submission date not recorded"}</p>
          <Link className="an-jump" href={record.href}>Open application</Link>
        </div>)}
        <h3>Related imported emails</h3>
        <p>{data.not_listed?.email_total??0} found{(data.not_listed?.email_total??0)>25?", showing the newest 25":""}.</p>
        {data.not_listed?.emails.map(email=><p key={email.id}><Link className="an-jump" href={`/app/applications/inbox?message=${email.id}`}>{clean(email.subject)||"No subject"}</Link> · {STATE[email.decision]??clean(email.decision)} · {KIND[email.classification]??clean(email.classification)} · {day(email.received_at)}</p>)}
        <p><Link className="an-jump" href={`/app/applications/inbox?decision=all&q=${encodeURIComponent(data.record_query)}`}>Search imported email and verify Gmail coverage</Link></p>
      </section>}
      <div className="an-record-pagination">
        <span>{data.record_total?`${shownFrom} to ${shownTo} of ${data.record_total.toLocaleString("en-US")} · Page ${current} of ${pages}`:"0 records"}</span>
        {pages>1&&<nav className="an-pager" aria-label="Record pages">
          {current>1?<Link className="btn" href={pageHref(current-1)}>Previous records</Link>:<span className="btn" aria-disabled="true">Previous records</span>}
          {pageNumbers(current,pages).map((page,index)=>page===null?<span key={`gap-${index}`} className="an-gap" aria-hidden="true">…</span>:page===current?<span key={page} className="an-page" aria-current="page">{page}</span>:<Link key={page} className="an-page" href={pageHref(page)} aria-label={`Page ${page}`}>{page}</Link>)}
          {current<pages?<Link className="btn" href={pageHref(current+1)}>Next records</Link>:<span className="btn" aria-disabled="true">Next records</span>}
        </nav>}
      </div>
    </section>
    <p className="an-foot">Each application appears once. Multiple verified events do not create extra applications. The lifetime Applied badge remains unchanged by filters.</p>
  </div></ScrollArea>;
}
