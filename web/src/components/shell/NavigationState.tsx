"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect } from "react";

// A click on a link to another page of ace dims the page until the next
// one is here, so a slow answer never looks like an ignored click. A new
// route also shows its loading skeleton; this covers what keeps the same
// route, such as the next page of a list, a tab or a sort.
export function NavigationState() {
  const path = usePathname();
  const search = useSearchParams().toString();

  useEffect(() => {
    delete document.documentElement.dataset.navigating;
  }, [path, search]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const onClick = (e: MouseEvent) => {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const link = (e.target as Element | null)?.closest?.("a[href]");
      if (!(link instanceof HTMLAnchorElement)) return;
      if ((link.target && link.target !== "_self") || link.hasAttribute("download")) return;
      const to = new URL(link.href, window.location.href);
      if (to.origin !== window.location.origin || !to.pathname.startsWith("/app/")) return;
      if (to.pathname === window.location.pathname && to.search === window.location.search) return;
      document.documentElement.dataset.navigating = "";
      // Never left dimmed: a navigation that fails or is abandoned clears
      // itself.
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => delete document.documentElement.dataset.navigating, 15000);
    };
    document.addEventListener("click", onClick);
    return () => {
      document.removeEventListener("click", onClick);
      if (timer) clearTimeout(timer);
    };
  }, []);

  return null;
}
