"use client";

import { ago, clock, parseDate } from "@/lib/format";

import { useApp, useNow } from "./AppProvider";
import { Popover, usePopover } from "./Popover";

// ACE polls every few minutes; a gap this long means the scheduler has
// stopped, and the page must say so rather than look current.
const STALE_MS = 45 * 60 * 1000;

export function useLive() {
  const { lastPoll } = useApp();
  const now = useNow();
  const last = parseDate(lastPoll);
  const stale = !last || now - last.getTime() > STALE_MS;
  return { lastPoll, stale, now };
}

/** The status island: always one line, always the same place. */
export function LiveChip() {
  const { lastPoll, stale, now } = useLive();
  const { tz } = useApp();
  const pop = usePopover();
  const label = !lastPoll
    ? "No pull recorded"
    : stale
      ? `Not updating · ${ago(lastPoll, now)}`
      : `Live · updated ${ago(lastPoll, now)}`;
  return (
    <>
      <button
        className={`live${stale ? " live-stale" : ""}`}
        onClick={(e) => pop.open(e.currentTarget)}
        suppressHydrationWarning
      >
        <span className={`dot${stale ? " stale" : ""}`} />
        {label}
      </button>
      <Popover anchor={pop.anchor} onClose={pop.close}>
        <h4>{stale ? "ace is not updating" : "Discovery status"}</h4>
        <p>
          Last pull{" "}
          {lastPoll ? `${clock(lastPoll, tz)}, ${ago(lastPoll, now)}${ago(lastPoll, now) === "just now" ? "" : " ago"}` : "not recorded"}.
        </p>
        {stale ? (
          <>
            <p>
              ace polls every few minutes, so a gap this long means the scheduler has stopped. Everything already found is
              still here.
            </p>
            <p>
              On the machine running ace: <b>docker compose ps</b>, then <b>docker compose up -d scheduler</b>.
            </p>
          </>
        ) : (
          <p>The page refreshes itself every two minutes.</p>
        )}
      </Popover>
    </>
  );
}
