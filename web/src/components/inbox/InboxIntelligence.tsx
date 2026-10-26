"use client";

// OAuth must leave the app and return through Google's full browser redirect.
/* eslint-disable @next/next/no-location-assign-relative-destination */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { getJson, RequestError, sendJson } from "@/lib/client";
import { clean } from "@/lib/format";
import { InboxReviewPanel, LOOKS, PENDING, type InboxEvent as Event, type InboxMessage as Message, type InboxApplication as Application } from "./InboxReviewPanel";

type Tab = "queue" | "register" | "audit" | "rules";
interface Connection {available: boolean; connected: boolean; state: string; email: string | null; last_synced_at: string | null; last_error: string | null; auto_outcomes_enabled: boolean; automation_available: boolean; auto_rejections: boolean}
interface Counts {stored: number; needs_review: number; automatic: number; reviewed: number; receipts: number; stale: number}
const VIEWS: [string, string][] = [["pending","Waiting for you"],["automatic","Recorded automatically"],["manual","Recorded by you"],["receipt","Receipts"],["deferred","Decide later"],["unrelated","Not about applications"],["ignored","No outcome found"],["review","Needs an application match"],["exact_preview","Matched, waiting for confirmation"],["ambiguous","Several possible applications"],["all","All imported email"]];
const DECISION: Record<string, string> = {review: "Waiting", exact_preview: "Waiting", deferred: "Later", automatic: "Recorded", manual: "Recorded by you", receipt: "Receipt", unrelated: "Not about applications", ignored: "No outcome"};

const date = (value: string | null) => value ? new Date(value).toLocaleString("en-US") : "Not recorded";

