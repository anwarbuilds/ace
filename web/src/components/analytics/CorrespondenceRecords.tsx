import Link from "next/link";
import Form from "next/form";
import { CompanyIdentity } from "@/components/CompanyIdentity";
import type { ApplicationAnalyticsEmailRecords } from "@/lib/analytics";
import { clean, familyLabel } from "@/lib/format";
import { KIND, STATE } from "@/lib/inboxLabels";

const SIZES=[25,50,100];
const INBOX="/app/applications/inbox";

/** The same effective receipt-date evidence as the Analytics category totals. */
export function CorrespondenceRecords({d,query}:{d:ApplicationAnalyticsEmailRecords;query:Record<string,string>}) {
  const href=(changes:Record<string,string|null>)=>{
    const next=new URLSearchParams(query);
    next.delete("records");next.set("emails","1");
    for(const [key,value] of Object.entries(changes)){if(value)next.set(key,value);else next.delete(key);}
    return `/app/applications/analytics?${next}`;
  };
  const back=new URLSearchParams();
  for(const key of ["days","start","end","tz","family","company"])if(query[key])back.set(key,query[key]);
  if(query.email_scope==="company")back.set("tab","companies");
  const evidence=d.classified_email_evidence;
  const start=evidence?.start??d.evidence_scope?.start??(d.days==="all"?"All dates":d.start);
  const end=evidence?.end??d.end;
  const limit=d.email_limit;
  const pages=Math.max(1,Math.ceil(d.email_total/limit));
  const current=Math.min(pages,Math.floor(d.email_offset/limit)+1);
  const day=(iso:string)=>new Date(iso).toLocaleDateString("en-US",{timeZone:d.timezone,month:"short",day:"numeric",year:"numeric"});
  const selected=[query.email_kind?KIND[query.email_kind]??clean(query.email_kind.replaceAll("_"," ")):null,query.email_scope==="company"?"Company-only evidence":null,query.family?familyLabel(query.family):null,query.company].filter(Boolean);
  const kept=Object.entries(query).filter(([key])=>!["records","q","offset"].includes(key));
  return <div className="an-page an-records-page">
    <div className="an-hero"><div><div className="an-eyebrow">Inbox evidence / Analytics selection</div><h1>Recruiting email evidence</h1><p>{d.email_total.toLocaleString("en-US")} distinct effective {d.email_total===1?"email":"emails"} · Receipt dates {start} to {end} · {d.timezone}</p></div></div>
    <div className="an-record-links"><Link className="btn" href={href({days:"all",start:null,end:null,offset:null})}>All time</Link><Link className="btn" href={`/app/analytics?${back}`}>Back to Analytics</Link><Link className="btn" href={INBOX}>Open Inbox Intelligence</Link></div>
    {selected.length>0&&<p className="an-record-selection">{selected.join(" · ")}</p>}
    <section className="an-panel">
      <div className="an-panel-head"><div><h2>Emails in this selection</h2><p>Newest receipt first. Effective Inbox meanings include owner corrections and exclude superseded or undone evidence.</p></div></div>
      <Form action="/app/applications/analytics" className="an-record-search" role="search">
        {kept.map(([key,value])=><input key={key} type="hidden" name={key} value={value}/>)}
        <label>Search these emails<input type="search" name="q" defaultValue={query.q??""} placeholder="Subject or verified company" autoComplete="off"/></label>
        <button className="btn primary" type="submit">Search</button>
        {query.q&&<Link className="btn" href={href({q:null,offset:null})}>Clear search</Link>}
        <span className="an-page-size">Per page {SIZES.map(size=><Link key={size} href={href({limit:String(size),offset:null})} aria-current={size===limit?"true":undefined}>{size}</Link>)}</span>
      </Form>
      <div className="an-table-wrap"><table className="an-table an-record-table"><thead><tr><th>Email and meaning</th><th>Received</th><th>Verified connection</th><th>Inbox decision</th><th>Evidence</th></tr></thead><tbody>{d.email_records.map(row=><tr key={row.id} className="an-record-row">
        <th><strong>{clean(row.subject)||"No subject"}</strong><span className="an-record-role">{KIND[row.classification]??clean(row.classification.replaceAll("_"," "))}</span></th>
        <td data-label="Received"><time dateTime={row.received_at}>{day(row.received_at)}</time></td>
        <td data-label="Verified connection">{row.company&&<CompanyIdentity name={row.company}/>}<p>{row.application_key?"Verified application link":row.company?"Company evidence; role not assigned":"No verified application link"}</p>{row.application_key?.startsWith("job:")&&<Link className="an-jump" href={`/app/jobs/${row.application_key.slice(4)}`}>Open application</Link>}</td>
        <td data-label="Inbox decision">{STATE[row.decision]??clean(row.decision.replaceAll("_"," "))}</td>
        <td data-label="Evidence"><Link className="an-jump" href={`${INBOX}?message=${row.id}`}>View email</Link></td>
      </tr>)}</tbody></table></div>
      {!d.email_records.length&&<p>No effective recruiting emails match this receipt-date selection. No application stage has been inferred.</p>}
      <div className="an-record-pagination"><span>{d.email_total?`${d.email_offset+1} to ${Math.min(d.email_total,d.email_offset+d.email_records.length)} of ${d.email_total.toLocaleString("en-US")} · Page ${current} of ${pages}`:"0 emails"}</span>{pages>1&&<nav className="an-pager" aria-label="Email evidence pages">
        {current>1?<Link className="btn" href={href({offset:current>2?String((current-2)*limit):null})}>Previous emails</Link>:<span className="btn" aria-disabled="true">Previous emails</span>}
        {current<pages?<Link className="btn" href={href({offset:String(current*limit)})}>Next emails</Link>:<span className="btn" aria-disabled="true">Next emails</span>}
      </nav>}</div>
    </section>
    <p className="an-foot">Each effective message appears once. Email receipt dates are separate from application submission dates. Recognized correspondence does not establish a verified application stage; a later rejection preserves earlier valid assessment and interview history.</p>
  </div>;
}
