// Small presentational pieces, usable from server and client components
// alike (no hooks, no state).

import type { CSSProperties, ReactNode } from "react";

import {
  STATUS_LABEL,
  TIER_LABEL,
  hueOf,
  monogram,
  tierLabel,
  tierOf,
} from "@/lib/format";
import type { ApplicationStatus, Tier } from "@/lib/types";

/** Initials on a tone of their own, so a column of employers can be
 *  scanned by shape before it is read. */
export function Avatar({ name, large = false }: { name: string; large?: boolean }) {
  return (
    <span
      className={`co-av${large ? " lg" : ""}`}
      style={{ "--h": hueOf(name) } as CSSProperties}
      aria-hidden="true"
    >
      {monogram(name)}
    </span>
  );
}

export function CompanyCell({ name, tier }: { name: string; tier: Tier }) {
  return (
    <div className="co-wrap">
      <Avatar name={name} />
      <div className="co-txt">
        <div className="co-name">{name}</div>
        {TIER_LABEL[tier] ? <div className="co-tier">{TIER_LABEL[tier]}</div> : null}
      </div>
    </div>
  );
}

/** The score as a percentage in the match colour, its tier beside it,
 *  and a hairline of how full it is. */
export function MatchCell({ score, scored }: { score: number | null; scored?: boolean }) {
  const t = tierOf(score);
  if (t === "unscored")
    return (
      <span className="m-unscored" title={scored === false ? "Not scored yet" : "Too little to score"}>
        {scored === false ? "Not scored yet" : "Not scored"}
      </span>
    );
  return (
    <>
      <div className="mt">
        <span className={`m-n m-${t}`}>
          {score}
          <i>%</i>
        </span>
        <span className={`m-tier m-${t}`}>{tierLabel(t)}</span>
      </div>
      <span className={`m-bar m-${t}`}>
        <i style={{ width: `${Math.max(2, Math.min(100, score ?? 0))}%` }} />
      </span>
    </>
  );
}

/** Unscored is a dotted, empty ring that says so, never a zero. */
export function ScoreRing({ score }: { score: number | null }) {
  const t = tierOf(score);
  const C = 2 * Math.PI * 40;
  if (t === "unscored")
    return (
      <div className="ring m-minimal" aria-label="Not scored">
        <svg width="92" height="92" viewBox="0 0 92 92">
          <circle className="trk" cx="46" cy="46" r="40" fill="none" strokeWidth="6" strokeDasharray="2 6" />
        </svg>
        <span className="score-n" style={{ fontSize: 18 }}>
          n/a
        </span>
      </div>
    );
  const fill = (Math.max(0, Math.min(100, score ?? 0)) / 100) * C;
  return (
    <div className={`ring m-${t}`} aria-label={`Match ${score} percent`}>
      <svg width="92" height="92" viewBox="0 0 92 92">
        <circle className="trk" cx="46" cy="46" r="40" fill="none" strokeWidth="6" />
        <circle
          className="val"
          cx="46"
          cy="46"
          r="40"
          fill="none"
          strokeWidth="6"
          strokeDasharray={`${fill.toFixed(1)} ${C.toFixed(1)}`}
        />
      </svg>
      <span className={`score-n m-${t}`}>{score}</span>
    </div>
  );
}

export function StatusBadge({ status, suffix }: { status: ApplicationStatus; suffix?: string }) {
  return (
    <span className={`badge ${status}`}>
      {STATUS_LABEL[status] ?? status}
      {suffix ? ` · ${suffix}` : ""}
    </span>
  );
}

export function EmptyBox({ title, children, actions }: { title: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      <p>{children}</p>
      {actions}
    </div>
  );
}
