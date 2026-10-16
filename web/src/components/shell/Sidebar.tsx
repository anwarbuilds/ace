"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { useApp, useNow } from "./AppProvider";
import { liveState } from "./liveState";
import { NAV, isActive } from "./nav";
import { NavIcon } from "./NavIcon";

const ENGINE: Record<string, string> = {
  live: "Discovery engine online",
  delayed: "Discovery engine delayed",
  stalled: "Discovery engine stopped",
  unknown: "No check recorded yet",
};

/** The application's navigation: three groups in the order the owner
 *  works, each entry its own route. Icons only on a narrow screen. */
export function Sidebar({ counts, email }: { counts: Record<string, number | null>; email: string | null }) {
  const path = usePathname();
  const { lastPoll, marks } = useApp();
  const now = useNow();
  const state = liveState(lastPoll, now);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCollapsed(localStorage.getItem("ace.sidebar") === "collapsed");
    } catch {}
  }, []);

  function toggle() {
    setCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem("ace.sidebar", next ? "collapsed" : "open");
      } catch {}
      return next;
    });
  }

  return (
    <aside className={`sb${collapsed ? " collapsed" : ""}`} aria-label="Application navigation">
      <div className="sb-brand-row">
        <Link className="sb-brand" href="/app/pulls" aria-label="ace, Pulls">
          <span>a</span>ce
        </Link>
        <button
          className="sb-collapse"
          type="button"
          onClick={toggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <NavIcon name="left" size="sm" />
        </button>
      </div>
      {NAV.map((group) => (
        <div className="sb-group" key={group.label}>
          <div className="sb-label">{group.label}</div>
          <nav className="sb-nav" aria-label={group.label}>
            {group.items.map((item) => {
              const on = isActive(item, path);
              const count = item.href === "/app/applications" ? marks.applications_total : counts[item.href];
              return (
                <Link
                  key={item.href}
                  className={`sb-link${on ? " on" : ""}`}
                  href={item.href}
                  aria-current={on ? "page" : undefined}
                  title={item.label}
                >
                  <NavIcon name={item.icon} />
                  <span className="sb-text">{item.label}</span>
                  {count ? <span className="sb-count">{count.toLocaleString("en-US")}</span> : null}
                </Link>
              );
            })}
          </nav>
        </div>
      ))}
      <div className="sb-bottom">
        <div className="sb-user">
          <div className="sb-avatar" aria-hidden="true">
            {(email ?? "ace").slice(0, 1).toUpperCase()}
          </div>
          <div>
            <div className="sb-user-t">Personal workspace</div>
            <div className="sb-user-s">Private, owner</div>
          </div>
        </div>
        <div className={`sb-engine s-${state}`} suppressHydrationWarning>
          <i className="pulse" aria-hidden="true" />
          {ENGINE[state]}
        </div>
      </div>
    </aside>
  );
}
