import { parseDate } from "@/lib/format";

// Same thresholds as /api/pulls: most boards are read every five
// minutes, so no successful read for a quarter hour is late and for
// three quarters is stopped. From the scheduler's evidence, never from
// whether this page loaded.
export const DELAYED_MS = 15 * 60 * 1000;
export const STALLED_MS = 45 * 60 * 1000;

export type LiveState = "live" | "delayed" | "stalled" | "unknown";

export function liveState(lastPoll: string | null | undefined, now: number): LiveState {
  const last = parseDate(lastPoll);
  if (!last) return "unknown";
  const age = now - last.getTime();
  if (age <= DELAYED_MS) return "live";
  if (age <= STALLED_MS) return "delayed";
  return "stalled";
}

export const LIVE_LABEL: Record<LiveState, string> = {
  live: "Live",
  delayed: "Delayed",
  stalled: "Stalled",
  unknown: "No check recorded",
};
