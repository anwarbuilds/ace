"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { getJson, setCookie } from "@/lib/client";
import { clean, undash } from "@/lib/format";
import type { Job, MarkCounts, PullsResponse } from "@/lib/types";

export type ThemeChoice = "dark" | "light" | "system";

export const THEME_LABEL: Record<ThemeChoice, string> = { dark: "Night", light: "Day", system: "System" };

interface Toast {
  id: number;
  message: string;
  undo?: () => void;
}

interface AppState {
  tz: string;
  prevVisit: Date | null;
  lastPoll: string | null;
  theme: ThemeChoice;
  setTheme: (t: ThemeChoice) => void;
  cycleTheme: () => void;
  marks: MarkCounts;
  refreshMarks: () => void;
  toast: (message: string, undo?: () => void) => void;
  /** Optimistic edits to jobs, keyed by id, laid over server data. */
  patches: Record<number, Partial<Job>>;
  patchJob: (id: number, patch: Partial<Job>) => void;
  hidden: Set<number>;
  hideJob: (id: number, hide: boolean) => void;
  answersOpen: boolean;
  setAnswersOpen: (open: boolean) => void;
  menuOpen: boolean;
  setMenuOpen: (open: boolean) => void;
}

const Ctx = createContext<AppState | null>(null);

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside AppProvider");
  return v;
}

