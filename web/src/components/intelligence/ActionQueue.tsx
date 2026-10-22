"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getJson, sendJson } from "@/lib/client";
import { clean } from "@/lib/format";

interface ActionItem {key: string; kind: string; title: string; reason: string; href: string; evidence_at: string; state: "open" | "completed" | "dismissed"}

export function ActionQueue() {
  const [items, setItems] = useState<ActionItem[] | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { void getJson<{items: ActionItem[]}>("/api/intelligence/actions").then((data) => setItems(data.items)).catch(() => setError("Actions could not be loaded.")); }, []);
  async function change(item: ActionItem, state: ActionItem["state"]) {
    setBusy(item.key); setError("");
    try {
      await sendJson("POST", "/api/intelligence/actions", {key: item.key, state});
      setItems((current) => current?.map((row) => row.key === item.key ? {...row, state} : row) ?? null);
    } catch { setError("The action could not be saved. Reload and try again."); }
    finally { setBusy(""); }
  }
  const open = items?.filter((item) => item.state === "open") ?? [];
  const handled = items?.filter((item) => item.state !== "open") ?? [];
  return <section className="panel intelligence-actions"><h2>Evidence-linked actions</h2><p>Complete or dismiss a suggestion without changing an application status. Reopen it any time.</p>
    {error && <p role="alert">{error}</p>}
    {!items && !error && <p>Loading actions</p>}
    {items && !items.length && <p>No dated follow-ups, unmatched emails or recent qualifying Pulls need attention.</p>}
    {open.map((item) => <div className="intelligence-action" key={item.key}><div><Link href={item.href}><strong>{clean(item.title)}</strong></Link><p>{clean(item.reason)}. Evidence: {new Date(item.evidence_at).toLocaleDateString("en-US")}.</p></div><div className="btns"><button className="btn" disabled={!!busy} onClick={() => change(item, "completed")}>Complete</button><button className="btn" disabled={!!busy} onClick={() => change(item, "dismissed")}>Dismiss</button></div></div>)}
    {!!handled.length && <details><summary>{handled.length} handled actions</summary>{handled.map((item) => <div className="intelligence-action" key={item.key}><div><Link href={item.href}><strong>{clean(item.title)}</strong></Link><p>{clean(item.state)}. {clean(item.reason)}</p></div><button className="btn" disabled={!!busy} onClick={() => change(item, "open")}>Reopen</button></div>)}</details>}
  </section>;
}
