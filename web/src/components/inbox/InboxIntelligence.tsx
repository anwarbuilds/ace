"use client";

// OAuth must leave the app and return through Google's full browser redirect.
/* eslint-disable @next/next/no-location-assign-relative-destination */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { CompanyIdentity } from "@/components/CompanyIdentity";
import { useApp } from "@/components/shell/AppProvider";
import { getJson, RequestError, sendJson } from "@/lib/client";
import { clean, parseDate } from "@/lib/format";
import { coverageText, verifyInbox, type InboxCoverage } from "@/lib/inboxSync";
import { InboxReviewPanel, KIND, PENDING, senderParts, since, STATE, type InboxEvent as Event, type InboxMessage as Message, type InboxApplication as Application } from "./InboxReviewPanel";

type Tab = "emails" | "register" | "audit" | "rules";
interface Connection {coverage: InboxCoverage | null; available: boolean; connected: boolean; state: string; email: string | null; last_synced_at: string | null; following_changes: boolean; last_error: string | null; auto_outcomes_enabled: boolean; automation_available: boolean; auto_rejections: boolean}
interface Counts {stored: number; needs_review: number; automatic: number; manual: number; reviewed: number; receipts: number; updates: number; stale: number}
interface Page {items: Message[]; total: number; has_more: boolean; counts: Counts; view: string; latest_received_at: string | null}
interface Sync {running: boolean; note: string; error: string; progress: string}

const PAGE = 50;
// Gmail is checked when the page opens and while it stays open, at most this often.
const FRESH_MS = 3 * 60_000;
const VIEWS: [string, string][] = [["pending","Waiting for you"],["recruiting","Recruiting email"],["automatic","Recorded by ACE"],["manual","Recorded by you"],["receipt","Acknowledgements"],["update","Saved correspondence"],["deferred","Decide later"],["unrelated","Not about applications"],["ignored","No outcome found"],["all","All imported email"],["review","Needs an application match"],["exact_preview","Matched, waiting for confirmation"],["ambiguous","Several possible applications"]];
const EMPTY: Counts = {stored:0,needs_review:0,automatic:0,manual:0,reviewed:0,receipts:0,updates:0,stale:0};

