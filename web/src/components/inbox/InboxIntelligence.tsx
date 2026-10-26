"use client";

// OAuth must leave the app and return through Google's full browser redirect.
/* eslint-disable @next/next/no-location-assign-relative-destination */

import { CompanyIdentity } from "@/components/CompanyIdentity";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { getJson, RequestError, sendJson } from "@/lib/client";
import { clean } from "@/lib/format";
import { InboxReviewPanel, type InboxMessage as Message, type InboxApplication as Application } from "./InboxReviewPanel";

type Tab = "queue" | "register" | "audit" | "rules";
interface Connection {available: boolean; connected: boolean; state: string; email: string | null; last_synced_at: string | null; last_error: string | null; auto_outcomes_enabled: boolean; automation_available: boolean}
interface Event {id: number; application_key: string; kind: string; before: string | null; after: string | null; actor: string; reason: string; recorded_at: string; undo_of_id: number | null; gmail_message_id: number | null}

const date = (value: string | null) => value ? new Date(value).toLocaleString("en-US") : "Not recorded";

export function InboxIntelligence() {
  const { refreshMarks, toast } = useApp();
  const router = useRouter();
  const params = useSearchParams();
  const decisionFilter = params.get("decision") ?? "pending";
  const offset = Math.max(0, Number(params.get("offset")) || 0);
  const [summary, setSummary] = useState({total:0,has_more:false,counts:{stored:0,needs_review:0,automatic:0,reviewed:0}});
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
      getJson<{items:Message[];total:number;has_more:boolean;counts:{stored:number;needs_review:number;automatic:number;reviewed:number}}>("/api/inbox/messages", new URLSearchParams({...decisionFilter === "all" ? {} : {decision:decisionFilter},offset:String(offset),limit:"50"})),
      getJson<{items: Application[]}>("/api/inbox/applications"),
      getJson<{items: Event[]}>("/api/inbox/events"),
    ]);
    if(sequence!==loadSequence.current)return;
    setConnection(c); setMessages(m.items); setApplications(a.items); setEvents(e.items); setSummary(m);
    setSelected(old => m.items.some(item=>item.id===old) ? old : m.items[0]?.id ?? null);
  }, [decisionFilter,offset]);

  useEffect(() => { void Promise.resolve().then(load).catch(() => setError("Inbox Intelligence could not be loaded.")); }, [load]);

  async function action(run: () => Promise<unknown>, success: string) {
    setBusy(true); setError("");
    try { await run(); await Promise.all([load(), refreshMarks()]); toast(success); }
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
  const pending = applications.filter((a) => !["accepted", "rejected", "withdrawn"].includes(a.status)).length;
  return <div className="pg inbox-page">
    <div className="page-hero"><div><div className="eyebrow">Application intelligence / mail reconciliation</div><h1 className="h1">Never guess the application.</h1><p className="subtitle">Capture recruiting evidence without closing the wrong opportunity. Every change has an audit trail and an Undo action.</p></div><div className="btns"><button className="btn" onClick={() => setTab("rules")}>View safety rules</button>{connection?.connected && <button className="btn primary" disabled={busy || connection.state !== "ready"} onClick={() => action(() => sendJson("POST", "/api/inbox/sync", {}), "Gmail catch-up finished")}>Run catch-up</button>}</div></div>
    <section className="inbox-hero"><div><div className="eyebrow">Protected by design</div><h2>A rejection email is not a matching application.</h2><p>Similar job titles, shared recruiting senders and uncertain requisitions never trigger an automatic rejection. Only unique, independently verified evidence can qualify after owner opt-in.</p></div><strong>Pending status protection: ON</strong></section>
    <div className="intelligence-kpis"><div className="kpi"><div className="kpi-l">Emails imported</div><div className="kpi-n">{summary.counts.stored}</div><div className="kpi-f">All stored email evidence</div></div><div className="kpi"><div className="kpi-l">Automatic updates</div><div className="kpi-n">{summary.counts.automatic}</div><div className="kpi-f">Verified outcomes only</div></div><button className="kpi inbox-kpi-button" onClick={()=>changeView("pending")}><span className="kpi-l">Needs your review</span><span className="kpi-n">{reviewCount}</span><span className="kpi-f">Messages, not days. Select to review.</span></button><div className="kpi"><div className="kpi-l">Pending protected</div><div className="kpi-n">{pending}</div><div className="kpi-f">Current application records</div></div></div>
    {error && <div role="alert" className="inbox-error">{error}</div>}
    {!connection ? <p>Loading connection status</p> : <div className="inbox-connection"><div><strong>Gmail connection: {connection.connected ? clean(connection.state) : connection.available ? "Not connected" : "Setup required"}</strong><p>{connection.connected ? `Account ${connection.email}. Last sync: ${date(connection.last_synced_at)}.` : connection.available ? "Connect a Gmail account to preview historical recruiting email." : "Gmail OAuth and token encryption must be configured by the owner before connecting."}{connection.last_error ? ` ${clean(connection.last_error)}` : ""}</p></div><div className="btns">{connection.available && !connection.connected && <button className="btn primary" onClick={() => window.location.assign("/api/inbox/google/start")}>Connect Gmail read-only</button>}{connection.connected && <><button className="btn" disabled={busy} onClick={() => action(() => sendJson("PATCH", "/api/inbox/connection", {paused: connection.state === "ready"}), connection.state === "ready" ? "Sync paused" : "Sync ready")}>{connection.state === "ready" ? "Pause sync" : "Resume sync"}</button><button className="btn" disabled={busy} onClick={() => { if (window.confirm("Disconnect Gmail and revoke the saved grant? Stored audit history will remain.")) action(() => sendJson("DELETE", "/api/inbox/connection"), "Gmail disconnected"); }}>Disconnect</button></>}</div></div>}
    {connection?.connected && <div className="inbox-backfill"><label>Import email from the last<select value={backfillDays} disabled={busy} onChange={event=>{const days=Number(event.target.value);setBackfillDays(days);setNextPage(null);setPreviewPages(0);const next=new URLSearchParams(params);next.set("days",String(days));router.replace(`/app/applications/inbox?${next}`,{scroll:false});}}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option><option value={365}>1 year</option></select></label><button className="btn" disabled={busy} onClick={()=>action(async()=>{const result=await sendJson<{next_page_token:string|null}>("POST","/api/inbox/backfill",{days:backfillDays,page_token:nextPage});setNextPage(result.next_page_token);setPreviewPages(value=>value+1);},"Preview page saved. Review messages to confirm outcomes.")}>{busy?"Working…":nextPage?"Preview next page":"Preview historical email"}</button><span>{previewPages?`${previewPages} preview pages saved for ${backfillDays} days. ${nextPage?"More pages remain.":"Selected window preview complete."}`:"Changing the window does not import automatically. Select Preview historical email."} Preview never changes application statuses. Needs your review counts messages across stored evidence.</span></div>}
    <nav className="intelligence-tabs" aria-label="Inbox Intelligence views">{([["queue","Review queue"],["register","Application register"],["audit","Audit trail"],["rules","Matching policy"]] as const).map(([id,label])=><button key={id} className={tab===id?"on":""} onClick={()=>setTab(id)}>{label}{id==="queue"?` ${reviewCount}`:""}</button>)}</nav>
    {tab === "queue" && <>
      {["review","exact_preview","ambiguous"].includes(decisionFilter)&&<p className="inbox-muted">Analytics evidence filter: {clean(decisionFilter.replaceAll("_"," "))}. <Link href="/app/applications/inbox">Show messages awaiting review</Link></p>}
      <div className="inbox-queue-tools"><label>Email view<select value={decisionFilter} disabled={busy} onChange={event=>changeView(event.target.value)}><option value="pending">Awaiting review</option><option value="review">Needs an application match</option><option value="exact_preview">Exact match previews</option><option value="ambiguous">Ambiguous matches</option><option value="deferred">Deferred</option><option value="all">All imported email</option><option value="ignored">Ignored email</option></select></label><p>Select an email, choose its exact application, then choose the outcome. Nothing is rejected automatically.</p><div className="btns"><button className="btn" disabled={busy||offset===0} onClick={()=>changeView(decisionFilter,Math.max(0,offset-50))}>Previous messages</button><span>{summary.total?`${offset+1} to ${offset+messages.length} of ${summary.total} messages`:"No messages in this view"}</span><button className="btn" disabled={busy||!summary.has_more} onClick={()=>changeView(decisionFilter,offset+50)}>Next messages</button></div></div>
      <div className="inbox-columns"><section className="panel inbox-list"><h2>{decisionFilter==="pending"?"Messages awaiting review":"Imported email"}</h2><p>Click a message to open its review form. Ignored messages are excluded from Awaiting review.</p>{visibleMessages.length?visibleMessages.map(m=><button key={m.id} className={`inbox-mail${active?.id===m.id?" on":""}`} aria-pressed={active?.id===m.id} onClick={()=>setSelected(m.id)}><strong>{clean(m.subject)||"No subject"}</strong><span>{clean(m.sender)} · {date(m.received_at)}</span><small>{clean(m.classification.replaceAll("_"," "))} · {clean(m.decision.replaceAll("_"," "))}</small></button>):<p>No messages await a decision in this view. Import historical email or choose another email view.</p>}</section><InboxReviewPanel key={active?.id??"empty"} message={active} applications={applications} busy={busy} action={action} showPending={()=>changeView("pending")}/></div>
    </>}
    {tab === "register" && <section className="panel"><h2>Application register</h2><p>Each key identifies one submitted record. Rejected applications stay in the total.</p><div className="inbox-table"><div className="inbox-row head"><span>Application</span><span>Role</span><span>Submitted</span><span>Status</span></div>{applications.map((a)=><div className="inbox-row" key={a.key}><span><strong><CompanyIdentity name={a.company} /></strong><small>{a.key}</small></span><span>{clean(a.title)}<small>{a.requisition_id ?? "No requisition recorded"}</small></span><span>{date(a.applied_at)}</span><span>{clean(a.status)}</span></div>)}</div>{!applications.length&&<p>No applications are recorded.</p>}</section>}
    {tab === "audit" && <section className="panel"><h2>Reconciliation audit trail</h2><p>Changes and corrections remain in chronological history.</p>{events.map((e)=><div className="inbox-event" key={e.id}><div><strong>{e.application_key}: {clean(e.kind)}</strong><p>{clean(e.before??"No status")} to {clean(e.after??"No status")}. {clean(e.reason)}</p><small>{date(e.recorded_at)} · {clean(e.actor)}{e.gmail_message_id?` · email evidence ${e.gmail_message_id}`:""}</small></div>{e.kind!=="undo"&&(e.application_key.startsWith("job:")||e.application_key.startsWith("external:"))&&!events.some((other)=>other.undo_of_id===e.id)&&<button className="btn" disabled={busy} onClick={()=>{if(window.confirm(`Undo event ${e.id} for ${e.application_key}?`)) action(()=>sendJson("POST",`/api/inbox/events/${e.id}/undo`,{}),"Status restored with a correction event")}}>Undo</button>}</div>)}{!events.length&&<p>No application events have been recorded since the evidence ledger was added.</p>}</section>}
    {tab === "rules" && <div className="inbox-columns"><section className="panel"><h2>Matching policy</h2><p>A company name or similar title never proves which application an email concerns. An automatic outcome requires explicit outcome text, one exact requisition, independently verified sender identity, plausible timing, and no protected terminal state.</p><p>Every missing or ambiguous condition leaves applications unchanged and enters human review.</p><p>Historical backfill is preview-only. Automatic outcomes are disabled by default and require a separate owner-approved server flag plus explicit opt-in.</p></section><section className="panel"><h2>Read-only access</h2><p>The connection requests Gmail read-only access. ACE cannot send, edit or delete mailbox messages through this integration. Only minimal extracted evidence is stored. Disconnect revokes the saved token locally.</p><p>Current automatic outcome setting: {connection?.auto_outcomes_enabled ? "Enabled" : "Disabled"}.</p>{connection?.connected && <button className="btn" disabled={busy || (!connection.automation_available && !connection.auto_outcomes_enabled)} onClick={()=>{ const enabled=!connection.auto_outcomes_enabled; if (!enabled || window.confirm("Enable verified-only automatic outcomes after the review pilot? Ambiguous email will still leave every application unchanged.")) action(()=>sendJson("PATCH","/api/inbox/automation",{enabled,confirmed:enabled}),enabled?"Verified outcome updates enabled":"Automatic outcomes disabled"); }}>{connection.auto_outcomes_enabled?"Disable automatic outcomes":connection.automation_available?"Enable verified-only outcomes":"Automatic outcomes locked"}</button>}<p><button className="btn" disabled={busy || !connection} onClick={()=>{if(window.confirm("Remove stored email snippets while keeping decision history?")) action(()=>sendJson("DELETE","/api/inbox/snippets"),"Stored email snippets removed")}}>Purge stored snippets</button></p><p><Link href="/app/applications">Return to Applications</Link></p></section></div>}
  </div>;
}
