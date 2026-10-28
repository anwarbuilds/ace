"use client";

import { useEffect, useMemo, useState } from "react";
import { CompanyLogo } from "@/components/CompanyLogo";
import { EmailFrame } from "@/components/inbox/EmailFrame";
import { clean, parseDate, STATUS_LABEL } from "@/lib/format";
import { getJson, RequestError, sendJson } from "@/lib/client";
import type { ApplicationStatus } from "@/lib/types";

export interface Understanding {decision_type?:string; classification_reason:string; classification_state:string; matching_state:string; workflow_state:string; update_policy:string; review_reason:string|null; evidence_source:string; evidence_excerpt:string}
export interface InboxMessage {understanding?:Understanding; id:number; received_at:string; sender:string; subject:string; snippet:string; classification:string; requisition_id:string|null; decision:string; candidate_keys:string[]; reason:string; selected_application_key:string|null}
export interface InboxApplication {key:string; company:string; title:string; requisition_id:string|null; applied_at:string|null; status:string}
export interface InboxEvent {company?:string|null; scope?:string; id:number; application_key:string; kind:string; before:string|null; after:string|null; actor:string; reason:string; recorded_at:string; undo_of_id:number|null; gmail_message_id:number|null}
/** The email as Gmail has it now, read live and never stored. */
export interface FullEmail {current_reading?:{classification:string; reason:string; variant:string; excerpt:string; complete:boolean}; sender:string; to:string; subject:string; received_at:string; text:string; document:string; format:string; blocked_images:number; message_id_header:string|null; thread_id:string|null}
type Action = (run:()=>Promise<unknown>, success:string)=>Promise<void>;

export const PENDING = ["review","exact_preview","deferred"];
import { KIND, STATE } from "@/lib/inboxLabels";
export { KIND, STATE } from "@/lib/inboxLabels";
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
const FILED: Record<string,string> = {unlinked:"Recognized historical outcome. No eligible application existed in ACE when this email arrived.",receipt:"Filed as an acknowledgement.",update:"Filed as a status update.",unrelated:"Marked not about your applications.",ignored:"ACE found no application outcome in it."};

const dates = (value:string|null)=>value ? new Date(value).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"}) : "Date not recorded";
const status = (value:string)=>STATUS_LABEL[value as ApplicationStatus]??clean(value);
// Email text keeps its lines; dashes and drawn rules are removed like any other text.
const readable = (text:string)=>text.split("\n").map(line=>/^[\s\-_=*~‐-―]+$/.test(line)?"":clean(line)).join("\n").replace(/\n{3,}/g,"\n\n").trim();
const loaded = new Map<number,FullEmail>();

/** "Wayfern Talent <no-reply@ashbyhq.example>" as its name and address. */
export function senderParts(value:string): {name:string; address:string} {
  const match = value.match(/^\s*"?([^"<]*?)"?\s*<([^>]+)>\s*$/);
  if (match) return {name:match[1].trim()||match[2], address:match[2]};
  return {name:value.trim(), address:value.includes("@")?value.trim():""};
}

// Letters and digits only, and initials: "General Motors" is generalmotors and gm.
const squash=(value:string)=>value.toLocaleLowerCase().replace(/[^a-z0-9]/g,"");
const initials=(value:string)=>value.split(/[^A-Za-z0-9]+/).filter(Boolean).map(word=>word[0]).join("").toLocaleLowerCase();
// Shared recruiting platforms and personal mail never name the employer.
const SHARED=/greenhouse|lever|workday|smartrecruiters|ashby|icims|jobvite|taleo|successfactors|workable|bamboohr|eightfold|avature|phenom|oraclecloud|brassring|rippling|teamtailor|recruitee|paylocity|ultipro|ukg|adp|applytojob|breezy|csod|hirevue|hackerrank|codesignal|linkedin|gmail|googlemail|outlook|hotmail|yahoo|icloud|proton/;

// First words too common to identify an employer on their own.
const GENERIC=new Set(["global","health","united","american","national","general","international","digital","capital","solutions","systems","technologies","technology","group","software","services","financial","first","north","south","western","eastern","energy","pacific","atlantic"]);
const tenantOf=(address:string)=>{const [local="",domain=""]=address.toLocaleLowerCase().split("@");return domain.endsWith("myworkday.com")?local.replace(/\d+$/,""):"";};