/** A clock that ticks, so "5m ago" keeps telling the truth. */
export function useNow(intervalMs = 30000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

export function withPatch(job: Job, patches: Record<number, Partial<Job>>): Job {
  const p = patches[job.id];
  return p ? { ...job, ...p } : job;
}

// Desktop alerts, remembered per pull as a count rather than a flag: a
// pull is fifteen minutes long and keeps growing, so its third role must
// be announced even after its first was. The first load only sets the
// baseline, so turning alerts on does not replay the week.
const ALERTED_KEY = "ace.alertedPulls";

function announceNewRoles(data: PullsResponse, onOpen: () => void): void {
  let seen: Record<string, number> | null = null;
  try {
    const v = JSON.parse(localStorage.getItem(ALERTED_KEY) || "null");
    seen = v && typeof v === "object" ? v : null;
  } catch {
    seen = null;
  }
  const first = seen === null;
  const map: Record<string, number> = seen ?? {};
  const fresh: { count: number; jobs: Job[] }[] = [];
  for (const s of data.sessions) {
    const had = map[s.id] || 0;
    const now = s.qualifying_discovered || 0;
    if (now > had && !first) fresh.push({ count: now - had, jobs: s.jobs || [] });
    if (now > had || !(s.id in map)) map[s.id] = now;
  }
  try {
    const kept: Record<string, number> = {};
    Object.keys(map)
      .map(Number)
      .sort((a, b) => b - a)
      .slice(0, 50)
      .forEach((id) => (kept[id] = map[id]));
    localStorage.setItem(ALERTED_KEY, JSON.stringify(kept));
  } catch {}
  if (!fresh.length || typeof Notification !== "function" || Notification.permission !== "granted") return;
  const total = fresh.reduce((a, f) => a + f.count, 0);
  const roles: string[] = [];
  fresh.forEach((f) =>
    f.jobs.forEach((j) => {
      if (roles.length < 4)
        roles.push(undash(`${j.company}, ${clean(j.title)}${j.applied_before ? " (applied before)" : ""}`));
    }),
  );
  try {
    const n = new Notification(`ace: ${total} new role${total === 1 ? "" : "s"} pass${total === 1 ? "es" : ""} your filters`, {
      body: roles.join("\n") || "Open ace to see them.",
      tag: "ace-new-roles",
    });
    n.onclick = () => {
      window.focus();
      onOpen();
      n.close();
    };
  } catch {}
}

// No em dash reaches the screen, whatever a source wrote: text nodes and
// the title, placeholder and aria-label attributes are rewritten as
// they appear. What the user types (textareas) is theirs and left alone.
const DASH_TEST = /[—―]|\s–\s/;
const ATTRS = ["title", "placeholder", "aria-label"];

function undashTree(node: Node): void {
  if (node.nodeType === Node.TEXT_NODE) {
    const p = node.parentNode;
    if (p && !/^(TEXTAREA|SCRIPT|STYLE)$/.test(p.nodeName) && node.nodeValue && DASH_TEST.test(node.nodeValue))
      node.nodeValue = undash(node.nodeValue);
    return;
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return;
  const el = node as Element;
  if (/^(TEXTAREA|SCRIPT|STYLE)$/.test(el.nodeName)) return;
  for (const a of ATTRS) {
    const v = el.getAttribute(a);
    if (v && DASH_TEST.test(v)) el.setAttribute(a, undash(v));
  }
  for (let c = el.firstChild; c; c = c.nextSibling) undashTree(c);
}

export function AppProvider({
  children,
  tz,
  prevVisit,
  lastPoll,
  theme: initialTheme,
  marks: initialMarks,
}: {
  children: ReactNode;
  tz: string;
  prevVisit: number | null;
  lastPoll: string | null;
  theme: ThemeChoice;
  marks: MarkCounts;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const [theme, setThemeState] = useState<ThemeChoice>(initialTheme);
  const [marks, setMarks] = useState(initialMarks);
  const [toastState, setToast] = useState<Toast | null>(null);
  const [patches, setPatches] = useState<Record<number, Partial<Job>>>({});
  const [hidden, setHidden] = useState<Set<number>>(new Set());
  const [answersOpen, setAnswersOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Server props are the truth after a refresh; local copies follow them.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMarks(initialMarks), [initialMarks]);

  // Optimistic edits belong to the screen they were made on. A new
  // route renders fresh server data, which already carries them.
  // Reset during render when the route changes (React's pattern for
  // state derived from a changing input), not in an effect.
  const routeKey = `${pathname}?${search.toString()}`;
  const [seenRoute, setSeenRoute] = useState(routeKey);
  if (seenRoute !== routeKey) {
    setSeenRoute(routeKey);
    setPatches({});
    setHidden(new Set());
    setMenuOpen(false);
  }

  const setTheme = useCallback((t: ThemeChoice) => {
    setCookie("ace_theme", t);
    if (t === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", t);
    setThemeState(t);
  }, []);

  const toast = useCallback((message: string, undo?: () => void) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ id: Date.now(), message, undo });
    toastTimer.current = setTimeout(() => setToast(null), 4000);
  }, []);

  const cycleTheme = useCallback(() => {
    const next: ThemeChoice = theme === "dark" ? "light" : theme === "light" ? "system" : "dark";
    setTheme(next);
    toast(`Theme: ${THEME_LABEL[next]}`);
  }, [theme, setTheme, toast]);

  const refreshMarks = useCallback(() => {
    getJson<MarkCounts>("/api/marks")
      .then(setMarks)
      .catch(() => {});
  }, []);

  const patchJob = useCallback((id: number, patch: Partial<Job>) => {
    setPatches((p) => ({ ...p, [id]: { ...p[id], ...patch } }));
  }, []);

  const hideJob = useCallback((id: number, hide: boolean) => {
    setHidden((h) => {
      const n = new Set(h);
      if (hide) n.add(id);
      else n.delete(id);
      return n;
    });
  }, []);

  // Links from the old UI were /#job/123; a redirect keeps the fragment,
  // so it arrives here and opens the job's own page.
  useEffect(() => {
    const m = /^#job\/(\d+)$/.exec(window.location.hash);
    if (m) router.replace(`/app/jobs/${m[1]}`);
  }, [router]);

  // The reader's own zone, so dates render where they are standing.
  useEffect(() => {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!zone || zone === tz) return;
    setCookie("ace_tz", zone);
    // Once per browser. Deferred a moment and skipped if the reader has
    // already moved on, so it can never swallow a click.
    const here = window.location.href;
    const t = setTimeout(() => {
      if (window.location.href === here) router.refresh();
    }, 400);
    return () => clearTimeout(t);
  }, [tz, router]);

  // Dash guard over everything drawn, portals and popovers included.
  useEffect(() => {
    undashTree(document.body);
    const obs = new MutationObserver((list) => {
      for (const m of list) {
        if (m.type === "characterData") undashTree(m.target);
        else if (m.type === "attributes") undashTree(m.target);
        else m.addedNodes.forEach(undashTree);
      }
    });
    obs.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ATTRS,
    });
    return () => obs.disconnect();
  }, []);

  // Spotlight: cards light where the pointer is.
  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const c = (e.target as Element | null)?.closest?.(".card,.stat") as HTMLElement | null;
      if (!c) return;
      const r = c.getBoundingClientRect();
      c.style.setProperty("--mx", `${e.clientX - r.left}px`);
      c.style.setProperty("--my", `${e.clientY - r.top}px`);
    };
    document.addEventListener("pointermove", onMove, { passive: true });
    return () => document.removeEventListener("pointermove", onMove);
  }, []);

  // Live: re-read the page every two minutes, and announce new roles.
  useEffect(() => {
    const check = () => {
      getJson<PullsResponse>("/api/sessions", new URLSearchParams({ limit: "30", jobs_per_session: "6" }))
        .then((d) => announceNewRoles(d, () => router.push("/app/pulls")))
        .catch(() => {});
    };
    check();
    const t = setInterval(() => {
      router.refresh();
      check();
    }, 120000);
    return () => clearInterval(t);
  }, [router]);

  // Global keys: "/" to search a list, and Escape closing whatever is open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target as Element)?.tagName ?? "");
      if (e.key === "/" && !typing) {
        const q = document.getElementById("q") as HTMLInputElement | null;
        if (q) {
          e.preventDefault();
          q.focus();
        }
        return;
      }
      if (typing && e.key === "Escape") {
        (e.target as HTMLElement).blur();
        return;
      }
      if (e.key === "Escape") {
        if (answersOpen) setAnswersOpen(false);
        else if (menuOpen) setMenuOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [answersOpen, menuOpen]);

  const value = useMemo<AppState>(
    () => ({
      tz,
      prevVisit: prevVisit ? new Date(prevVisit) : null,
      lastPoll,
      theme,
      setTheme,
      cycleTheme,
      marks,
      refreshMarks,
      toast,
      patches,
      patchJob,
      hidden,
      hideJob,
      answersOpen,
      setAnswersOpen,
      menuOpen,
      setMenuOpen,
    }),
    [
      tz,
      prevVisit,
      lastPoll,
      theme,
      setTheme,
      cycleTheme,
      marks,
      refreshMarks,
      toast,
      patches,
      patchJob,
      hidden,
      hideJob,
      answersOpen,
      menuOpen,
    ],
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      {toastState ? (
        <div className="toast" role="status" key={toastState.id}>
          <span>{toastState.message}</span>
          {toastState.undo ? (
            <button
              className="link-btn"
              onClick={() => {
                toastState.undo?.();
                setToast(null);
              }}
            >
              Undo
            </button>
          ) : null}
        </div>
      ) : null}
    </Ctx.Provider>
  );
}
