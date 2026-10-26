"use client";

import { useEffect, useMemo, useState } from "react";
import { CompanyLogo } from "@/components/CompanyLogo";
import { EmailFrame } from "@/components/inbox/EmailFrame";
import { clean, parseDate, STATUS_LABEL } from "@/lib/format";
import { getJson, RequestError, sendJson } from "@/lib/client";
import type { ApplicationStatus } from "@/lib/types";

export interface InboxMessage {id:number; received_at:string; sender:string; subject:string; snippet:string; classification:string; requisition_id:string|null; decision:string; candidate_keys:string[]; reason:string; selected_application_key:string|null}
export interface InboxApplication {key:string; company:string; title:string; requisition_id:string|null; applied_at:string|null; status:string}
export interface InboxEvent {id:number; application_key:string; kind:string; before:string|null; after:string|null; actor:string; reason:string; recorded_at:string; undo_of_id:number|null; gmail_message_id:number|null}
/** The email as Gmail has it now, read live and never stored. */
export interface FullEmail {sender:string; to:string; subject:string; received_at:string; text:string; document:string; format:string; blocked_images:number; message_id_header:string|null; thread_id:string|null}
type Action = (run:()=>Promise<unknown>, success:string)=>Promise<void>;

export const PENDING = ["review","exact_preview","deferred"];
/** What ACE read the email as. */
export const KIND: Record<string,string> = {rejection:"Rejection",possible_rejection:"Possible rejection",interview:"Interview",online_assessment:"Assessment",offer:"Offer",recruiter_reply:"Recruiter reply",application_confirmation:"Acknowledgement",unknown:"No outcome found"};
/** What happened to it. */
export const STATE: Record<string,string> = {review:"Needs you",exact_preview:"Needs you",deferred:"Decide later",automatic:"Recorded by ACE",manual:"Recorded by you",receipt:"Acknowledgement",update:"Status update",unrelated:"Not about applications",ignored:"Nothing recorded"};
// One click each. The status is what the application becomes; the kind is
// what the email was, so Analytics counts an assessment as an assessment.
const OUTCOMES = [
  {kind:"rejection",status:"rejected",label:"Rejection",hint:"Not moving forward, or the role was filled or closed",done:"Marked rejected"},
  {kind:"online_assessment",status:"screening",label:"Assessment",hint:"Online assessment or coding test",done:"Marked assessment"},
  {kind:"recruiter_reply",status:"screening",label:"Recruiter reply",hint:"A person wrote back about this application",done:"Marked recruiter reply"},
  {kind:"interview",status:"interviewing",label:"Interview",hint:"Interview invitation or scheduling",done:"Marked interviewing"},
  {kind:"offer",status:"offer",label:"Offer",hint:"An offer of employment",done:"Marked offer"},
] as const;
// Filed without changing any application.
const FILINGS = [
  {action:"receipt",label:"Acknowledgement",hint:"Application received, thanks for applying",done:"Filed as an acknowledgement. Nothing changed."},
  {action:"update",label:"Status update",hint:"Still under review, no decision yet",done:"Filed as a status update. Nothing changed."},
  {action:"unrelated",label:"Not about my applications",hint:"Job alerts, newsletters and other mail",done:"Marked not about your applications."},
  {action:"deferred",label:"Decide later",hint:"Keep it waiting for now",done:"Saved for later."},
] as const;
// ACE's reading, as the choice to suggest.
const SUGGEST: Record<string,string> = {rejection:"rejection",possible_rejection:"rejection",interview:"interview",online_assessment:"online_assessment",offer:"offer",recruiter_reply:"recruiter_reply",application_confirmation:"receipt"};
const FILED: Record<string,string> = {receipt:"Filed as an acknowledgement.",update:"Filed as a status update.",unrelated:"Marked not about your applications.",ignored:"ACE found no application outcome in it."};

const dates = (value:string|null)=>value ? new Date(value).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"}) : "Date not recorded";
const status = (value:string)=>STATUS_LABEL[value as ApplicationStatus]??clean(value);
// Email text keeps its lines; dashes and drawn rules are removed like any other text.
const readable = (text:string)=>text.split("\n").map(line=>/^[\s\-_=*~‐-―]+$/.test(line)?"":clean(line)).join("\n").replace(/\n{3,}/g,"\n\n").trim();
const loaded = new Map<number,FullEmail>();

/** "Wayfern Talent <no-reply@ashbyhq.example>" as its name and address. */
export function senderParts(value:string): {name:string; address:string} {
  const match = value.match(/^\s*"?([^"<]*?)"?\s*<([^>]+)>\s*$/);
  return match ? {name:match[1].trim()||match[2], address:match[2]} : {name:value.trim(), address:""};
}

