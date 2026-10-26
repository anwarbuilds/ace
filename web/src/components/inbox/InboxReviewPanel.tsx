"use client";

import { CompanyIdentity } from "@/components/CompanyIdentity";
import { useState } from "react";
import { clean, STATUS_LABEL } from "@/lib/format";
import { sendJson } from "@/lib/client";
import type { ApplicationStatus } from "@/lib/types";

export interface InboxMessage {id:number; received_at:string; sender:string; subject:string; snippet:string; classification:string; requisition_id:string|null; decision:string; candidate_keys:string[]; reason:string; selected_application_key:string|null}
export interface InboxApplication {key:string; company:string; title:string; requisition_id:string|null; applied_at:string|null; status:string}
type Action = (run:()=>Promise<unknown>, success:string)=>Promise<void>;
const stages = ["applied","screening","interviewing","offer","accepted","rejected","withdrawn","ghosted"] as ApplicationStatus[];
const dates = (value:string|null)=>value ? new Date(value).toLocaleDateString("en-US") : "Date not recorded";

export function InboxReviewPanel({message,applications,busy,action,showPending}: {message:InboxMessage|null; applications:InboxApplication[]; busy:boolean; action:Action; showPending:()=>void}) {
  const [search,setSearch]=useState("");
  const [targetKey,setTargetKey]=useState("");
  const [stage,setStage]=useState("");
  const [confirmed,setConfirmed]=useState(false);
  if(!message)return <section className="panel inbox-inspector"><h2>Review an email</h2><p>Select a message on the left to see its evidence and review controls.</p></section>;
  const reviewable=["review","exact_preview","deferred"].includes(message.decision);
  const candidates=applications.filter(a=>message.candidate_keys.includes(a.key));
  const matching=applications.filter(a=>`${a.company} ${a.title} ${a.requisition_id??""}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const target=applications.find(a=>a.key===targetKey);
  return <section className="panel inbox-inspector">
    <h2>{reviewable?"Review this email":"Email details"}</h2>
    <h3>{clean(message.subject)||"No subject"}</h3>
    <p className="inbox-muted">{clean(message.sender)} · {dates(message.received_at)}</p>
    <blockquote>{clean(message.snippet)||"No excerpt is stored. Read the original email in Gmail before deciding."}</blockquote>
    <p><strong>Why it needs attention:</strong> {clean(message.reason)}</p>
    {reviewable ? <div className="inbox-manual" id="inbox-review-form">
      <h3>1. Choose the exact application</h3>
      <p>Match the company, role, submission date and requisition. A company name alone is not enough.</p>
      {candidates.length>0&&<p>{candidates.length} possible applications: {candidates.slice(0,3).map(a=>`${clean(a.company)}, ${clean(a.title)}${a.requisition_id?` (${clean(a.requisition_id)})`:""}`).join("; ")}{candidates.length>3?". Search below to narrow them down.":"."}</p>}
      <label>Search your applications<input autoComplete="off" placeholder="Company, role or requisition" value={search} onChange={event=>setSearch(event.target.value)}/></label>
      <label>Application<select value={targetKey} onChange={event=>{setTargetKey(event.target.value);setConfirmed(false);}}>
        <option value="">Choose the application this email refers to</option>
        {target&&!matching.some(a=>a.key===target.key)&&<option value={target.key}>{clean(target.company)} · {clean(target.title)} · {dates(target.applied_at)}</option>}
        {matching.map(a=><option key={a.key} value={a.key}>{clean(a.company)} · {clean(a.title)} · {dates(a.applied_at)}{a.requisition_id?` · ${clean(a.requisition_id)}`:""}</option>)}
      </select></label>
      {!matching.length&&<p>No applications match that search. Clear the search or defer this message.</p>}
      {target&&<p>Selected: <strong><CompanyIdentity name={target.company} /> · {clean(target.title)}</strong>. Submitted {dates(target.applied_at)}. Current status: {STATUS_LABEL[target.status as ApplicationStatus]??clean(target.status)}.</p>}
      <h3>2. Choose what the email confirms</h3>
      <label>Outcome<select value={stage} onChange={event=>{setStage(event.target.value);setConfirmed(false);}}><option value="">Choose an outcome after reading the email</option>{stages.map(s=><option value={s} key={s}>{s==="applied"?"Application received or submitted":s==="screening"?"Screening, assessment or recruiter reply":STATUS_LABEL[s]}</option>)}</select></label>
      <p>A receipt can stay Applied. Choose Rejected only for an explicit rejection of this exact application. No reply is not rejection.</p>
      <label className="inbox-confirm"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/> I read the email and verified this exact application and outcome.</label>
      <button className="btn primary" disabled={busy||!target||!stage||!confirmed} onClick={()=>{
        setConfirmed(false);
        void action(()=>sendJson("POST","/api/inbox/review",{message_id:message.id,application_key:targetKey,status:stage,expected_status:target?.status,confirmed:true}),"Outcome confirmed. Analytics updated with an audit event.");
      }}>Confirm application outcome</button>
      <div className="btns"><button className="btn" disabled={busy} onClick={()=>action(()=>sendJson("PATCH",`/api/inbox/messages/${message.id}/decision`,{action:"deferred"}),"Deferred. No application status changed.")}>Defer for later</button><button className="btn" disabled={busy} onClick={()=>action(()=>sendJson("PATCH",`/api/inbox/messages/${message.id}/decision`,{action:"unrelated"}),"Marked unrelated. No application status changed.")}>Not about an application</button></div>
      <p>You can undo a confirmed change in Audit trail.</p>
    </div> : <div className="inbox-manual"><p>This message is {clean(message.decision)}. It has no pending outcome to confirm.</p><button className="btn" onClick={showPending}>Show messages awaiting review</button></div>}
  </section>;
}
