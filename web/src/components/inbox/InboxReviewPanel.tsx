"use client";

import { useEffect, useMemo, useState } from "react";
import { CompanyLogo } from "@/components/CompanyLogo";
import { clean, STATUS_LABEL } from "@/lib/format";
import { getJson, RequestError, sendJson } from "@/lib/client";
import type { ApplicationStatus } from "@/lib/types";

export interface InboxMessage {id:number; received_at:string; sender:string; subject:string; snippet:string; classification:string; requisition_id:string|null; decision:string; candidate_keys:string[]; reason:string; selected_application_key:string|null}
export interface InboxApplication {key:string; company:string; title:string; requisition_id:string|null; applied_at:string|null; status:string}
export interface InboxEvent {id:number; application_key:string; kind:string; before:string|null; after:string|null; actor:string; reason:string; recorded_at:string; undo_of_id:number|null; gmail_message_id:number|null}
type Action = (run:()=>Promise<unknown>, success:string)=>Promise<void>;

export const PENDING = ["review","exact_preview","deferred"];
// One click each. The status is what the application becomes; the kind is
// what the email was, so Analytics counts an assessment as an assessment.
const OUTCOMES = [
  {kind:"rejection",status:"rejected",label:"Rejected",done:"Marked rejected"},
  {kind:"interview",status:"interviewing",label:"Interview",done:"Marked interviewing"},
  {kind:"online_assessment",status:"screening",label:"Assessment",done:"Marked assessment"},
  {kind:"offer",status:"offer",label:"Offer",done:"Marked offer"},
] as const;
export const LOOKS: Record<string,string> = {rejection:"Looks like a rejection",interview:"Looks like an interview invitation",online_assessment:"Looks like an assessment",offer:"Looks like an offer",recruiter_reply:"Looks like a recruiter reply",application_confirmation:"Looks like an application receipt",unknown:"No recruiting outcome found"};
const dates = (value:string|null)=>value ? new Date(value).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"}) : "Date not recorded";
const status = (value:string)=>STATUS_LABEL[value as ApplicationStatus]??clean(value);
// Email text keeps its lines; dashes and drawn rules are removed like any other text.
const readable = (text:string)=>text.split("\n").map(line=>/^[\s\-_=*~‐-―]+$/.test(line)?"":clean(line)).join("\n").replace(/\n{3,}/g,"\n\n").trim();
const loaded = new Map<number,string>();

function AppCard({app}:{app:InboxApplication}) {
  return <div className="inbox-app"><CompanyLogo name={app.company}/><div><strong>{clean(app.company)}</strong><span>{clean(app.title)}</span><small>Applied {dates(app.applied_at)} · {status(app.status)}{app.requisition_id?` · Job ID ${clean(app.requisition_id)}`:""}</small></div></div>;
}

