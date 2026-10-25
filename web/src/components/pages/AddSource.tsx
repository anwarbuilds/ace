"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { sendJson } from "@/lib/client";
import type { SourceResult } from "@/lib/types";

/** Paste a job link, a careers page or a name; ace finds the board,
 *  checks it belongs to that company, and starts polling it. */
export function AddSource() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [msg, setMsg] = useState<{ text: string; kind: "" | "ok" | "warn" } | null>(null);
  const [busy, setBusy] = useState(false);

  const add = async () => {
    const value = text.trim();
    if (!value) {
      setMsg({ text: "Paste a link or a company name first.", kind: "warn" });
      return;
    }
    setBusy(true);
    setMsg({ text: `Looking for a board at ${value}…`, kind: "" });
    try {
      const d = await sendJson<SourceResult>("POST", "/api/sources", { text: value });
      if (d.status === "added") {
        setMsg({
          text: `Now watching ${d.company} on ${d.source_type}/${d.source_account}, ${d.job_count} postings. Verified: ${d.evidence}. Its jobs appear within a few minutes.`,
          kind: "ok",
        });
        setText("");
      } else if (d.status === "already_known") {
        setMsg({ text: `ace already watches ${d.company || d.source_account}.`, kind: "" });
        setText("");
      } else setMsg({ text: d.detail || "No board ace can read was found there.", kind: "warn" });
      router.refresh();
    } catch {
      setMsg({ text: "Could not reach ace.", kind: "warn" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="cov-add">
        <input
          id="cov-input"
          type="text"
          autoComplete="off"
          spellCheck={false}
          placeholder="https://company.com/careers  ·  or  ·  Cursor"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void add();
          }}
        />
        <button className="btn btn-primary" onClick={add} disabled={busy}>
          Add
        </button>
      </div>
      {msg ? <div className={`cov-out ${msg.kind}`}>{msg.text}</div> : null}
    </>
  );
}
