"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

/** Invalidate the server projection after the existing marks bus settles a save.
 * No second application count or optimistic ledger is kept by Analytics. */
export function AnalyticsRefresh() {
  const router=useRouter();
  const pathname=usePathname();
  useEffect(()=>{ router.refresh(); },[router,pathname]);
  useEffect(()=>{
    const refresh=()=>router.refresh();
    const channel=typeof BroadcastChannel === "function" ? new BroadcastChannel("ace-marks") : null;
    if(channel)channel.onmessage=refresh;
    const visible=()=>{if(document.visibilityState === "visible")refresh();};
    window.addEventListener("focus",refresh);
    document.addEventListener("visibilitychange",visible);
    return ()=>{channel?.close();window.removeEventListener("focus",refresh);document.removeEventListener("visibilitychange",visible);};
  },[router]);
  return null;
}