/** Applications the sender, subject or email text seems to name, offered when ACE could not tell. */
export function likelyApplications(message:InboxMessage, applications:InboxApplication[], text=""): InboxApplication[] {
  const {name,address}=senderParts(message.sender);
  const domain=address.toLocaleLowerCase().split("@")[1]??"";
  const hints=[name.includes("@")?"":squash(name)];
  // Workday sends as the employer's tenant: generalmotors@myworkday.com, or initials such as cir.
  const tenant=squash(tenantOf(address));
  if(tenant)hints.push(tenant);
  else if(!SHARED.test(domain))hints.push(...domain.split(".").slice(0,-1).map(squash));
  const named=squash(message.subject);
  const acronyms=new Set(message.subject.match(/\b[A-Z][A-Z0-9&]{1,4}\b/g)?.map(word=>squash(word))??[]);
  const words=new Set(`${message.subject} ${text||message.snippet}`.toLocaleLowerCase().split(/[^a-z0-9&]+/).filter(Boolean));
  return applications.filter(app=>{
    const company=squash(app.company);
    if(company.length<2)return false;
    const first=app.company.toLocaleLowerCase().split(/[^a-z0-9&]+/).filter(Boolean)[0]??"";
    return hints.some(hint=>hint.length>=3&&(hint===company||hint.startsWith(company)||(company.length>=5&&company.startsWith(hint))))
      ||(company.length>=4&&named.includes(company))||acronyms.has(initials(app.company))
      ||(tenant.length>=3&&tenant===initials(app.company))
      ||(first.length>=5&&!GENERIC.has(first)&&words.has(first));
  }).slice(0,8);
}

/** Guard an owner-selected application against an email naming another company.
 * This is a warning only; it never aliases employers or changes automatic matching.
 */
export function companyNamed(message:InboxMessage, company:string, text=""):boolean {
  const haystack=`${message.sender} ${message.subject} ${message.snippet} ${text}`;
  const name=squash(company.replace(/\b(?:incorporated|inc|llc|ltd|corp|corporation|company|plc)\.?$/i,"").trim());
  if(name.length>=4&&squash(haystack).includes(name))return true;
  const tokens=haystack.match(/\b[A-Za-z0-9]+\b/g)??[];
  const short=initials(company);
  return tokens.some(token=>squash(token)===name || (short.length>=2&&short.length<=6&&token===token.toUpperCase()&&squash(token)===short))
    || (short.length>=3&&squash(tenantOf(senderParts(message.sender).address))===short);
}

export function confirmCompany(message:InboxMessage,company:string,text:string,confirm:(warning:string)=>boolean):boolean {
  return companyNamed(message,company,text)||confirm(`This email does not name ${clean(company)}. Check the employer and role before recording this outcome. Record it for ${clean(company)} anyway?`);
}

