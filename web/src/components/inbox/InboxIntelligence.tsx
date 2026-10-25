"use client";

// OAuth must leave the app and return through Google's full browser redirect.
/* eslint-disable @next/next/no-location-assign-relative-destination */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { getJson, sendJson } from "@/lib/client";
import { clean } from "@/lib/format";

type Tab = "queue" | "register" | "audit" | "rules";
interface Connection {available: boolean; connected: boolean; state: string; email: string | null; last_synced_at: string | null; last_error: string | null; auto_outcomes_enabled: boolean; automation_available: boolean}
interface Message {id: number; received_at: string; sender: string; subject: string; snippet: string; classification: string; requisition_id: string | null; decision: string; candidate_keys: string[]; reason: string; selected_application_key: string | null}
interface Application {key: string; company: string; title: string; requisition_id: string | null; applied_at: string | null; status: string}
interface Event {id: number; application_key: string; kind: string; before: string | null; after: string | null; actor: string; reason: string; recorded_at: string; undo_of_id: number | null; gmail_message_id: number | null}

const STAGES = ["applied", "screening", "interviewing", "offer", "accepted", "rejected", "withdrawn", "ghosted"];
const date = (value: string | null) => value ? new Date(value).toLocaleString("en-US") : "Not recorded";

export function InboxIntelligence() {
  const { refreshMarks, toast } = useApp();
  const params = useSearchParams();
  const decisionFilter = params.get("decision");
  const [tab, setTab] = useState<Tab>("queue");
  const [connection, setConnection] = useState<Connection | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [targetKey, setTargetKey] = useState("");
  const [stage, setStage] = useState("rejected");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [backfillDays, setBackfillDays] = useState(30);
  const [nextPage, setNextPage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [c, m, a, e] = await Promise.all([
      getJson<Connection>("/api/inbox/connection"),
      getJson<{items: Message[]}>("/api/inbox/messages", ["review", "exact_preview", "ambiguous"].includes(decisionFilter ?? "") ? new URLSearchParams({decision:decisionFilter!}) : undefined),
      getJson<{items: Application[]}>("/api/inbox/applications"),
      getJson<{items: Event[]}>("/api/inbox/events"),
    ]);
    setConnection(c); setMessages(m.items); setApplications(a.items); setEvents(e.items);
    setSelected((old) => old ?? m.items[0]?.id ?? null);
  }, [decisionFilter]);

  useEffect(() => { void Promise.resolve().then(load).catch(() => setError("Inbox Intelligence could not be loaded.")); }, [load]);

  async function action(run: () => Promise<unknown>, success: string) {
    setBusy(true); setError("");
    try { await run(); await Promise.all([load(), refreshMarks()]); toast(success); }
    catch (cause) { setError(cause instanceof Error ? clean(cause.message) : "The operation failed. Reload and try again."); }
    finally { setBusy(false); }
  }

  const visibleMessages = messages.filter((m) => decisionFilter === "ambiguous" ? m.decision === "review" && m.candidate_keys.length > 1 : ["review", "exact_preview"].includes(decisionFilter ?? "") ? m.decision === decisionFilter : true);
  const active = visibleMessages.find((m) => m.id === selected) ?? visibleMessages[0] ?? null;
  const target = applications.find((a) => a.key === targetKey) ?? null;
  const review = messages.filter((m) => m.decision === "review" || m.decision === "exact_preview");
  const pending = applications.filter((a) => !["accepted", "rejected", "withdrawn"].includes(a.status)).length;
  return <div className="pg inbox-page">
    <div className="page-hero"><div><div className="eyebrow">Application intelligence / mail reconciliation</div><h1 className="h1">Never guess the application.</h1><p className="subtitle">Capture recruiting evidence without closing the wrong opportunity. Every change has an audit trail and an Undo action.</p></div><div className="btns"><button className="btn" onClick={() => setTab("rules")}>View safety rules</button>{connection?.connected && <button className="btn primary" disabled={busy || connection.state !== "ready"} onClick={() => action(() => sendJson("POST", "/api/inbox/sync", {}), "Gmail catch-up finished")}>Run catch-up</button>}</div></div>
    <section className="inbox-hero"><div><div className="eyebrow">Protected by design</div><h2>A rejection email is not a matching application.</h2><p>Similar job titles, shared recruiting senders and uncertain requisitions never trigger an automatic rejection. Only unique, independently verified evidence can qualify after owner opt-in.</p></div><strong>Pending status protection: ON</strong></section>
    <div className="intelligence-kpis"><div className="kpi"><div className="kpi-l">Emails reviewed</div><div className="kpi-n">{messages.length}</div><div className="kpi-f">Stored evidence</div></div><div className="kpi"><div className="kpi-l">Automatic updates</div><div className="kpi-n">{messages.filter((m)=>m.decision==="automatic").length}</div><div className="kpi-f">Unique evidence only</div></div><div className="kpi"><div className="kpi-l">Needs your review</div><div className="kpi-n">{review.length}</div><div className="kpi-f">No automatic rejection</div></div><div className="kpi"><div className="kpi-l">Pending protected</div><div className="kpi-n">{pending}</div><div className="kpi-f">Current application records</div></div></div>
    {error && <div role="alert" className="inbox-error">{error}</div>}
    {!connection ? <p>Loading connection status</p> : <div className="inbox-connection"><div><strong>Gmail connection: {connection.connected ? clean(connection.state) : connection.available ? "Not connected" : "Setup required"}</strong><p>{connection.connected ? `Account ${connection.email}. Last sync: ${date(connection.last_synced_at)}.` : connection.available ? "Connect a Gmail account to preview historical recruiting email." : "Gmail OAuth and token encryption must be configured by the owner before connecting."}{connection.last_error ? ` ${clean(connection.last_error)}` : ""}</p></div><div className="btns">{connection.available && !connection.connected && <button className="btn primary" onClick={() => window.location.assign("/api/inbox/google/start")}>Connect Gmail read-only</button>}{connection.connected && <><button className="btn" disabled={busy} onClick={() => action(() => sendJson("PATCH", "/api/inbox/connection", {paused: connection.state === "ready"}), connection.state === "ready" ? "Sync paused" : "Sync ready")}>{connection.state === "ready" ? "Pause sync" : "Resume sync"}</button><button className="btn" disabled={busy} onClick={() => { if (window.confirm("Disconnect Gmail and revoke the saved grant? Stored audit history will remain.")) action(() => sendJson("DELETE", "/api/inbox/connection"), "Gmail disconnected"); }}>Disconnect</button></>}</div></div>}
    {connection?.connected && <div className="inbox-backfill"><label>Historical preview window <select value={backfillDays} onChange={(e)=>setBackfillDays(Number(e.target.value))}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option><option value={365}>1 year</option></select></label><button className="btn" disabled={busy} onClick={() => action(async () => { const result = await sendJson<{next_page_token: string | null}>("POST", "/api/inbox/backfill", {days:backfillDays,page_token:nextPage}); setNextPage(result.next_page_token); }, "Preview saved. No application status changed.")}>{nextPage ? "Preview next page" : "Preview historical email"}</button><span>Backfill is always preview-only. {nextPage ? "More messages remain." : ""}</span></div>}
    <nav className="intelligence-tabs" aria-label="Inbox Intelligence views">{([["queue","Review queue"],["register","Application register"],["audit","Audit trail"],["rules","Matching policy"]] as const).map(([id,label])=><button key={id} className={tab===id?"on":""} onClick={()=>setTab(id)}>{label}{id==="queue"?` ${review.length}`:""}</button>)}</nav>
      {tab === "queue" && <div className="inbox-columns"><section className="panel inbox-list"><h2>Inbox triage</h2><p>Each email is classified, then reconciled against submitted applications.</p>{decisionFilter && <p>Analytics evidence filter: {clean(decisionFilter.replaceAll("_", " "))}. Showing up to 100 matching messages, newest first. <Link href="/app/applications/inbox">Show all evidence</Link></p>}{visibleMessages.length ? visibleMessages.map((m)=><button key={m.id} className={`inbox-mail${active?.id===m.id?" on":""}`} onClick={()=>{setSelected(m.id);setTargetKey("");setConfirmed(false)}}><strong>{clean(m.subject)}</strong><span>{clean(m.sender)} · {date(m.received_at)}</span><small>{clean(m.classification)} · {clean(m.decision)}</small></button>) : <p>No recruiting email matches this view. Connect Gmail or review all stored evidence.</p>}</section><section className="panel inbox-inspector"><h2>Evidence inspector</h2>{active ? <><p className="eyebrow">{clean(active.classification)} / {clean(active.decision)}</p><h3>{clean(active.subject)}</h3><p>From: {clean(active.sender)} · {date(active.received_at)}</p><blockquote>{clean(active.snippet)}</blockquote><p><strong>Requisition:</strong> {active.requisition_id ? clean(active.requisition_id) : "Not stated"}</p><p><strong>Decision:</strong> {clean(active.reason)}</p><p><strong>Possible applications:</strong> {active.candidate_keys.length ? active.candidate_keys.join(", ") : "None identified"}</p>{["review","exact_preview","deferred"].includes(active.decision) && <><div className="btns"><button className="btn" disabled={busy} onClick={()=>action(()=>sendJson("PATCH",`/api/inbox/messages/${active.id}/decision`,{action:"unrelated"}),"Email marked unrelated")}>Mark unrelated</button><button className="btn" disabled={busy} onClick={()=>action(()=>sendJson("PATCH",`/api/inbox/messages/${active.id}/decision`,{action:"deferred"}),"Email deferred for review")}>Defer</button></div><div className="inbox-manual"><h3>Confirm the exact application</h3><label>Application<select value={targetKey} onChange={(e)=>setTargetKey(e.target.value)}><option value="">Choose an application</option>{applications.map((a)=><option value={a.key} key={a.key}>{a.key}: {clean(a.company)}, {clean(a.title)}</option>)}</select></label>{target && <p>Current status: {clean(target.status)}. Submitted: {date(target.applied_at)}. Requisition: {target.requisition_id ?? "Not stated"}.</p>}<label>New status<select value={stage} onChange={(e)=>setStage(e.target.value)}>{STAGES.map((s)=><option key={s} value={s}>{s}</option>)}</select></label><label className="inbox-confirm"><input type="checkbox" checked={confirmed} onChange={(e)=>setConfirmed(e.target.checked)}/> I verified this exact application and understand the status change.</label><button className="btn primary" disabled={busy || !target || !confirmed} onClick={() => action(() => sendJson("POST", "/api/inbox/review", {message_id:active.id,application_key:targetKey,status:stage,expected_status:target?.status,confirmed}), "Application status updated with an audit event")}>Confirm status change</button></div></>}</> : <p>Select an email to inspect evidence.</p>}</section></div>}
    {tab === "register" && <section className="panel"><h2>Application register</h2><p>Each key identifies one submitted record. Rejected applications stay in the total.</p><div className="inbox-table"><div className="inbox-row head"><span>Application</span><span>Role</span><span>Submitted</span><span>Status</span></div>{applications.map((a)=><div className="inbox-row" key={a.key}><span><strong>{clean(a.company)}</strong><small>{a.key}</small></span><span>{clean(a.title)}<small>{a.requisition_id ?? "No requisition recorded"}</small></span><span>{date(a.applied_at)}</span><span>{clean(a.status)}</span></div>)}</div>{!applications.length&&<p>No applications are recorded.</p>}</section>}
    {tab === "audit" && <section className="panel"><h2>Reconciliation audit trail</h2><p>Changes and corrections remain in chronological history.</p>{events.map((e)=><div className="inbox-event" key={e.id}><div><strong>{e.application_key}: {clean(e.kind)}</strong><p>{clean(e.before??"No status")} to {clean(e.after??"No status")}. {clean(e.reason)}</p><small>{date(e.recorded_at)} · {clean(e.actor)}{e.gmail_message_id?` · email evidence ${e.gmail_message_id}`:""}</small></div>{e.kind!=="undo"&&(e.application_key.startsWith("job:")||e.application_key.startsWith("external:"))&&!events.some((other)=>other.undo_of_id===e.id)&&<button className="btn" disabled={busy} onClick={()=>{if(window.confirm(`Undo event ${e.id} for ${e.application_key}?`)) action(()=>sendJson("POST",`/api/inbox/events/${e.id}/undo`,{}),"Status restored with a correction event")}}>Undo</button>}</div>)}{!events.length&&<p>No application events have been recorded since the evidence ledger was added.</p>}</section>}
    {tab === "rules" && <div className="inbox-columns"><section className="panel"><h2>Matching policy</h2><p>A company name or similar title never proves which application an email concerns. An automatic outcome requires explicit outcome text, one exact requisition, independently verified sender identity, plausible timing, and no protected terminal state.</p><p>Every missing or ambiguous condition leaves applications unchanged and enters human review.</p><p>Historical backfill is preview-only. Automatic outcomes are disabled by default and require a separate owner-approved server flag plus explicit opt-in.</p></section><section className="panel"><h2>Read-only access</h2><p>The connection requests Gmail read-only access. ACE cannot send, edit or delete mailbox messages through this integration. Only minimal extracted evidence is stored. Disconnect revokes the saved token locally.</p><p>Current automatic outcome setting: {connection?.auto_outcomes_enabled ? "Enabled" : "Disabled"}.</p>{connection?.connected && <button className="btn" disabled={busy || (!connection.automation_available && !connection.auto_outcomes_enabled)} onClick={()=>{ const enabled=!connection.auto_outcomes_enabled; if (!enabled || window.confirm("Enable verified-only automatic outcomes after the review pilot? Ambiguous email will still leave every application unchanged.")) action(()=>sendJson("PATCH","/api/inbox/automation",{enabled,confirmed:enabled}),enabled?"Verified outcome updates enabled":"Automatic outcomes disabled"); }}>{connection.auto_outcomes_enabled?"Disable automatic outcomes":connection.automation_available?"Enable verified-only outcomes":"Automatic outcomes locked"}</button>}<p><button className="btn" disabled={busy || !connection} onClick={()=>{if(window.confirm("Remove stored email snippets while keeping decision history?")) action(()=>sendJson("DELETE","/api/inbox/snippets"),"Stored email snippets removed")}}>Purge stored snippets</button></p><p><Link href="/app/applications">Return to Applications</Link></p></section></div>}
  </div>;
}
