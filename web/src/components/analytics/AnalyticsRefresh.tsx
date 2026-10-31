"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useEffectEvent, useRef, useTransition } from "react";

export const ANALYTICS_REFRESH_REQUEST = "ace-analytics-refresh";
export const ANALYTICS_REFRESH_STATE = "ace-analytics-refresh-state";
const POLL_MS = 120_000;
const COALESCE_MS = 500;
type Reason = "return" | "wake" | "poll" | "evidence" | "retry";

/** The persistent shell owns one coordinator, including when a page read fails.
 * Refresh the existing server projection; never maintain another metrics ledger. */
export function AnalyticsRefresh() {
  const { refresh } = useRouter();
  const pathname = usePathname();
  const active = pathname === "/app/analytics" || pathname === "/app/applications/analytics";
  const [pending, startTransition] = useTransition();
  const lastPath = useRef(pathname);
  const busy = useRef(false);
  const lastStarted = useRef(-Infinity);
  const queuedEvidence = useRef(false);
  const deferred = useRef<ReturnType<typeof setTimeout> | null>(null);
  const generation = useRef(0);
  const inFlight = useRef<number | null>(null);
  const slowTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Effect events keep the contextual router current without replacing listeners
  // or restarting timers when a new server response replaces the page.
  const request = useEffectEvent((reason: Reason) => {
    if (!active || document.visibilityState !== "visible") return;
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      window.dispatchEvent(new window.CustomEvent(ANALYTICS_REFRESH_STATE, { detail: { phase: "offline", id: ++generation.current } }));
      return;
    }
    if (busy.current || Date.now() - lastStarted.current < COALESCE_MS) {
      // A decision can commit after an in-flight read began. Read once more
      // after it settles; focus/visibility/poll bursts need no trailing read.
      if (reason === "evidence" || reason === "retry") {
        queuedEvidence.current = true;
        if (!busy.current && !deferred.current) deferred.current = setTimeout(() => {
          deferred.current = null;
          window.dispatchEvent(new Event(ANALYTICS_REFRESH_REQUEST));
        }, COALESCE_MS - (Date.now() - lastStarted.current));
      }
      return;
    }
    busy.current = true;
    queuedEvidence.current = false;
    lastStarted.current = Date.now();
    inFlight.current = ++generation.current;
    window.dispatchEvent(new window.CustomEvent(ANALYTICS_REFRESH_STATE, { detail: { phase: "started", id: inFlight.current } }));
    slowTimer.current = setTimeout(() => {
      window.dispatchEvent(new window.CustomEvent(ANALYTICS_REFRESH_STATE, { detail: { phase: "delayed", id: inFlight.current } }));
    }, 30_000);
    startTransition(() => refresh());
  });

  useEffect(() => {
    if (pending) return;
    if (inFlight.current !== null) {
      window.dispatchEvent(new window.CustomEvent(ANALYTICS_REFRESH_STATE, { detail: { phase: "settled", id: inFlight.current } }));
      inFlight.current = null;
    }
    if (slowTimer.current) clearTimeout(slowTimer.current);
    slowTimer.current = null;
    busy.current = false;
    if (deferred.current) clearTimeout(deferred.current);
    if (queuedEvidence.current && active) {
      deferred.current = setTimeout(() => {
        deferred.current = null;
        request("evidence");
      }, Math.max(0, COALESCE_MS - (Date.now() - lastStarted.current)));
    }
  }, [active, pending]);

  useEffect(() => {
    // Hydration already has a server read. A return from Inbox needs one read,
    // while subsequent response replacements must not start a refresh loop.
    if (lastPath.current === pathname) return;
    lastPath.current = pathname;
    busy.current = false;
    inFlight.current = null;
    queuedEvidence.current = false;
    lastStarted.current = -Infinity;
    if (active) request("return");
  }, [active, pathname]);

  useEffect(() => {
    if (!active) return;
    const channel = typeof BroadcastChannel === "function" ? new BroadcastChannel("ace-marks") : null;
    if (channel) channel.onmessage = () => request("evidence");
    const wake = () => request("wake");
    const retry = () => request("retry");
    const offline = () => window.dispatchEvent(new window.CustomEvent(ANALYTICS_REFRESH_STATE, { detail: { phase: "offline", id: ++generation.current } }));
    const timer = setInterval(() => request("poll"), POLL_MS);
    window.addEventListener("focus", wake);
    window.addEventListener("online", retry);
    window.addEventListener("offline", offline);
    document.addEventListener("visibilitychange", wake);
    window.addEventListener(ANALYTICS_REFRESH_REQUEST, retry);
    return () => {
      clearInterval(timer);
      if (slowTimer.current) clearTimeout(slowTimer.current);
      slowTimer.current = null;
      if (deferred.current) clearTimeout(deferred.current);
      deferred.current = null;
      channel?.close();
      window.removeEventListener("focus", wake);
      window.removeEventListener("online", retry);
      window.removeEventListener("offline", offline);
      document.removeEventListener("visibilitychange", wake);
      window.removeEventListener(ANALYTICS_REFRESH_REQUEST, retry);
    };
  }, [active]);
  return null;
}
