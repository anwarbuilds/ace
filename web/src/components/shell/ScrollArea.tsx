"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";

/** The page's scrolling panel. Its position is remembered per URL, so
 *  coming back from a job page returns to the row you left, and a list
 *  page records itself as the place "Back" on a job page leads to. */
export function ScrollArea({ children, list = false }: { children: ReactNode; list?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const path = usePathname();
  const search = useSearchParams().toString();
  const key = `${path}?${search}`;

  // The route this panel last showed, so a fresh mount (hydration) can be
  // told apart from moving to another page of the list.
  const shown = useRef<string | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (list) {
      try {
        sessionStorage.setItem("ace.lastList", key);
      } catch {}
    }
    let saved: number | null = null;
    try {
      const raw = sessionStorage.getItem(`ace.scroll:${key}`);
      saved = raw == null ? null : Number(raw);
    } catch {}
    // A remembered place wins. Otherwise a new route starts at the top,
    // and the first mount leaves the panel where the browser put it.
    if (saved != null && Number.isFinite(saved)) el.scrollTop = saved;
    else if (shown.current !== null && shown.current !== key) el.scrollTop = 0;
    shown.current = key;

    let t: ReturnType<typeof setTimeout> | null = null;
    const onScroll = () => {
      if (t) clearTimeout(t);
      t = setTimeout(() => {
        try {
          sessionStorage.setItem(`ace.scroll:${key}`, String(el.scrollTop));
        } catch {}
      }, 120);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      if (t) clearTimeout(t);
      el.removeEventListener("scroll", onScroll);
    };
  }, [key, list]);

  return (
    <div className="scroll" ref={ref}>
      {children}
    </div>
  );
}
