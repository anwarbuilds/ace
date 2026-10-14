"use client";

import Link from "next/link";
import { useLayoutEffect, useRef } from "react";

export interface TabDef {
  key: string;
  label: string;
  count: number | null;
  href: string;
}

// The pill's last position, kept across navigations so it slides from
// the tab it was on rather than appearing at the new one.
let memo: { x: number; w: number } | null = null;

/** A segmented control with one pill that slides to the chosen tab. */
export function Tabs({ tabs, active }: { tabs: TabDef[]; active: string }) {
  const bar = useRef<HTMLDivElement>(null);
  const ind = useRef<HTMLSpanElement>(null);

  useLayoutEffect(() => {
    const place = () => {
      const on = bar.current?.querySelector<HTMLElement>('.tab[aria-selected="true"]');
      const pill = ind.current;
      if (!on || !pill) return;
      const x = on.offsetLeft;
      const w = on.offsetWidth;
      if (memo && (memo.x !== x || memo.w !== w)) {
        pill.style.transition = "none";
        pill.style.transform = `translateX(${memo.x}px)`;
        pill.style.width = `${memo.w}px`;
        void pill.offsetWidth;
        pill.style.transition = "";
      }
      pill.style.transform = `translateX(${x}px)`;
      pill.style.width = `${w}px`;
      memo = { x, w };
    };
    place();
    document.fonts?.ready.then(place);
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [active]);

  return (
    <div className="tabs has-ind" role="tablist" ref={bar}>
      <span className="tab-ind" aria-hidden="true" ref={ind} />
      {tabs.map((t) => (
        <Link
          key={t.key}
          className="tab"
          role="tab"
          aria-selected={t.key === active}
          href={t.href}
          scroll={false}
        >
          {t.label}
          {t.count != null ? <span className="tab-n">{t.count.toLocaleString("en-US")}</span> : null}
        </Link>
      ))}
    </div>
  );
}
