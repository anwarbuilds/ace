"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Invalidate the server projection after the existing marks bus settles a save.
 * No second application count or optimistic ledger is kept by Analytics. */
export function AnalyticsRefresh() {
  const {refresh}=useRouter();
  useEffect(()=>{
    const channel=typeof BroadcastChannel === "function" ? new BroadcastChannel("ace-marks") : null;
    if(channel)channel.onmessage=refresh;
    const visible=()=>{if(document.visibilityState === "visible")refresh();};
    window.addEventListener("focus",refresh);
    document.addEventListener("visibilitychange",visible);
    return ()=>{channel?.close();window.removeEventListener("focus",refresh);document.removeEventListener("visibilitychange",visible);};
  },[refresh]);
  return null;
}
