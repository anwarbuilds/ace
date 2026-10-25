import { clean } from "@/lib/format";
import Link from "next/link";

import {
  COMPONENT_LABEL,
  EVIDENCE_LABEL,
  STATE_LABEL,
  type Assessment,
  type Component,
  type Evidence,
  type Finding,
} from "@/lib/studio";

const ORDER: Component[] = ["requirements", "parseability", "quality", "fit"];

const SEVERITY: Record<Finding["severity"], string> = {
  blocker: "Blocker",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Note",
};

function band(n: number | null | undefined): string {
  if (n == null) return "";
  return n >= 75 ? "st-good" : n >= 50 ? "st-mid" : "st-low";
}

export function ScoreDial({ value, size = 112 }: { value: number | null; size?: number }) {
  const r = 46;
  const c = 2 * Math.PI * r;
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div className={`st-dial ${band(value)}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle cx="50" cy="50" r={r} className="st-dial-track" />
        <circle
          cx="50"
          cy="50"
          r={r}
          className="st-dial-fill"
          strokeDasharray={`${(pct / 100) * c} ${c}`}
          transform="rotate(-90 50 50)"
        />
      </svg>
      <span className="st-dial-n">{value == null ? "?" : value}</span>
    </div>
  );
}

function EvidenceRow({ e }: { e: Evidence }) {
  return (
    <div className={`st-ev st-ev-${e.state}`}>
      <span className="st-ev-skill">{e.skill}</span>
      <span className="st-ev-level">{e.level}</span>
      <span className="st-chip">{e.state === "related" && e.via ? `Related via ${e.via}` : EVIDENCE_LABEL[e.state]}</span>
      <span className="st-ev-quote">
        {e.quote ? (
          <>
            <q>{e.quote}</q>
            {e.line != null ? <span className="st-line">line {e.line + 1}</span> : null}
          </>
        ) : (
          <span className="st-muted">Nothing in the resume shows this.</span>
        )}
      </span>
    </div>
  );
}

export function AssessmentView({ a, versionLabel }: { a: Assessment; versionLabel?: string }) {
  const r = a.result;
  const required = r.evidence.filter((e) => e.level === "required");
  const preferred = r.evidence.filter((e) => e.level === "preferred");
  return (
    <div className="st-result">
      <div className="st-hero card">
        <ScoreDial value={a.aggregate} />
        <div className="st-hero-txt">
          <p className="eyebrow" style={{ margin: 0 }}>
            Estimated ace compatibility score
          </p>
          <h2 className="st-h2">
            {a.job_source === "stored" && a.job_id ? (
              <Link href={`/app/jobs/${a.job_id}`} prefetch={false}>
                {a.job_company ? `${a.job_company}, ` : ""}
                {clean(a.job_title) || "Job"}
              </Link>
            ) : (
              <>{clean(a.job_title) || a.job_company || "Pasted job description"}</>
            )}
          </h2>
          <p className="why" style={{ margin: 0 }}>
            {STATE_LABEL[a.state]}
            {a.state === "scored" ? `, ${a.confidence} confidence` : ""}
            {versionLabel ? `, resume: ${versionLabel}` : ""}. Algorithm {a.algorithm_version}.
          </p>
        </div>
      </div>

      <div className="st-comps">
        {ORDER.map((k) => {
          const n = a.components[k];
          return (
            <div className="st-comp card" key={k}>
              <div className="st-comp-head">
                <span>{COMPONENT_LABEL[k]}</span>
                <span className={`st-comp-n ${band(n)}`}>{n == null ? "Cannot judge" : n}</span>
              </div>
              <div className="st-meter">
                <span className={band(n)} style={{ width: `${n ?? 0}%` }} />
              </div>
              <span className="st-weight">weight {Math.round((r.weights[k] ?? 0) * 100)}%</span>
            </div>
          );
        })}
      </div>

      {r.recommendations.length ? (
        <div className="sect">
          <p className="eyebrow">What to fix first</p>
          <div className="st-findings">
            {r.recommendations.map((f, i) => (
              <div className={`st-finding st-sev-${f.severity}`} key={i}>
                <span className="st-chip">{SEVERITY[f.severity]}</span>
                <span className="st-finding-c">{COMPONENT_LABEL[f.component]}</span>
                <span>{f.message}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {required.length || preferred.length ? (
        <div className="sect">
          <p className="eyebrow">
            Requirements and the evidence for each, {required.length} required, {preferred.length} preferred
          </p>
          <div className="st-evs">
            {[...required, ...preferred].map((e) => (
              <EvidenceRow e={e} key={`${e.level}-${e.skill}`} />
            ))}
          </div>
        </div>
      ) : null}

      {r.unknowns.length ? (
        <div className="sect">
          <p className="eyebrow">Not stated, or cannot be judged</p>
          <ul className="st-unknowns">
            {r.unknowns.map((u, i) => (
              <li key={i}>{u}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="note">
        This is ace&rsquo;s own rubric, versioned and repeatable. It is not any employer&rsquo;s applicant tracking
        system and does not predict a recruiter&rsquo;s decision. Weights: requirement evidence{" "}
        {Math.round((r.weights.requirements ?? 0) * 100)}%, parseability {Math.round((r.weights.parseability ?? 0) * 100)}%,
        hard fit {Math.round((r.weights.fit ?? 0) * 100)}%, content quality {Math.round((r.weights.quality ?? 0) * 100)}%.
      </div>
    </div>
  );
}