const plural = (n: number, one: string, many = `${one}s`) => `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
const time = (iso: string | null) => parseDate(iso)?.toLocaleTimeString("en-US", {hour: "numeric", minute: "2-digit"}) ?? "";
const stamp = (iso: string | null) => parseDate(iso)?.toLocaleString("en-US", {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"}) ?? "Not recorded";
const listDate = (iso: string, now: number) => {
  const moment = parseDate(iso);
  if (!moment) return "";
  return now && new Date(now).toDateString() === moment.toDateString() ? time(iso) : moment.toLocaleDateString("en-US", {month: "short", day: "numeric"});
};

/** What one sync found, in a sentence. */
function described(counts: Record<string, number>, rechecked: number, recorded: number): string {
  const fresh = Object.entries(counts).filter(([key]) => !["duplicate", "excluded"].includes(key)).reduce((sum, [, value]) => sum + value, 0);
  const waiting = (counts.review ?? 0) + (counts.exact_preview ?? 0);
  const parts = [counts.automatic ? `${counts.automatic} recorded automatically` : "", waiting ? `${waiting} waiting for you` : "",
    counts.receipt ? `${plural(counts.receipt, "acknowledgement")} filed` : ""].filter(Boolean);
  const other = fresh - (counts.automatic ?? 0) - waiting - (counts.receipt ?? 0);
  if (other) parts.push(`${other} with no application outcome`);
  let text = fresh ? `Found ${plural(fresh, "new email")}: ${parts.join(", ")}.` : "No new email since the last check.";
  if (rechecked) text += ` Read ${plural(rechecked, "older email")} again with the newest rules; ${recorded} recorded.`;
  return text;
}

export function InboxIntelligence() {
  const { refreshMarks, settleMarks, toast } = useApp();
  const router = useRouter();
  const params = useSearchParams();
  const requested = params.get("decision") ?? "auto";
  const offset = Math.max(0, Number(params.get("offset")) || 0);
  const searched = params.get("q") ?? "";
  const linkedId = Number(params.get("message")) || null;
  const [page, setPage] = useState<Page>({items: [], total: 0, has_more: false, counts: EMPTY, view: "pending", latest_received_at: null});
  const [loadedOnce, setLoadedOnce] = useState(false);
  const [tab, setTab] = useState<Tab>("emails");
  const [connection, setConnection] = useState<Connection | null>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [linked, setLinked] = useState<Message | null>(null);
  const [selected, setSelected] = useState<number | null>(linkedId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sync, setSync] = useState<Sync>({running: false, note: "", error: "", progress: ""});
  const [now, setNow] = useState(0);
  const [query, setQuery] = useState(searched);
  const [backfillDays, setBackfillDays] = useState(() => [0,30,90,365].includes(Number(params.get("days"))) ? Number(params.get("days")) : 0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const loadSequence = useRef(0);
  const syncing = useRef(false);
  const verificationDays = useRef(backfillDays);
  const restUntil = useRef(0);
  const latest = useRef<{connection: Connection | null; stale: number}>({connection: null, stale: 0});
  const inspector = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    const sequence = ++loadSequence.current;
    const filters = new URLSearchParams({offset: String(offset), limit: String(PAGE)});
    if (requested !== "all") filters.set("decision", requested);
    if (searched) filters.set("q", searched);
    const [c, m, a, e, one] = await Promise.all([
      getJson<Connection>("/api/inbox/connection"),
      getJson<Page>("/api/inbox/messages", filters),
      getJson<{items: Application[]}>("/api/inbox/applications"),
      getJson<{items: Event[]}>("/api/inbox/events"),
      linkedId ? getJson<Message>(`/api/inbox/messages/${linkedId}`).catch(() => null) : Promise.resolve(null),
    ]);
    if (sequence !== loadSequence.current) return;
    latest.current = {connection: c, stale: m.counts.stale};
    setConnection(c); setPage(m); setApplications(a.items); setEvents(e.items); setLinked(one); setLoadedOnce(true);
    setSelected(old => old != null && (m.items.some(item => item.id === old) || one?.id === old) ? old : m.items[0]?.id ?? one?.id ?? null);
  }, [requested, offset, searched, linkedId]);

  useEffect(() => { void Promise.resolve().then(load).catch(() => setError("Inbox Intelligence could not be loaded.")); }, [load]);

  // The clock for "3 minutes ago", read outside render.
  useEffect(() => {
    const tick = () => setNow(Date.now());
    void Promise.resolve().then(tick);
    const timer = window.setInterval(tick, 30_000);
    return () => window.clearInterval(timer);
  }, []);

  const notifyEvidence = useCallback(() => {
    settleMarks();
    router.refresh();
  }, [settleMarks, router]);

  async function action(run: () => Promise<unknown>, success: string | (() => string)) {
    setBusy(true); setError("");
    try { await run(); notifyEvidence(); await Promise.all([load(), refreshMarks()]); toast(typeof success === "function" ? success() : success); }
    catch (cause) { setError(cause instanceof RequestError && cause.status === 500 ? "Email import could not finish. Reload to see saved progress, then try again." : cause instanceof Error ? clean(cause.message) : "The operation failed. Reload and try again."); await load().catch(() => {}); }
    finally { setBusy(false); }
  }

  /** Verify the whole window and re-read stale evidence, including on page open. */
  const syncNow = useCallback(async (byHand: boolean, days = verificationDays.current) => {
    if (syncing.current || latest.current.connection?.state !== "ready") return;
    syncing.current = true;
    verificationDays.current = days;
    setSync(old => ({...old, running: true, error: "", progress: "Checking Gmail for new email"}));
    try {
      const {counts, rechecked, recorded} = await verifyInbox({days, stale: latest.current.stale,
        post: (path, body) => sendJson("POST", path, body),
        active: () => mounted.current && latest.current.connection?.state === "ready",
        progress: (progress, coverage) => {
          setSync(old => ({...old, progress}));
          if (coverage) setConnection(old => old && ({...old, coverage}));
        },
      });
      const note = described(counts, rechecked, recorded);
      notifyEvidence();
      await Promise.all([load(), refreshMarks()]);
      setSync({running: false, note, error: "", progress: ""});
      const fresh = Object.entries(counts).some(([key, value]) => key !== "duplicate" && key !== "ignored" && value > 0);
      if (byHand || fresh || recorded) toast(note);
    } catch (cause) {
      if (!mounted.current) return;
      restUntil.current = Date.now() + (cause instanceof RequestError && cause.status === 429 ? 10 : 1) * 60_000;
      setSync({running: false, note: "", progress: "", error: cause instanceof Error ? clean(cause.message) : "Gmail could not be checked."});
      notifyEvidence();
      await Promise.all([load(), refreshMarks()]).catch(() => {});
    } finally {
      syncing.current = false;
    }
  }, [load, refreshMarks, toast, notifyEvidence]);

  // Opening the page checks Gmail, and so does coming back to it later.
  const ready = connection?.connected && connection.state === "ready";
  useEffect(() => {
    if (!ready) return;
    const due = () => {
      const last = parseDate(latest.current.connection?.last_synced_at)?.getTime() ?? 0;
      return document.visibilityState === "visible" && Date.now() > restUntil.current &&
        (!latest.current.connection?.coverage || latest.current.connection.coverage.scope !== "job_mail" || !latest.current.connection.coverage.complete || latest.current.connection.coverage.days !== verificationDays.current || latest.current.stale > 0 || Date.now() - last > FRESH_MS);
    };
    const check = () => { if (due()) void syncNow(false); };
    void Promise.resolve().then(check);
    const timer = window.setInterval(check, 60_000);
    document.addEventListener("visibilitychange", check);
    return () => { window.clearInterval(timer); document.removeEventListener("visibilitychange", check); };
  }, [ready, syncNow]);

  const go = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) if (value) next.set(key, value); else next.delete(key);
    setSelected(null);
    router.replace(`/app/applications/inbox?${next}`, {scroll: false});
    setTab("emails");
  };
  const changeView = (decision: string, nextOffset = 0) => go({decision, offset: nextOffset ? String(nextOffset) : null, message: null});
  const pick = (id: number) => {
    setSelected(id);
    if (window.matchMedia("(max-width: 760px)").matches) inspector.current?.scrollIntoView({behavior: "smooth", block: "start"});
  };

  const counts = page.counts;
  const view = page.view;
  const viewLabel = VIEWS.find(([key]) => key === view)?.[1] ?? "Imported email";
  const byKey = new Map(applications.map(a => [a.key, a]));
  const active = page.items.find(m => m.id === selected) ?? (linked && linked.id === selected ? linked : null) ?? page.items[0] ?? null;
  const checkedAgo = since(connection?.last_synced_at, now);

  let tone = "loading", headline = "Checking your Gmail connection", detail = "", buttons: ReactNode = null;
  if (connection && !connection.connected) {
    tone = "off";
    headline = connection.available ? "Connect Gmail to follow your applications" : "Gmail is not set up on this server";
    detail = connection.available ? "ACE asks Google for read-only access. It cannot send, change or delete email." : "Gmail sign-in and token encryption must be configured on the server first.";
    if (connection.available) buttons = <button className="btn primary" onClick={() => window.location.assign("/api/inbox/google/start")}>Connect Gmail read-only</button>;
  } else if (connection && connection.state === "paused") {
    tone = "off"; headline = "Gmail sync is paused"; detail = "ACE is not reading new email. Resume to bring it in.";
    buttons = <button className="btn primary" disabled={busy} onClick={() => action(() => sendJson("PATCH", "/api/inbox/connection", {paused: false}), "Sync resumed")}>Resume sync</button>;
  } else if (connection && connection.state === "error") {
    tone = "warn"; headline = "Gmail needs attention"; detail = clean(connection.last_error) || "Google refused the saved connection.";
    buttons = <button className="btn primary" onClick={() => window.location.assign("/api/inbox/google/start")}>Reconnect Gmail</button>;
  } else if (connection) {
    const checked = connection.last_synced_at ? `Gmail checked ${checkedAgo || "recently"} (${stamp(connection.last_synced_at)}).` : "Gmail has not been checked for new email yet.";
    const coverage = coverageText(connection.coverage);
    const newest = page.latest_received_at ? ` Newest email in ACE arrived ${stamp(page.latest_received_at)}.` : "";
    if (sync.running) { tone = "busy"; headline = sync.progress || "Checking Gmail for new email"; detail = checked; }
    else if (sync.error) { tone = "warn"; headline = "Gmail could not be checked"; detail = `${sync.error} ${checked}`; }
    else if (counts.needs_review) { tone = "wait"; headline = `${plural(counts.needs_review, "email")} ${counts.needs_review === 1 ? "needs" : "need"} you`; detail = `${coverage} ${checked}${newest}`; }
    else if (connection.coverage?.days === 0 && connection.coverage.scope === "job_mail" && connection.coverage.complete && !connection.coverage.missing && !counts.stale) { tone = "ok"; headline = "Job-mail check complete"; detail = `${coverage} ${checked}${newest}`; }
    else { tone = "wait"; headline = "Email coverage needs checking"; detail = `${coverage} ${checked}`; }
    buttons = <>{counts.needs_review > 0 && view !== "pending" && <button className="btn" onClick={() => changeView("pending")}>Review {counts.needs_review === 1 ? "it" : "them"}</button>}<button className="btn primary" disabled={sync.running || busy} onClick={() => void syncNow(true)}>{sync.running ? "Syncing" : "Sync now"}</button></>;
  }

  return <div className="pg inbox-page">
    <div className="page-hero"><div><div className="eyebrow">Application intelligence</div><h1 className="h1">Inbox Intelligence</h1><p className="subtitle">ACE reads your Gmail for application email. Clear rejections are recorded for you; anything unclear waits here, shown exactly as it arrived, for one click.</p></div></div>
    <section className={`inbox-status s-${tone}`} aria-live="polite" aria-busy={sync.running}>
      <span className="inbox-status-icon" aria-hidden="true">{tone === "ok" ? <svg viewBox="0 0 24 24"><path d="m5 12.5 4.2 4.2L19 7"/></svg> : <svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></svg>}</span>
      <div className="inbox-status-text">
        <h2>{headline}</h2>
        {detail && <p>{detail}</p>}
        {!sync.running && sync.note && <p className="inbox-status-note">Last check: {sync.note}</p>}
        {ready && counts.stale > 0 && !sync.running && <p className="inbox-status-note">{plural(counts.stale, "email")} {counts.stale === 1 ? "was" : "were"} read under ACE&rsquo;s earlier rules. ACE re-reads {counts.stale === 1 ? "it" : "them"} when this page checks Gmail and records any clear rejection.</p>}
        {connection?.connected && <p className="inbox-status-meta">{connection.email} · Clear rejections recorded automatically: {connection.auto_rejections ? "on" : "off"} · <button className="link-btn" disabled={busy} onClick={() => action(() => sendJson("PATCH", "/api/inbox/connection", {paused: connection.state === "ready"}), connection.state === "ready" ? "Sync paused" : "Sync resumed")}>{connection.state === "ready" ? "Pause sync" : "Resume sync"}</button> · <button className="link-btn" disabled={busy} onClick={() => { if (window.confirm("Disconnect Gmail and revoke the saved grant? Stored audit history will remain.")) action(() => sendJson("DELETE", "/api/inbox/connection"), "Gmail disconnected"); }}>Disconnect</button></p>}
      </div>
      {buttons && <div className="btns">{buttons}</div>}
    </section>
    <div className="intelligence-kpis inbox-kpis">
      <button className="kpi inbox-kpi-button" onClick={() => changeView("pending")}><span className="kpi-l">Waiting for you</span><span className="kpi-n">{counts.needs_review}</span><span className="kpi-f">One click each</span></button>
      <button className="kpi inbox-kpi-button" onClick={() => changeView("automatic")}><span className="kpi-l">Recorded automatically</span><span className="kpi-n">{counts.automatic}</span><span className="kpi-f">Clear outcomes, each with Undo</span></button>
      <button className="kpi inbox-kpi-button" onClick={() => changeView("receipt")}><span className="kpi-l">Acknowledgements</span><span className="kpi-n">{counts.receipts}</span><span className="kpi-f">Application received, nothing to do</span></button>
      <button className="kpi inbox-kpi-button" onClick={() => changeView("all")}><span className="kpi-l">Emails imported</span><span className="kpi-n">{counts.stored}</span><span className="kpi-f">Everything ACE has read</span></button>
    </div>
    {error && <div role="alert" className="inbox-error">{error}</div>}
    <nav className="intelligence-tabs" aria-label="Inbox Intelligence views">{([["emails","Emails"],["register","Application register"],["audit","Audit trail"],["rules","How ACE decides"]] as const).map(([id, label]) => <button key={id} className={tab === id ? "on" : ""} aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>)}</nav>
    {tab === "emails" && <>
      {["review","exact_preview","ambiguous"].includes(view) && <p className="inbox-muted">Analytics evidence filter: {viewLabel}. <Link href="/app/applications/inbox">Show everything waiting for you</Link></p>}
      <div className="inbox-queue-tools">
        <label>Email view<select value={view} disabled={busy} onChange={event => changeView(event.target.value)}>{VIEWS.map(([key, label]) => <option key={key} value={key}>{label}{key === "pending" ? ` (${counts.needs_review.toLocaleString("en-US")})` : ""}</option>)}</select></label>
        <form className="inbox-search" role="search" onSubmit={event => { event.preventDefault(); go({q: query.trim() || null, offset: null, message: null}); }}>
          <label>Search email<input type="search" autoComplete="off" value={query} placeholder="Sender, company or subject" onChange={event => setQuery(event.target.value)}/></label>
          <button className="btn" type="submit" disabled={busy}>Search</button>
          {searched && <button className="btn" type="button" onClick={() => { setQuery(""); go({q: null, offset: null}); }}>Clear</button>}
        </form>
        <div className="btns"><button className="btn" disabled={busy || offset === 0} onClick={() => changeView(view, Math.max(0, offset - PAGE))}>Previous messages</button><span>{page.total ? `${offset + 1} to ${offset + page.items.length} of ${page.total}` : "No messages in this view"}</span><button className="btn" disabled={busy || !page.has_more} onClick={() => changeView(view, offset + PAGE)}>Next messages</button></div>
      </div>
      <div className="inbox-columns">
        <section className="panel inbox-list" aria-label={viewLabel}>
          <h2>{searched ? `${viewLabel} matching “${searched}”` : viewLabel}</h2>
          <p>{view === "pending" ? "Newest first. Each one needs a single click." : view === "recruiting" ? "Newest first, with what ACE did with each one." : "Newest first."}</p>
          {page.items.length ? page.items.map(m => {
            const app = m.selected_application_key ? byKey.get(m.selected_application_key) : undefined;
            return <button key={m.id} className={`inbox-mail${active?.id === m.id ? " on" : ""}${PENDING.includes(m.decision) ? " needs" : ""}`} aria-pressed={active?.id === m.id} onClick={() => pick(m.id)}>
              <span className="inbox-mail-top"><strong>{clean(senderParts(m.sender).name) || "Unknown sender"}</strong><time dateTime={m.received_at}>{listDate(m.received_at, now)}</time></span>
              <span className="inbox-mail-subject">{clean(m.subject) || "No subject"}</span>
              <span className="inbox-mail-tags">{m.classification !== "unknown" && <span className={`inbox-kind k-${m.classification}`}>{KIND[m.classification] ?? clean(m.classification)}</span>}<span className={`inbox-state d-${m.decision}`}>{STATE[m.decision] ?? clean(m.decision)}</span>{app && <small><CompanyIdentity name={app.company}/>, {clean(app.title)}</small>}</span>
            </button>;
          }) : loadedOnce && <div className="inbox-empty">{searched ? <p>No email in this view matches that search. <button className="link-btn" onClick={() => go({decision: "all", offset: null})}>Search all imported email</button></p> : view === "pending" ? <p>Nothing is waiting for you. <button className="link-btn" onClick={() => changeView("recruiting")}>See recent recruiting email</button></p> : <p>No email in this view.</p>}</div>}
        </section>
        <div ref={inspector} className="inbox-inspector-wrap"><InboxReviewPanel key={active?.id ?? "empty"} message={active} applications={applications} events={events} busy={busy} action={action} account={connection?.email} now={now}/></div>
      </div>
      {connection?.connected && <details className="inbox-import">
        <summary>Verify mailbox history</summary>
        <p>Check job-related mail across all dates, including archived mail. Spam, Trash and ordinary personal mail are outside automatic processing. Search terms may miss some job mail. Existing evidence and your decisions remain searchable. Progress is saved automatically.</p>
        <div className="inbox-backfill"><label>Email coverage<select value={backfillDays} disabled={busy || sync.running} onChange={event => { const days = Number(event.target.value); setBackfillDays(days); const next = new URLSearchParams(params); next.set("days", String(days)); router.replace(`/app/applications/inbox?${next}`, {scroll: false}); }}><option value={0}>All dates, job-related mail</option><option value={30}>Last 30 days</option><option value={90}>90 days</option><option value={365}>365 days</option></select></label><button className="btn" disabled={busy || sync.running || !ready} onClick={() => void syncNow(true, backfillDays)}>{sync.running ? "Verifying" : "Verify selected history"}</button></div>
      </details>}
    </>}
    {tab === "register" && <section className="panel"><h2>Application register</h2><p>Each key identifies one submitted record. Rejected applications stay in the total.</p><div className="inbox-table"><div className="inbox-row head"><span>Application</span><span>Role</span><span>Submitted</span><span>Status</span></div>{applications.map(a => <div className="inbox-row" key={a.key}><span><strong><CompanyIdentity name={a.company} /></strong><small>{a.key}</small></span><span>{clean(a.title)}<small>{a.requisition_id ?? "No requisition recorded"}</small></span><span>{stamp(a.applied_at)}</span><span>{clean(a.status)}</span></div>)}</div>{!applications.length && <p>No applications are recorded.</p>}</section>}
    {tab === "audit" && <section className="panel"><h2>Reconciliation audit trail</h2><p>Changes and corrections remain in chronological history.</p>{events.map(e => { const app = byKey.get(e.application_key); return <div className="inbox-event" key={e.id}><div><strong>{app ? <CompanyIdentity name={app.company}>{clean(app.company)}, {clean(app.title)}</CompanyIdentity> : e.application_key}: {clean(e.kind.replaceAll("_", " "))}</strong><p>{clean(e.before ?? "No status")} to {clean(e.after ?? "No status")}. {clean(e.reason)}</p><small>{stamp(e.recorded_at)} · {e.actor === "verified_automation" ? "ACE, automatically" : e.actor === "owner" ? "You" : clean(e.actor)}{e.gmail_message_id ? <> · <button className="link-btn" onClick={() => go({message: String(e.gmail_message_id), decision: "all", q: null, offset: null})}>Show the email</button></> : null}</small></div>{e.kind !== "undo" && (e.application_key.startsWith("job:") || e.application_key.startsWith("external:")) && !events.some(other => other.undo_of_id === e.id) && <button className="btn" disabled={busy} onClick={() => { if (window.confirm(`Undo this ${clean(e.kind.replaceAll("_", " "))} for ${app ? clean(app.company) : e.application_key}?`)) action(() => sendJson("POST", `/api/inbox/events/${e.id}/undo`, {}), "Status restored with a correction event"); }}>Undo</button>}</div>; })}{!events.length && <p>No application events have been recorded since the evidence ledger was added.</p>}</section>}
    {tab === "rules" && <div className="inbox-columns"><section className="panel"><h2>How ACE decides</h2><p>Routine application correspondence is saved and searchable without a review task or application status change. Account notifications and job alerts do not establish outcomes. Recognized outcomes with uncertain identity, wording or timing still need you, including historical mail.</p><p>ACE checks Gmail when you open this page, every few minutes while it stays open, and whenever you press Sync now. Nothing is sent, changed or deleted in Gmail.</p><p>A rejection is recorded automatically when the wording is explicit (for example &ldquo;we regret to inform you&rdquo; or &ldquo;we won&rsquo;t be moving forward&rdquo;), Gmail verifies the sender, the sender is not a personal mailbox, and exactly one application fits: its job ID is in the email, its exact title at that company is, or it is your only application there for a role like it.</p><p>It waits for you when two applications could fit, when the email predates the application, when the application already has a newer or final status, or when an email that thanks you for applying also sounds like a decision. You then see the email exactly as it arrived and ACE&rsquo;s likeliest application, and one click records it.</p><p>Acknowledgements such as &ldquo;thank you for applying&rdquo; are filed without changing anything. Interviews, assessments and offers are recorded automatically only after you turn on verified outcomes below; they also need the exact job ID from the employer&rsquo;s own domain. Every change can be undone.</p></section><section className="panel"><h2>Read-only access</h2><p>The connection requests Gmail read-only access. ACE cannot send, edit or delete mailbox messages through this integration. Only minimal extracted evidence is stored; the full email is read from Gmail each time you open it and never saved. Pictures on the sender&rsquo;s servers are not loaded, so senders cannot tell you opened their email.</p><p>Automatic rejections: {connection?.auto_rejections ? "On" : "Off"}. Automatic interviews, assessments and offers: {connection?.auto_outcomes_enabled ? "On" : "Off"}.</p>{connection?.connected && <button className="btn" disabled={busy || (!connection.automation_available && !connection.auto_outcomes_enabled)} onClick={() => { const enabled = !connection.auto_outcomes_enabled; if (!enabled || window.confirm("Enable verified-only automatic outcomes after the review pilot? Ambiguous email will still leave every application unchanged.")) action(() => sendJson("PATCH", "/api/inbox/automation", {enabled, confirmed: enabled}), enabled ? "Verified outcome updates enabled" : "Automatic outcomes disabled"); }}>{connection.auto_outcomes_enabled ? "Disable automatic outcomes" : connection.automation_available ? "Enable verified-only outcomes" : "Automatic outcomes locked"}</button>}<p><button className="btn" disabled={busy || !connection} onClick={() => { if (window.confirm("Remove stored email snippets while keeping decision history?")) action(() => sendJson("DELETE", "/api/inbox/snippets"), "Stored email snippets removed"); }}>Purge stored snippets</button></p><p><Link href="/app/applications">Return to Applications</Link></p></section></div>}
  </div>;
}