export function InboxIntelligence() {
  const { refreshMarks, toast } = useApp();
  const router = useRouter();
  const params = useSearchParams();
  const decisionFilter = params.get("decision") ?? "pending";
  const offset = Math.max(0, Number(params.get("offset")) || 0);
  const [summary, setSummary] = useState<{total:number;has_more:boolean;counts:Counts}>({total:0,has_more:false,counts:{stored:0,needs_review:0,automatic:0,reviewed:0,receipts:0,stale:0}});
  const [tab, setTab] = useState<Tab>("queue");
  const [connection, setConnection] = useState<Connection | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [backfillDays, setBackfillDays] = useState(() => [7,30,90,365].includes(Number(params.get("days"))) ? Number(params.get("days")) : 30);
  const [previewPages,setPreviewPages] = useState(0);
  const [nextPage, setNextPage] = useState<string | null>(null);
  const loadSequence=useRef(0);

  const load = useCallback(async () => {
    const sequence=++loadSequence.current;
    const [c, m, a, e] = await Promise.all([
      getJson<Connection>("/api/inbox/connection"),
      getJson<{items:Message[];total:number;has_more:boolean;counts:Counts}>("/api/inbox/messages", new URLSearchParams({...decisionFilter === "all" ? {} : {decision:decisionFilter},offset:String(offset),limit:"50"})),
      getJson<{items: Application[]}>("/api/inbox/applications"),
      getJson<{items: Event[]}>("/api/inbox/events"),
    ]);
    if(sequence!==loadSequence.current)return;
    setConnection(c); setMessages(m.items); setApplications(a.items); setEvents(e.items); setSummary(m);
    setSelected(old => m.items.some(item=>item.id===old) ? old : m.items[0]?.id ?? null);
  }, [decisionFilter,offset]);

  useEffect(() => { void Promise.resolve().then(load).catch(() => setError("Inbox Intelligence could not be loaded.")); }, [load]);

  async function action(run: () => Promise<unknown>, success: string | (() => string)) {
    setBusy(true); setError("");
    try { await run(); await Promise.all([load(), refreshMarks()]); toast(typeof success === "function" ? success() : success); }
    catch (cause) { setError(cause instanceof RequestError && cause.status===500 ? "Email import could not finish. Reload to see saved progress, then retry the historical preview." : cause instanceof Error ? clean(cause.message) : "The operation failed. Reload and try again."); await load().catch(()=>{}); }
    finally { setBusy(false); }
  }

  const visibleMessages = messages;
  const active = visibleMessages.find(m=>m.id===selected) ?? visibleMessages[0] ?? null;
  const reviewCount = summary.counts.needs_review;
  const changeView = (decision:string, nextOffset=0) => {
    const next=new URLSearchParams(params);
    next.set("decision",decision);
    if(nextOffset)next.set("offset",String(nextOffset));else next.delete("offset");
    setSelected(null);
    router.replace(`/app/applications/inbox?${next}`,{scroll:false});
    setTab("queue");
  };
  // Re-decide emails read under older rules, a page at a time, until none remain.
  const recheck = () => { let checked = 0, recorded = 0; return action(async () => {
    for (let round = 0; round < 40; round++) {
      const result = await sendJson<{checked:number;remaining:number;counts:Record<string,number>}>("POST", "/api/inbox/recheck", {limit: 25});
      checked += result.checked; recorded += result.counts.automatic ?? 0;
      if (!result.remaining || !result.checked) break;
    }
  }, () => `${checked} waiting ${checked === 1 ? "email" : "emails"} checked again. ${recorded} recorded automatically.`); };
  return <div className="pg inbox-page">
    <div className="page-hero"><div><div className="eyebrow">Application intelligence</div><h1 className="h1">Inbox Intelligence</h1><p className="subtitle">Clear rejections are recorded for you. Everything else waits for one click, with the whole email beside it. Every change has an Undo.</p></div><div className="btns"><button className="btn" onClick={() => setTab("rules")}>How ACE decides</button>{connection?.connected && <button className="btn primary" disabled={busy || connection.state !== "ready"} onClick={() => action(() => sendJson("POST", "/api/inbox/sync", {}), "Gmail catch-up finished")}>Run catch-up</button>}</div></div>
    <section className="inbox-hero"><div><div className="eyebrow">How ACE decides</div><h2>A clear rejection counts on its own.</h2><p>When the wording is explicit, Gmail verifies the sender and exactly one application fits, ACE marks it rejected. Two possible applications, a personal mailbox or a newer status means it waits for you instead.</p></div><strong>Automatic rejections: {connection ? connection.auto_rejections ? "ON" : "OFF" : "Loading"}</strong></section>
    <div className="intelligence-kpis inbox-kpis"><button className="kpi inbox-kpi-button" onClick={()=>changeView("all")}><span className="kpi-l">Emails imported</span><span className="kpi-n">{summary.counts.stored}</span><span className="kpi-f">Recruiting and other email read</span></button><button className="kpi inbox-kpi-button" onClick={()=>changeView("automatic")}><span className="kpi-l">Recorded automatically</span><span className="kpi-n">{summary.counts.automatic}</span><span className="kpi-f">Clear outcomes, each with Undo</span></button><button className="kpi inbox-kpi-button" onClick={()=>changeView("pending")}><span className="kpi-l">Waiting for you</span><span className="kpi-n">{reviewCount}</span><span className="kpi-f">One click each</span></button><button className="kpi inbox-kpi-button" onClick={()=>changeView("receipt")}><span className="kpi-l">Receipts filed</span><span className="kpi-n">{summary.counts.receipts}</span><span className="kpi-f">Application received, nothing to do</span></button></div>
    {summary.counts.stale>0&&connection?.connected&&<div className="inbox-recheck"><p><strong>{summary.counts.stale} waiting {summary.counts.stale===1?"email was":"emails were"} read under the earlier, stricter rules.</strong> Checking again reads each one from Gmail and records the clear rejections.</p><button className="btn primary" disabled={busy} onClick={()=>void recheck()}>{busy?"Checking":"Check waiting emails again"}</button></div>}
    {error && <div role="alert" className="inbox-error">{error}</div>}
    {!connection ? <p>Loading connection status</p> : <div className="inbox-connection"><div><strong>Gmail connection: {connection.connected ? clean(connection.state) : connection.available ? "Not connected" : "Setup required"}</strong><p>{connection.connected ? `Account ${connection.email}. Last sync: ${date(connection.last_synced_at)}.` : connection.available ? "Connect a Gmail account to preview historical recruiting email." : "Gmail OAuth and token encryption must be configured by the owner before connecting."}{connection.last_error ? ` ${clean(connection.last_error)}` : ""}</p></div><div className="btns">{connection.available && !connection.connected && <button className="btn primary" onClick={() => window.location.assign("/api/inbox/google/start")}>Connect Gmail read-only</button>}{connection.connected && <><button className="btn" disabled={busy} onClick={() => action(() => sendJson("PATCH", "/api/inbox/connection", {paused: connection.state === "ready"}), connection.state === "ready" ? "Sync paused" : "Sync ready")}>{connection.state === "ready" ? "Pause sync" : "Resume sync"}</button><button className="btn" disabled={busy} onClick={() => { if (window.confirm("Disconnect Gmail and revoke the saved grant? Stored audit history will remain.")) action(() => sendJson("DELETE", "/api/inbox/connection"), "Gmail disconnected"); }}>Disconnect</button></>}</div></div>}
    {connection?.connected && <div className="inbox-backfill"><label>Import email from the last<select value={backfillDays} disabled={busy} onChange={event=>{const days=Number(event.target.value);setBackfillDays(days);setNextPage(null);setPreviewPages(0);const next=new URLSearchParams(params);next.set("days",String(days));router.replace(`/app/applications/inbox?${next}`,{scroll:false});}}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option><option value={365}>1 year</option></select></label><button className="btn" disabled={busy} onClick={()=>action(async()=>{const result=await sendJson<{next_page_token:string|null}>("POST","/api/inbox/backfill",{days:backfillDays,page_token:nextPage});setNextPage(result.next_page_token);setPreviewPages(value=>value+1);},"Import page saved.")}>{busy?"Working":nextPage?"Import next page":"Import past email"}</button><span>{previewPages?`${previewPages} import ${previewPages===1?"page":"pages"} saved for ${backfillDays} days. ${nextPage?"More pages remain.":"Selected window complete."}`:"Changing the window does not import by itself. Select Import past email."} Clear rejections in past email are recorded; interviews, assessments and offers wait for you.</span></div>}
    <nav className="intelligence-tabs" aria-label="Inbox Intelligence views">{([["queue","Review queue"],["register","Application register"],["audit","Audit trail"],["rules","Matching policy"]] as const).map(([id,label])=><button key={id} className={tab===id?"on":""} onClick={()=>setTab(id)}>{label}{id==="queue"?` ${reviewCount}`:""}</button>)}</nav>
    {tab === "queue" && <>
      {["review","exact_preview","ambiguous"].includes(decisionFilter)&&<p className="inbox-muted">Analytics evidence filter: {VIEWS.find(([key])=>key===decisionFilter)?.[1]}. <Link href="/app/applications/inbox">Show everything waiting for you</Link></p>}
      <div className="inbox-queue-tools"><label>Email view<select value={decisionFilter} disabled={busy} onChange={event=>changeView(event.target.value)}>{VIEWS.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><p>Read the email on the right and click what it says. ACE has already picked the likeliest application.</p><div className="btns"><button className="btn" disabled={busy||offset===0} onClick={()=>changeView(decisionFilter,Math.max(0,offset-50))}>Previous messages</button><span>{summary.total?`${offset+1} to ${offset+messages.length} of ${summary.total} messages`:"No messages in this view"}</span><button className="btn" disabled={busy||!summary.has_more} onClick={()=>changeView(decisionFilter,offset+50)}>Next messages</button></div></div>
      <div className="inbox-columns"><section className="panel inbox-list"><h2>{VIEWS.find(([key])=>key===decisionFilter)?.[1]??"Imported email"}</h2><p>Newest first. Email with no recruiting outcome stays out of Waiting for you.</p>{visibleMessages.length?visibleMessages.map(m=><button key={m.id} className={`inbox-mail${active?.id===m.id?" on":""}`} aria-pressed={active?.id===m.id} onClick={()=>setSelected(m.id)}><strong>{clean(m.subject)||"No subject"}</strong><span>{clean(m.sender)} · {date(m.received_at)}</span><small>{LOOKS[m.classification]??clean(m.classification)}{PENDING.includes(m.decision)?"":` · ${DECISION[m.decision]??clean(m.decision)}`}</small></button>):<p>{decisionFilter==="pending"?"Nothing is waiting for you. New recruiting email appears here after a catch-up.":"No email in this view."}</p>}</section><InboxReviewPanel key={active?.id??"empty"} message={active} applications={applications} events={events} busy={busy} action={action}/></div>
    </>}
    {tab === "register" && <section className="panel"><h2>Application register</h2><p>Each key identifies one submitted record. Rejected applications stay in the total.</p><div className="inbox-table"><div className="inbox-row head"><span>Application</span><span>Role</span><span>Submitted</span><span>Status</span></div>{applications.map((a)=><div className="inbox-row" key={a.key}><span><strong>{clean(a.company)}</strong><small>{a.key}</small></span><span>{clean(a.title)}<small>{a.requisition_id ?? "No requisition recorded"}</small></span><span>{date(a.applied_at)}</span><span>{clean(a.status)}</span></div>)}</div>{!applications.length&&<p>No applications are recorded.</p>}</section>}
    {tab === "audit" && <section className="panel"><h2>Reconciliation audit trail</h2><p>Changes and corrections remain in chronological history.</p>{events.map((e)=><div className="inbox-event" key={e.id}><div><strong>{e.application_key}: {clean(e.kind)}</strong><p>{clean(e.before??"No status")} to {clean(e.after??"No status")}. {clean(e.reason)}</p><small>{date(e.recorded_at)} · {e.actor==="verified_automation"?"ACE, automatically":e.actor==="owner"?"You":clean(e.actor)}{e.gmail_message_id?` · email evidence ${e.gmail_message_id}`:""}</small></div>{e.kind!=="undo"&&(e.application_key.startsWith("job:")||e.application_key.startsWith("external:"))&&!events.some((other)=>other.undo_of_id===e.id)&&<button className="btn" disabled={busy} onClick={()=>{if(window.confirm(`Undo event ${e.id} for ${e.application_key}?`)) action(()=>sendJson("POST",`/api/inbox/events/${e.id}/undo`,{}),"Status restored with a correction event")}}>Undo</button>}</div>)}{!events.length&&<p>No application events have been recorded since the evidence ledger was added.</p>}</section>}
    {tab === "rules" && <div className="inbox-columns"><section className="panel"><h2>How ACE decides</h2><p>A rejection is recorded automatically when the wording is explicit (for example &ldquo;we regret to inform you&rdquo; or &ldquo;we have decided to move forward with other candidates&rdquo;), Gmail verifies the sender, the sender is not a personal mailbox, and exactly one application fits: its job ID is in the email, its exact title at that company is, or it is your only application there for a role like it.</p><p>It waits for you when two applications could fit, when the email predates the application, or when the application already has a newer or final status. You then see the whole email and ACE&rsquo;s likeliest application, and one click records it.</p><p>Receipts such as &ldquo;thank you for applying&rdquo; are filed without changing anything. Interviews, assessments and offers are recorded automatically only after you turn on verified outcomes below; they also need the exact job ID from the employer&rsquo;s own domain. Every change can be undone.</p></section><section className="panel"><h2>Read-only access</h2><p>The connection requests Gmail read-only access. ACE cannot send, edit or delete mailbox messages through this integration. Only minimal extracted evidence is stored. Disconnect revokes the saved token locally.</p><p>Automatic rejections: {connection?.auto_rejections ? "On" : "Off"}. Automatic interviews, assessments and offers: {connection?.auto_outcomes_enabled ? "On" : "Off"}.</p>{connection?.connected && <button className="btn" disabled={busy || (!connection.automation_available && !connection.auto_outcomes_enabled)} onClick={()=>{ const enabled=!connection.auto_outcomes_enabled; if (!enabled || window.confirm("Enable verified-only automatic outcomes after the review pilot? Ambiguous email will still leave every application unchanged.")) action(()=>sendJson("PATCH","/api/inbox/automation",{enabled,confirmed:enabled}),enabled?"Verified outcome updates enabled":"Automatic outcomes disabled"); }}>{connection.auto_outcomes_enabled?"Disable automatic outcomes":connection.automation_available?"Enable verified-only outcomes":"Automatic outcomes locked"}</button>}<p><button className="btn" disabled={busy || !connection} onClick={()=>{if(window.confirm("Remove stored email snippets while keeping decision history?")) action(()=>sendJson("DELETE","/api/inbox/snippets"),"Stored email snippets removed")}}>Purge stored snippets</button></p><p><Link href="/app/applications">Return to Applications</Link></p></section></div>}
  </div>;
}
