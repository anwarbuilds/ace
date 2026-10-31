"use client";

import { useEffect, useEffectEvent, useState, type ReactNode } from "react";
import { ANALYTICS_REFRESH_REQUEST, ANALYTICS_REFRESH_STATE } from "./AnalyticsRefresh";

interface Props {
  scope: string;
  attemptedAt: number;
  asOf: string | null;
  timezone: string;
  success: boolean;
  children: ReactNode;
}
interface Snapshot { asOf: string | null; children: ReactNode }

/** Retain only this mounted selection's last successful server-rendered result.
 * Nothing is persisted to browser storage or shared with another route/session. */
export function AnalyticsFreshness({ scope, attemptedAt, asOf, timezone, success, children }: Props) {
  const [request, setRequest] = useState<{ id: number; previousAttempt: number; pending: boolean; failed: boolean } | null>(null);
  const [state, setState] = useState(() => ({
    scope, attemptedAt, failed: !success,
    snapshot: success ? { asOf, children } as Snapshot : null,
  }));
  if (scope !== state.scope) {
    if (request) setRequest(null);
    setState({ scope, attemptedAt, failed: !success, snapshot: success ? { asOf, children } : null });
  } else if (attemptedAt > state.attemptedAt) {
    const older = success && asOf && state.snapshot?.asOf && Date.parse(asOf) < Date.parse(state.snapshot.asOf);
    setState({ scope, attemptedAt, failed: !success || !!older,
      snapshot: success && !older ? { asOf, children } : state.snapshot });
  }
  const snapshot = state.snapshot;
  const response = useEffectEvent((event: Event) => {
    const detail = (event as CustomEvent<{ phase: string; id: number }>).detail;
    if (detail.phase === "started") setRequest({ id: detail.id, previousAttempt: attemptedAt, pending: true, failed: false });
    else if (detail.phase === "offline") setRequest({ id: detail.id, previousAttempt: attemptedAt, pending: false, failed: true });
    else if (detail.phase === "delayed" && request?.id === detail.id) setRequest({ ...request, failed: true });
    else if (detail.phase === "settled" && request?.id === detail.id) {
      // A failed RSC/network request can settle without replacing any page props.
      // Comparing response tokens avoids depending on browser/server clock parity.
      setRequest({ ...request, pending: false, failed: attemptedAt === request.previousAttempt });
    }
  });
  useEffect(() => {
    const receive = (event: Event) => response(event);
    window.addEventListener(ANALYTICS_REFRESH_STATE, receive);
    return () => window.removeEventListener(ANALYTICS_REFRESH_STATE, receive);
  }, []);
  const failed = state.failed || !!request?.failed;
  const pending = !!request?.pending;
  const delayed = pending && !!request?.failed;
  const checked = snapshot?.asOf && Number.isFinite(Date.parse(snapshot.asOf))
    ? new Date(snapshot.asOf).toLocaleString("en-US", { timeZone: timezone, month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" })
    : null;
  const notice = <div className="an-freshness" role="status" aria-live="polite" aria-busy={pending} data-state={delayed ? "stale" : pending ? "refreshing" : failed ? snapshot ? "stale" : "unavailable" : "fresh"} data-analytics-as-of={snapshot?.asOf ?? undefined}>
      <span>{delayed ? `Refresh is delayed. Showing the last verified results${checked ? ` from ${checked}` : ""}.` : pending ? "Checking for updates. The last verified results remain visible." : failed
        ? snapshot ? `Refresh failed. Showing the last verified results${checked ? ` from ${checked}` : ""}.` : "Analytics is unavailable. Retry to check this selection again."
        : checked ? `Updated ${checked}. Checks automatically while this page is visible.` : "Checks automatically while this page is visible."}</span>
      {failed && <button className="btn" type="button" disabled={pending} onClick={() => window.dispatchEvent(new Event(ANALYTICS_REFRESH_REQUEST))}>Retry refresh</button>}
    </div>;
  return <>
    {(failed || pending) && notice}
    {snapshot?.children ?? children}
    {!failed && !pending && notice}
  </>;
}
