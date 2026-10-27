"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

/** Keep this coordinator in the persistent app layout. A refreshed server page
 * can replace its children; mounting a new coordinator there can refresh again.
 * Analytics always reads the server projection, never a second local ledger. */
export function AnalyticsRefresh() {
  const { refresh } = useRouter();
  const pathname = usePathname();
  const active = pathname === "/app/analytics" || pathname === "/app/applications/analytics";
  // The initial server response already contains fresh data. Avoid fetching it
  // again during hydration; keep the guard in the layout for return navigation.
  const lastPath = useRef(pathname);

  useEffect(() => {
    if (lastPath.current === pathname) return;
    lastPath.current = pathname;
    if (active) refresh();
  }, [active, pathname, refresh]);

  useEffect(() => {
    if (!active) return;
    const channel = typeof BroadcastChannel === "function" ? new BroadcastChannel("ace-marks") : null;
    if (channel) channel.onmessage = refresh;
    const visible = () => { if (document.visibilityState === "visible") refresh(); };
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", visible);
    return () => {
      channel?.close();
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [active, refresh]);
  return null;
}
