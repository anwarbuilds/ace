"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useApp } from "@/components/shell/AppProvider";
import { RequestError, sendJson } from "@/lib/client";
import { KIND_LABEL, STATUS_LABEL, type Fact, type FactKind, type FactStatus } from "@/lib/studio";

const KINDS: FactKind[] = ["experience", "project", "education", "skill", "certification", "summary", "preference"];

const FILTER_LABEL = { review: "Waiting for review", verified: "Verified", deprecated: "Retired", all: "All" };

function dates(f: Fact): string {
  const fmt = (d: string) => {
    if (!d) return "";
    if (d === "present") return "Present";
    const [y, m] = d.split("-");
    const month = new Date(Number(y), Number(m) - 1, 1).toLocaleString("en-US", { month: "short" });
    return `${month} ${y}`;
  };
  const a = fmt(f.start_date);
  const b = fmt(f.end_date);
  return a && b ? `${a} to ${b}` : a || b;
}

function message(err: unknown) {
  return err instanceof RequestError ? err.message : "ace did not answer. Try again in a moment.";
}

function FactEditor({ fact, onDone }: { fact?: Fact; onDone: () => void }) {
  const router = useRouter();
  const { toast } = useApp();
  const [error, setError] = useState("");
  async function save(form: FormData) {
    const body = {
      kind: form.get("kind"),
      title: form.get("title"),
      organization: form.get("organization"),
      start_date: form.get("start_date"),
      end_date: form.get("end_date"),
      bullets: String(form.get("bullets") ?? "").split("\n"),
      skills: String(form.get("skills") ?? "").split(","),
      note: form.get("note"),
    };
    try {
      if (fact) await sendJson("PATCH", `/api/studio/facts/${fact.id}`, body);
      else await sendJson("POST", "/api/studio/facts", body);
      toast(fact ? "Fact updated" : "Fact added, verified");
      onDone();
      router.refresh();
    } catch (err) {
      setError(message(err));
    }
  }
  return (
    <form className="st-editor card" action={save} autoComplete="off">
      <div className="st-grid2">
        <label>
          Kind
          <select name="kind" defaultValue={fact?.kind ?? "experience"}>
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {KIND_LABEL[k]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Title
          <input name="title" defaultValue={fact?.title ?? ""} required placeholder="Software Engineer" />
        </label>
        <label>
          Organization
          <input name="organization" defaultValue={fact?.organization ?? ""} placeholder="Company or school" />
        </label>
        <div className="st-grid2 st-dates">
          <label>
            From
            <input name="start_date" defaultValue={fact?.start_date ?? ""} placeholder="2023-01" />
          </label>
          <label>
            To
            <input name="end_date" defaultValue={fact?.end_date ?? ""} placeholder="present" />
          </label>
        </div>
      </div>
      <label>
        Achievements, one per line
        <textarea name="bullets" rows={4} defaultValue={(fact?.bullets ?? []).join("\n")} />
      </label>
      <label>
        Skills used, separated by commas
        <input name="skills" defaultValue={(fact?.skills ?? []).join(", ")} />
      </label>
      <label>
        Note to yourself
        <input name="note" defaultValue={fact?.note ?? ""} />
      </label>
      {error ? <p className="auth-err">{error}</p> : null}
      <div className="controls" style={{ paddingLeft: 0 }}>
        <button className="btn btn-primary btn-sm" type="submit">
          {fact ? "Save" : "Add fact"}
        </button>
        <button className="btn btn-secondary btn-sm" type="button" onClick={onDone}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function FactCard({ fact }: { fact: Fact }) {
  const router = useRouter();
  const { toast } = useApp();
  const [editing, setEditing] = useState(false);
  async function setStatus(status: FactStatus, undoTo?: FactStatus) {
    try {
      await sendJson("PATCH", `/api/studio/facts/${fact.id}`, { status });
      router.refresh();
      toast(`Marked ${STATUS_LABEL[status].toLowerCase()}`, undoTo ? () => void setStatus(undoTo) : undefined);
    } catch (err) {
      toast(message(err));
    }
  }
  if (editing) return <FactEditor fact={fact} onDone={() => setEditing(false)} />;
  const when = dates(fact);
  return (
    <article className={`st-fact card st-fact-${fact.status}`}>
      <div className="st-fact-head">
        <div className="st-fact-t">
          <h3>{fact.title || KIND_LABEL[fact.kind]}</h3>
          {fact.organization || when ? (
            <p>
              {fact.organization}
              {fact.organization && when ? ", " : ""}
              {when}
            </p>
          ) : null}
        </div>
        <span className={`st-chip st-status-${fact.status}`}>{STATUS_LABEL[fact.status]}</span>
      </div>
      {fact.bullets.length ? (
        <ul className="st-bullets">
          {fact.bullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      ) : null}
      {fact.skills.length && fact.kind !== "skill" ? (
        <div className="skills">
          {fact.skills.map((k) => (
            <span key={k} className="sk">
              {k}
            </span>
          ))}
        </div>
      ) : null}
      {fact.note ? <p className="st-note">{fact.note}</p> : null}
      {fact.origin === "parsed" && fact.evidence ? (
        <details className="st-source">
          <summary>Read from your resume</summary>
          <pre>{fact.evidence}</pre>
        </details>
      ) : null}
      <div className="st-fact-acts">
        {fact.status !== "verified" ? (
          <button className="btn btn-secondary btn-sm" onClick={() => setStatus("verified", fact.status)}>
            Verify
          </button>
        ) : null}
        {fact.status !== "needs_clarification" && fact.status !== "deprecated" ? (
          <button className="link-btn" onClick={() => setStatus("needs_clarification", fact.status)}>
            Needs clarification
          </button>
        ) : null}
        <button className="link-btn" onClick={() => setEditing(true)}>
          Edit
        </button>
        {fact.status !== "deprecated" ? (
          <button className="link-btn" onClick={() => setStatus("deprecated", fact.status)}>
            Retire
          </button>
        ) : (
          <button className="link-btn" onClick={() => setStatus("suggested")}>
            Restore
          </button>
        )}
      </div>
    </article>
  );
}

export function FactsBoard({ facts, filter, kind }: { facts: Fact[]; filter: keyof typeof FILTER_LABEL; kind: string }) {
  const [adding, setAdding] = useState(false);
  const counts = {
    review: facts.filter((f) => f.status === "suggested" || f.status === "needs_clarification").length,
    verified: facts.filter((f) => f.status === "verified").length,
    deprecated: facts.filter((f) => f.status === "deprecated").length,
    all: facts.filter((f) => f.status !== "deprecated").length,
  };
  const shown = facts.filter((f) => {
    if (kind && f.kind !== kind) return false;
    if (filter === "review") return f.status === "suggested" || f.status === "needs_clarification";
    if (filter === "verified") return f.status === "verified";
    if (filter === "deprecated") return f.status === "deprecated";
    return f.status !== "deprecated";
  });
  const href = (status: string, k = kind) => {
    const p = new URLSearchParams();
    if (status !== "all") p.set("status", status);
    if (k) p.set("kind", k);
    const q = p.toString();
    return `/app/resume-studio/facts${q ? `?${q}` : ""}`;
  };
  return (
    <>
      <div className="st-filters">
        {(Object.keys(FILTER_LABEL) as (keyof typeof FILTER_LABEL)[]).map((k) => (
          <Link key={k} className={`chip${filter === k ? " ctl-active" : ""}`} href={href(k)}>
            {FILTER_LABEL[k]} <span className="chip-n">{counts[k]}</span>
          </Link>
        ))}
        {kind ? (
          <Link className="chip ctl-active" href={href(filter, "")}>
            {KIND_LABEL[kind as FactKind] ?? kind}, clear
          </Link>
        ) : null}
        <span className="spacer" />
        <button className="btn btn-secondary btn-sm" onClick={() => setAdding((v) => !v)}>
          Add a fact
        </button>
      </div>
      <p className="why" style={{ margin: "12px 0 20px" }}>
        Only verified facts count as evidence. Suggested ones were read from your resume and wait for you; nothing here
        is ever invented, and retiring keeps the record.
      </p>
      {adding ? <FactEditor onDone={() => setAdding(false)} /> : null}
      {KINDS.map((k) => {
        const group = shown.filter((f) => f.kind === k);
        if (!group.length) return null;
        return (
          <section className="sect" key={k}>
            <p className="eyebrow">
              {KIND_LABEL[k]} <span className="st-muted">{group.length}</span>
            </p>
            <div className={k === "skill" ? "st-facts st-facts-tight" : "st-facts"}>
              {group.map((f) => (
                <FactCard key={f.id} fact={f} />
              ))}
            </div>
          </section>
        );
      })}
      {!shown.length ? <p className="why">Nothing here yet.</p> : null}
    </>
  );
}
