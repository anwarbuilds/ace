"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AssessmentView } from "@/components/studio/AssessmentView";
import { RequestError, getJson, sendJson } from "@/lib/client";
import type { Assessment, Version } from "@/lib/studio";
import type { JobPage } from "@/lib/types";

interface PickedJob {
  id: number;
  company: string;
  title: string;
}

export function Checker({
  versions,
  primaryId,
  initialJob,
}: {
  versions: Version[];
  primaryId: number | null;
  initialJob: PickedJob | null;
}) {
  const [versionId, setVersionId] = useState<number | null>(primaryId ?? versions[0]?.id ?? null);
  const [mode, setMode] = useState<"stored" | "pasted">("stored");
  const [job, setJob] = useState<PickedJob | null>(initialJob);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<PickedJob[]>([]);
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Assessment | null>(null);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) return;
    const t = setTimeout(() => {
      getJson<JobPage>("/api/jobs", new URLSearchParams({ q: term, limit: "8", sort: "best_match" }))
        .then((d) => setResults(d.items.map((i) => ({ id: i.id, company: i.company, title: i.title }))))
        .catch(() => setResults([]));
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  if (!versions.length) {
    return (
      <div className="empty">
        <h3>No resume to check</h3>
        <p>Upload a resume in the Overview first.</p>
      </div>
    );
  }

  const label = versions.find((v) => v.id === versionId)?.label;

  async function run() {
    setBusy(true);
    setError("");
    try {
      const body =
        mode === "stored"
          ? { version_id: versionId, job_id: job?.id }
          : { version_id: versionId, job_text: text, job_title: title, job_company: company };
      setResult(await sendJson<Assessment>("POST", "/api/studio/check", body));
    } catch (err) {
      setError(err instanceof RequestError ? err.message : "ace did not answer. Try again in a moment.");
    }
    setBusy(false);
  }

  const ready = versionId != null && (mode === "stored" ? job != null : text.trim().length > 0);

  return (
    <>
      <div className="st-split sect">
        <div className="card st-card">
          <p className="eyebrow">1. Resume</p>
          <select className="st-select" value={versionId ?? ""} onChange={(e) => setVersionId(Number(e.target.value))}>
            {versions.map((v) => (
              <option key={v.id} value={v.id}>
                {v.label}
                {v.is_primary ? ", used for matching" : ""}
              </option>
            ))}
          </select>
          <p className="why" style={{ marginTop: 10 }}>
            The checker reads this version&rsquo;s text and the layout of the file it came from.
          </p>
        </div>
        <div className="card st-card">
          <p className="eyebrow">2. Job</p>
          <div className="st-seg" role="tablist">
            <button role="tab" aria-selected={mode === "stored"} onClick={() => setMode("stored")}>
              A job in ace
            </button>
            <button role="tab" aria-selected={mode === "pasted"} onClick={() => setMode("pasted")}>
              Paste a description
            </button>
          </div>
          {mode === "stored" ? (
            job ? (
              <div className="st-picked">
                <span>
                  <b>{job.company}</b>, {job.title}
                </span>
                <button className="link-btn" onClick={() => setJob(null)}>
                  Change
                </button>
              </div>
            ) : (
              <div className="st-pick">
                <input
                  className="st-input"
                  placeholder="Search by company or title"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  aria-label="Search jobs"
                />
                {results.length && q.trim().length >= 2 ? (
                  <div className="st-picklist">
                    {results.map((r) => (
                      <button key={r.id} onClick={() => setJob(r)}>
                        <b>{r.company}</b> {r.title}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            )
          ) : (
            <div className="st-paste">
              <div className="st-grid2">
                <input className="st-input" placeholder="Company" value={company} onChange={(e) => setCompany(e.target.value)} />
                <input className="st-input" placeholder="Role title" value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <textarea
                className="st-text"
                rows={8}
                placeholder="The full job description, including its requirements"
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
              <p className="why">Marked as pasted by you, and kept with the result.</p>
            </div>
          )}
        </div>
      </div>
      <div className="controls" style={{ paddingLeft: 0, marginBottom: 22 }}>
        <button className="btn btn-primary" disabled={!ready || busy} onClick={run}>
          {busy ? "Checking" : "Check this resume"}
        </button>
        {result ? (
          <Link className="link-btn" href={`/app/resume-studio/history/${result.id}`}>
            Saved to history
          </Link>
        ) : null}
      </div>
      {error ? <p className="auth-err">{error}</p> : null}
      {result ? <AssessmentView a={result} versionLabel={label} /> : null}
    </>
  );
}
