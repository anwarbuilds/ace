// Small presentational pieces, usable from server and client components
// alike (no hooks, no state).

import type { ReactNode } from "react";
import { CompanyLogo } from "@/components/CompanyLogo";

import {
  STATUS_LABEL,
  UNSCORED,
  TIER_LABEL,
  tierLabel,
  tierOf,
} from "@/lib/format";
import type { ApplicationStatus, MatchState, Tier } from "@/lib/types";

/** One employer identity across lists and detail pages. */
export function Avatar({ name, large = false }: { name: string; large?: boolean }) {
  return <CompanyLogo name={name} size={large ? "large" : "table"} className={`co-av${large ? " lg" : ""}`} />;
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
export function MatchCell({ score, reason }: { score: number | null; reason: Exclude<MatchState, "scored"> }) {
  const t = tierOf(score);
  if (t === "unscored")
    return (
      <span className="m-unscored" title={UNSCORED[reason].long}>
        {UNSCORED[reason].short}
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
          Pending
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