/** "3 minutes ago"; empty until the page knows the time. */
export function since(iso:string|null|undefined, now:number): string {
  const moment = parseDate(iso);
  if (!moment || !now) return "";
  const minutes = Math.floor(Math.max(0, now - moment.getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} ${minutes === 1 ? "minute" : "minutes"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} ${hours === 1 ? "hour" : "hours"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} ${days === 1 ? "day" : "days"} ago`;
}

/** Gmail's own view of the same email, in the connected account. */
function gmailHref(account:string|null|undefined, full:FullEmail|null): string | null {
  if (!account || !full) return null;
  const base = `https://mail.google.com/mail/?authuser=${encodeURIComponent(account)}`;
  const key = full.message_id_header?.replace(/^<|>$/g, "");
  if (key) return `${base}#search/${encodeURIComponent(`rfc822msgid:${key}`)}`;
  return full.thread_id ? `${base}#all/${encodeURIComponent(full.thread_id)}` : null;
}

function AppCard({app}:{app:InboxApplication}) {
  return <div className="inbox-app"><CompanyLogo name={app.company}/><div><strong>{clean(app.company)}</strong><span>{clean(app.title)}</span><small>Applied {dates(app.applied_at)} · {status(app.status)}{app.requisition_id?` · Job ID ${clean(app.requisition_id)}`:""}</small></div></div>;
}

export function InboxReviewPanel({message,applications,events,busy,action,account,now=0}: {message:InboxMessage|null; applications:InboxApplication[]; events:InboxEvent[]; busy:boolean; action:Action; account?:string|null; now?:number}) {
  const id=message?.id;
  const [full,setFull]=useState<FullEmail|null>(()=>id==null?null:loaded.get(id)??null);
  const [fullError,setFullError]=useState("");
  const [plain,setPlain]=useState(false);
  const [targetKey,setTargetKey]=useState(()=>message?.selected_application_key??message?.candidate_keys[0]??"");
  const [choosing,setChoosing]=useState(false);
  const [search,setSearch]=useState("");
  const byKey=useMemo(()=>new Map(applications.map(a=>[a.key,a])),[applications]);
  useEffect(()=>{
    if(id==null||loaded.has(id))return;
    let live=true;
    getJson<FullEmail>(`/api/inbox/messages/${id}/full`).then(result=>{loaded.set(id,result);if(live)setFull(result);})
      .catch(cause=>{if(live)setFullError(cause instanceof RequestError&&cause.status===404?"This email is no longer in Gmail. Showing the saved excerpt.":"The email could not be read from Gmail just now. Showing the saved excerpt.");});
    return ()=>{live=false;};
  },[id]);
  if(!message)return <section className="panel inbox-inspector"><h2>Nothing selected</h2><p>Choose an email on the left to see it exactly as it arrived.</p></section>;

  const pending=PENDING.includes(message.decision);
  const applied=message.decision==="automatic"||message.decision==="manual";
  const target=byKey.get(targetKey);
  const candidates=message.candidate_keys.map(key=>byKey.get(key)).filter((a):a is InboxApplication=>Boolean(a));
  const query=search.trim().toLocaleLowerCase();
  const options=query?applications.filter(a=>`${a.company} ${a.title} ${a.requisition_id??""}`.toLocaleLowerCase().includes(query)).slice(0,30):candidates;
  const linked=message.selected_application_key?byKey.get(message.selected_application_key):undefined;
  const change=events.find(e=>e.gmail_message_id===message.id&&e.kind!=="undo"&&e.application_key===message.selected_application_key&&["owner","verified_automation"].includes(e.actor)&&!events.some(other=>other.undo_of_id===e.id));
  const decide=(outcome:typeof OUTCOMES[number])=>{if(target)void action(()=>sendJson("POST","/api/inbox/review",{message_id:message.id,application_key:target.key,status:outcome.status,expected_status:target.status,confirmed:true,kind:outcome.kind}),`${outcome.done}: ${clean(target.company)}`);};
  const file=(filing:typeof FILINGS[number])=>{void action(()=>sendJson("PATCH",`/api/inbox/messages/${message.id}/decision`,{action:filing.action}),filing.done);};
  const guessed=Boolean(target)&&!message.selected_application_key&&candidates[0]?.key===targetKey;
  const suggest=SUGGEST[message.classification];
  const sender=senderParts(full?.sender??message.sender);
  const gmail=gmailHref(account,full);
  const ago=since(message.received_at,now);

  return <section className="panel inbox-inspector" aria-label="Selected email">
    <header className="inbox-mail-head">
      <div className="inbox-chips">{message.classification!=="unknown"&&<span className={`inbox-kind k-${message.classification}`}>{KIND[message.classification]??clean(message.classification)}</span>}<span className={`inbox-state d-${message.decision}`}>{STATE[message.decision]??clean(message.decision)}</span></div>
      <h2>{clean(full?.subject??message.subject)||"No subject"}</h2>
      <dl className="inbox-mail-meta">
        <dt>From</dt><dd><strong>{clean(sender.name)}</strong>{sender.address&&<span className="inbox-address"> &lt;{sender.address}&gt;</span>}</dd>
        {full?.to?<><dt>To</dt><dd>{clean(full.to)}</dd></>:null}
        <dt>Received</dt><dd>{parseDate(message.received_at)?.toLocaleString("en-US",{weekday:"short",month:"short",day:"numeric",year:"numeric",hour:"numeric",minute:"2-digit"})}{ago?<span className="inbox-address"> ({ago})</span>:null}</dd>
      </dl>
    </header>
    <div className="inbox-mail-body">
      {full?plain?<div className="inbox-full" tabIndex={0} aria-label="Email text">{readable(full.text)||"This email has no text."}</div>:<EmailFrame document={full.document} title={`Email: ${clean(full.subject)||"No subject"}`}/>
        :<div className="inbox-full" tabIndex={0} aria-label="Saved email excerpt">{readable(message.snippet||"No excerpt is stored.")}<small>{fullError||"Loading the email from Gmail"}</small></div>}
      {(full||gmail)&&<div className="inbox-mail-tools">
        {full&&<button className="btn btn-sm" onClick={()=>setPlain(value=>!value)}>{plain?"Show the original email":"Show as plain text"}</button>}
        {gmail&&<a className="btn btn-sm" href={gmail} target="_blank" rel="noopener noreferrer">Open in Gmail</a>}
        {full&&!plain&&full.blocked_images>0&&<small>{full.blocked_images} {full.blocked_images===1?"picture":"pictures"} from the sender&rsquo;s server not loaded, so the sender cannot tell you opened it.</small>}
      </div>}
    </div>
    {applied ? <div className="inbox-decided">
      <h3>{message.decision==="automatic"?"ACE recorded this email.":"You recorded this email."}</h3>
      <p className="inbox-muted">{clean(message.reason)}.</p>
      {linked&&<AppCard app={linked}/>}
      {change?<button className="btn" disabled={busy} onClick={()=>void action(()=>sendJson("POST",`/api/inbox/events/${change.id}/undo`,{}),"Undone. The email is back in your queue.")}>Undo this change</button>:<p className="inbox-muted">Undo it from Audit trail.</p>}
    </div> : <div className="inbox-decide">
      {!pending&&FILED[message.decision]&&<p className="inbox-filed"><strong>{FILED[message.decision]}</strong> Nothing changed. If that is wrong, choose what it is below.</p>}
      <div className="inbox-target">
        <div className="inbox-target-head"><h3>{target?guessed?"ACE thinks this is about":"Application":"Which application?"}</h3>{target&&!choosing&&<button className="btn btn-sm" onClick={()=>setChoosing(true)}>Change</button>}</div>
        {target&&!choosing?<AppCard app={target}/>:<div className="inbox-picker">
          <input autoComplete="off" aria-label="Search your applications" placeholder="Search company, role or job ID" value={search} onChange={event=>setSearch(event.target.value)}/>
          {options.length?<div className="inbox-options">{options.map(a=><button key={a.key} className={a.key===targetKey?"on":""} onClick={()=>{setTargetKey(a.key);setChoosing(false);setSearch("");}}><AppCard app={a}/></button>)}</div>:<p className="inbox-muted">{query?"No application matches that search.":"ACE could not tell which application this is. Search for it above."}</p>}
        </div>}
      </div>
      <div className="inbox-outcomes" role="group" aria-label="What is this email?">
        <h3>What is this email?</h3>
        {pending&&message.reason&&<p className="inbox-muted">Why it waits: {clean(message.reason)}.</p>}
        <p className="inbox-group">Changes the application</p>
        <div className="inbox-choices">{OUTCOMES.map(outcome=><button key={outcome.kind} className={`inbox-choice${suggest===outcome.kind?" suggested":""}`} disabled={busy||!target} onClick={()=>decide(outcome)}><strong>{outcome.label}</strong><span>{outcome.hint}</span>{suggest===outcome.kind&&<em>ACE&rsquo;s reading</em>}</button>)}</div>
        {!target&&<p className="inbox-muted">Choose the application first to record an outcome.</p>}
        <p className="inbox-group">Nothing to change</p>
        <div className="inbox-choices quiet">{FILINGS.filter(filing=>filing.action!=="deferred"||(pending&&message.decision!=="deferred")).map(filing=><button key={filing.action} className={`inbox-choice${suggest===filing.action?" suggested":""}`} disabled={busy||message.decision===filing.action} onClick={()=>file(filing)}><strong>{filing.label}</strong><span>{filing.hint}</span>{suggest===filing.action&&<em>ACE&rsquo;s reading</em>}</button>)}</div>
      </div>
    </div>}
  </section>;
}