export function InboxReviewPanel({message,applications,events,busy,action}: {message:InboxMessage|null; applications:InboxApplication[]; events:InboxEvent[]; busy:boolean; action:Action}) {
  const id=message?.id;
  const [full,setFull]=useState<string|null>(()=>id==null?null:loaded.get(id)??null);
  const [fullError,setFullError]=useState("");
  const [targetKey,setTargetKey]=useState(()=>message?.selected_application_key??message?.candidate_keys[0]??"");
  const [choosing,setChoosing]=useState(false);
  const [search,setSearch]=useState("");
  const byKey=useMemo(()=>new Map(applications.map(a=>[a.key,a])),[applications]);
  useEffect(()=>{
    if(id==null||loaded.has(id))return;
    let live=true;
    getJson<{text:string}>(`/api/inbox/messages/${id}/full`).then(result=>{const text=readable(result.text);loaded.set(id,text);if(live)setFull(text);})
      .catch(cause=>{if(live)setFullError(cause instanceof RequestError&&cause.status===404?"This email is no longer in Gmail. Showing the saved excerpt.":"The full email could not be loaded. Showing the saved excerpt.");});
    return ()=>{live=false;};
  },[id]);
  if(!message)return <section className="panel inbox-inspector"><h2>Nothing selected</h2><p>Choose an email on the left.</p></section>;

  const pending=PENDING.includes(message.decision);
  const target=byKey.get(targetKey);
  const candidates=message.candidate_keys.map(key=>byKey.get(key)).filter((a):a is InboxApplication=>Boolean(a));
  const query=search.trim().toLocaleLowerCase();
  const options=query?applications.filter(a=>`${a.company} ${a.title} ${a.requisition_id??""}`.toLocaleLowerCase().includes(query)).slice(0,30):candidates;
  const linked=message.selected_application_key?byKey.get(message.selected_application_key):undefined;
  const change=events.find(e=>e.gmail_message_id===message.id&&e.kind!=="undo"&&e.application_key===message.selected_application_key&&["owner","verified_automation"].includes(e.actor)&&!events.some(other=>other.undo_of_id===e.id));
  const decide=(outcome:typeof OUTCOMES[number])=>{if(target)void action(()=>sendJson("POST","/api/inbox/review",{message_id:message.id,application_key:target.key,status:outcome.status,expected_status:target.status,confirmed:true,kind:outcome.kind}),`${outcome.done}: ${clean(target.company)}`);};
  const file=(kind:"receipt"|"unrelated"|"deferred",done:string)=>{void action(()=>sendJson("PATCH",`/api/inbox/messages/${message.id}/decision`,{action:kind}),done);};
  const applied=message.decision==="automatic"||message.decision==="manual";
  const guessed=Boolean(target)&&!message.selected_application_key&&candidates[0]?.key===targetKey;

  return <section className="panel inbox-inspector" aria-label="Selected email">
    <div className="inbox-mail-head"><h2>{clean(message.subject)||"No subject"}</h2><p className="inbox-muted">{clean(message.sender)} · {dates(message.received_at)}</p><span className={`inbox-looks k-${message.classification}`}>{LOOKS[message.classification]??clean(message.classification)}</span></div>
    <div className="inbox-full" tabIndex={0} aria-label="Full email text">{full??readable(message.snippet||"No excerpt is stored.")}{full==null&&<small>{fullError||"Loading the full email"}</small>}</div>
    {applied ? <div className="inbox-decided">
      <p><strong>{message.decision==="automatic"?"ACE recorded this email.":"You recorded this email."}</strong> {clean(message.reason)}</p>
      {linked&&<AppCard app={linked}/>}
      {change?<button className="btn" disabled={busy} onClick={()=>void action(()=>sendJson("POST",`/api/inbox/events/${change.id}/undo`,{}),"Undone. The email is back in your queue.")}>Undo this change</button>:<p className="inbox-muted">Undo it from Audit trail.</p>}
    </div> : <>
      <div className="inbox-target">
        <div className="inbox-target-head"><h3>{target?guessed?"ACE thinks this is about":"Application":"Which application?"}</h3>{target&&!choosing&&<button className="btn btn-sm" onClick={()=>setChoosing(true)}>Change</button>}</div>
        {target&&!choosing?<AppCard app={target}/>:<div className="inbox-picker">
          <input autoComplete="off" aria-label="Search your applications" placeholder="Search company, role or job ID" value={search} onChange={event=>setSearch(event.target.value)}/>
          {options.length?<div className="inbox-options">{options.map(a=><button key={a.key} className={a.key===targetKey?"on":""} onClick={()=>{setTargetKey(a.key);setChoosing(false);setSearch("");}}><AppCard app={a}/></button>)}</div>:<p className="inbox-muted">{query?"No application matches that search.":"ACE could not tell which application this is. Search for it above."}</p>}
        </div>}
        {message.reason&&<p className="inbox-muted">{pending?"Why it waits: ":""}{clean(message.reason)}.</p>}
      </div>
      <div className="inbox-outcomes" role="group" aria-label="What does this email say?">
        <h3>What does this email say?</h3>
        <div className="inbox-outcome-buttons">{OUTCOMES.map(outcome=><button key={outcome.kind} className={`btn${message.classification===outcome.kind?" primary":""}`} disabled={busy||!target} onClick={()=>decide(outcome)}>{outcome.label}</button>)}</div>
        <div className="inbox-outcome-buttons quiet"><button className={`btn${message.classification==="application_confirmation"?" primary":""}`} disabled={busy||message.decision==="receipt"} onClick={()=>file("receipt","Filed as a receipt. Nothing changed.")}>Just a receipt</button><button className="btn" disabled={busy||message.decision==="unrelated"} onClick={()=>file("unrelated","Marked not about your applications.")}>Not about my applications</button>{pending&&message.decision!=="deferred"&&<button className="btn" disabled={busy} onClick={()=>file("deferred","Saved for later.")}>Decide later</button>}</div>
        {!target&&<p className="inbox-muted">Choose the application first to record an outcome.</p>}
      </div>
    </>}
  </section>;
}