/** A company and role for an application ACE does not have, read from the email for the owner to check. */
export function applicationFromEmail(message:InboxMessage, text=""): {company:string; title:string} {
  const body=(text||message.snippet).replace(/\s+/g," ");
  const {name,address}=senderParts(message.sender);
  let company=body.match(/\b(?:role|position|opportunity|opening|career|job|interest|employment)\s+(?:with|at)\s+([A-Z][\w&'-]*(?: (?:[A-Z][\w&'-]*|of|and|&))*)/)?.[1]??"";
  if(!company&&!name.includes("@")&&!SHARED.test(squash(name)))company=name;
  const tenant=tenantOf(address);
  if(!company&&tenant)company=tenant.length<=4?tenant.toUpperCase():tenant.charAt(0).toUpperCase()+tenant.slice(1);
  const role=body.match(/\bapplication for (?:the |our |a )?([A-Z][^,.;:!?]{2,80}?)(?:\s+(?:position|role|opening|job))?\s*(?:[,.;:!?]|\s+(?:at|with|in|and)\b)/)
    ??body.match(/\binterest in (?:the |our |a )?([A-Z][^,.;:!?]{2,80}?)(?:\s+(?:position|role|opening))?\s+(?:at|with)\b/)
    ??message.subject.match(/,\s*([^,]{3,80})$/)
    ??message.subject.match(/\b(?:for|in)\s+(?:the\s+)?([A-Z][^,]{2,80}?)(?:\s+(?:position|role))?(?:\s+at\s+.+)?$/);
  return {company:clean(company).slice(0,255), title:clean(role?.[1]??"").slice(0,500)};
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
  const decision=message?.decision;
  const [full,setFull]=useState<FullEmail|null>(()=>id==null?null:loaded.get(id)??null);
  const [fullError,setFullError]=useState("");
  const [plain,setPlain]=useState(false);
  const [messageEvents,setMessageEvents]=useState<InboxEvent[]>([]);
  useEffect(()=>{
    if(id==null||!["automatic","manual","company_rejection"].includes(decision??""))return;
    let live=true;
    getJson<{items:InboxEvent[]}>("/api/inbox/events",new URLSearchParams({message_id:String(id)}))
      .then(result=>{if(live)setMessageEvents(result.items);}).catch(()=>{});
    return ()=>{live=false;};
  },[id,decision]);
  const [targetKey,setTargetKey]=useState(()=>["ambiguous","identity_uncertain"].includes(message?.understanding?.matching_state??"")?"":message?.selected_application_key??message?.candidate_keys[0]??"");
  const [choosing,setChoosing]=useState(false);
  const [search,setSearch]=useState("");
  // An application ACE never had: added from this email, then recorded.
  const [draft,setDraft]=useState<{company:string;title:string;applied:string}|null>(null);
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
  const companyRecorded=message.decision==="company_rejection";
  const applied=message.decision==="automatic"||message.decision==="manual"||companyRecorded;
  const target=byKey.get(targetKey);
  const candidates=message.candidate_keys.map(key=>byKey.get(key)).filter((a):a is InboxApplication=>Boolean(a));
  const query=search.trim().toLocaleLowerCase();
  const guesses=!query&&!candidates.length?likelyApplications(message,applications,full?.text):[];
  // Search also finds "gm" and "generalmotors" for General Motors.
  const options=query?applications.filter(a=>`${a.company} ${a.title} ${a.requisition_id??""} ${squash(a.company)} ${initials(a.company)}`.toLocaleLowerCase().includes(query)).slice(0,30):candidates.length?candidates:guesses;
  const linked=message.selected_application_key?byKey.get(message.selected_application_key):undefined;
  const history=[...new Map([...events,...messageEvents].map(event=>[event.id,event])).values()];
  const change=history.find(e=>e.gmail_message_id===message.id&&e.kind!=="undo"&&(e.application_key===message.selected_application_key||(companyRecorded&&e.kind==="company_rejection"&&e.scope==="company"))&&["owner","verified_automation"].includes(e.actor)&&!history.some(other=>other.undo_of_id===e.id));
  const ready=draft?Boolean(draft.company.trim()&&draft.title.trim()):Boolean(target);
  const chosenCompany=draft?.company.trim()||target?.company||"";
  const mismatch=Boolean(chosenCompany)&&!companyNamed(message,chosenCompany,full?.text??"");
  const decide=(outcome:typeof OUTCOMES[number])=>{
    if(!ready||!confirmCompany(message,chosenCompany,full?.text??"",warning=>window.confirm(warning)))return;
    if(draft){if(ready)void action(()=>sendJson("POST","/api/inbox/applications",{message_id:message.id,company:draft.company,title:draft.title,status:outcome.status,kind:outcome.kind,applied_on:draft.applied||null}),`${outcome.done}: ${clean(draft.company)} added to your applications`);}
    else if(target)void action(()=>sendJson("POST","/api/inbox/review",{message_id:message.id,application_key:target.key,status:outcome.status,expected_status:target.status,confirmed:true,kind:outcome.kind}),`${outcome.done}: ${clean(target.company)}`);
  };
  const edit=(field:"company"|"title"|"applied",value:string)=>setDraft(old=>old&&{...old,[field]:value});
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
        <dt>From</dt><dd><strong>{clean(sender.name)}</strong>{sender.address&&sender.address!==sender.name&&<span className="inbox-address"> &lt;{sender.address}&gt;</span>}</dd>
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
    <div className="inbox-filed" aria-label="ACE understanding">
      <strong>ACE&rsquo;s classification: {KIND[message.classification]??clean(message.classification)}</strong>
      {message.understanding&&<>
        <p>{clean(message.understanding.classification_reason)}</p>
        {message.understanding.decision_type&&<p>{clean(message.understanding.decision_type)}</p>}
        <p>Application linkage: {clean(message.understanding.matching_state)}. {message.understanding.update_policy==="company_recorded"?"A company rejection was recorded. No role choice is needed.":message.understanding.update_policy==="recorded"?"The outcome was recorded with an audit event.":message.understanding.update_policy==="no_status_change"?"No application status changed.":"No status change is authorized until the specific review is resolved."}</p>
        {pending&&message.understanding.review_reason&&<p>Decision needed: {clean(message.understanding.review_reason)}</p>}
      </>}
      {full?.current_reading&&<>
        <p>Current email reading: {KIND[full.current_reading.classification]??clean(full.current_reading.classification)}{full.current_reading.variant?` (${clean(full.current_reading.variant.replaceAll("_"," "))})`:""}. {clean(full.current_reading.reason)}</p>
        {full.current_reading.excerpt&&<blockquote>{readable(full.current_reading.excerpt)}</blockquote>}
        {!full.current_reading.complete&&<p>Only part of the body is available. Its missing content may change this interpretation.</p>}
        {full.current_reading.classification!==message.classification&&<p>This current reading has not changed the saved decision or application history.</p>}
      </>}
    </div>
    {applied ? <div className="inbox-decided">
      <h3>{companyRecorded?"ACE recorded the company rejection.":message.decision==="automatic"?"ACE recorded this email.":"You recorded this email."}</h3>
      <p className="inbox-muted">{companyRecorded?`${clean(change?.company??candidates[0]?.company??"The employer")}: rejection received. No role choice is needed.`:clean(message.reason)+"."}</p>
      {linked&&<AppCard app={linked}/>}
      {change?<button className="btn" disabled={busy} onClick={()=>void action(()=>sendJson("POST",`/api/inbox/events/${change.id}/undo`,{}),"Undone. The email is back in your queue.")}>Undo this change</button>:<p className="inbox-muted">Undo it from Audit trail.</p>}
    </div> : <div className="inbox-decide">
      {!pending&&FILED[message.decision]&&<p className="inbox-filed"><strong>{FILED[message.decision]}</strong> {message.decision==="unlinked" ? "No application outcome was recorded. Linking is optional; the email remains searchable. " + clean(message.reason) : "Nothing changed. If that is wrong, choose what it is below."}</p>}
      <div className="inbox-target">
        <div className="inbox-target-head"><h3>{draft?"Add it to your applications":target?guessed?"ACE thinks this is about":"Application":"Which application?"}</h3>{target&&!choosing&&!draft&&<button className="btn btn-sm" onClick={()=>setChoosing(true)}>Change</button>}</div>
        {draft?<div className="inbox-add">
          <p className="inbox-muted">Not in ACE yet. It is added to your applications, then what you choose below is recorded on it. Check what ACE read from the email.</p>
          <label>Company<input autoComplete="off" value={draft.company} onChange={event=>edit("company",event.target.value)}/></label>
          <label>Role<input autoComplete="off" value={draft.title} onChange={event=>edit("title",event.target.value)}/></label>
          <label>Applied on, if you know it<input type="date" value={draft.applied} onChange={event=>edit("applied",event.target.value)}/></label>
          <button className="btn btn-sm" onClick={()=>setDraft(null)}>Back to my applications</button>
        </div>:target&&!choosing?<AppCard app={target}/>:<div className="inbox-picker">
          <input autoComplete="off" aria-label="Search your applications" placeholder="Search company, role or job ID" value={search} onChange={event=>setSearch(event.target.value)}/>
          {guesses.length>0&&<p className="inbox-muted">Possible matches from the sender and subject. Click the right one, or search above.</p>}
          {options.length?<div className="inbox-options">{options.map(a=><button key={a.key} className={a.key===targetKey?"on":""} onClick={()=>{setTargetKey(a.key);setChoosing(false);setSearch("");}}><AppCard app={a}/></button>)}</div>:<p className="inbox-muted">{query?"No application matches that search.":"ACE could not tell which application this is. Search for it above."}</p>}
          <button className="btn btn-sm inbox-add-open" onClick={()=>{setDraft({...applicationFromEmail(message,full?.text),applied:""});setSearch("");}}>Not in ACE yet? Add it from this email</button>
        </div>}
      </div>
      <div className="inbox-outcomes" role="group" aria-label="What is this email?">
        <h3>What is this email?</h3>
        {pending&&message.reason&&<p className="inbox-muted">Why it waits: {clean(message.reason)}.</p>}
        {mismatch&&<p className="inbox-error" role="status">This email does not name {clean(chosenCompany)}. Check the employer and role. Recording an outcome will ask you to confirm this choice.</p>}
        <p className="inbox-group">Changes the application</p>
        <div className="inbox-choices">{OUTCOMES.map(outcome=><button key={outcome.kind} className={`inbox-choice${suggest===outcome.kind?" suggested":""}`} disabled={busy||!ready} onClick={()=>decide(outcome)}><strong>{outcome.label}</strong><span>{outcome.hint}</span>{suggest===outcome.kind&&<em>ACE&rsquo;s reading</em>}</button>)}</div>
        {!ready&&<p className="inbox-muted">{draft?"Give the company and the role to record an outcome.":"Choose the application above, or add it from this email, to record an outcome."}</p>}
        <p className="inbox-group">Nothing to change</p>
        <div className="inbox-choices quiet">{FILINGS.filter(filing=>filing.action!=="deferred"||(pending&&message.decision!=="deferred")).map(filing=><button key={filing.action} className={`inbox-choice${suggest===filing.action?" suggested":""}`} disabled={busy||message.decision===filing.action} onClick={()=>file(filing)}><strong>{filing.label}</strong><span>{filing.hint}</span>{suggest===filing.action&&<em>ACE&rsquo;s reading</em>}</button>)}</div>
      </div>
    </div>}
  </section>;
}
