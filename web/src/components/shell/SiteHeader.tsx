"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";

import { useApp } from "./AppProvider";

interface NavLink {
  href: string;
  label: string;
  count?: number | null;
  exact?: boolean;
}

/** The site's top navigation: one row of page links, like any website.
 *  Every link is its own route; the active page is marked for screen
 *  readers with aria-current and drawn as a pill. */
export function SiteHeader({
  queueCount,
  externalCount,
  answersFilled,
  coverageGaps,
}: {
  queueCount: number;
  externalCount: number;
  answersFilled: number;
  coverageGaps: number;
}) {
  const path = usePathname();
  const { marks, cycleTheme, setPaletteOpen, menuOpen, setMenuOpen } = useApp();
  const [more, setMore] = useState(false);
  const [mac, setMac] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMac(/Mac|iPhone|iPad/.test(navigator.userAgent)), []);

  // A new page closes any open menu.
  const [seen, setSeen] = useState(path);
  if (seen !== path) {
    setSeen(path);
    setMore(false);
    if (menuOpen) setMenuOpen(false);
  }

  useEffect(() => {
    if (!more) return;
    const close = (e: MouseEvent) => {
      if (!moreRef.current?.contains(e.target as Node)) setMore(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [more]);

  const on = (l: NavLink) => (l.exact ? path === l.href : path === l.href || path.startsWith(`${l.href}/`));

  const primary: NavLink[] = [
    { href: "/app", label: "Overview", exact: true },
    { href: "/app/opportunities", label: "Opportunities", count: queueCount },
    { href: "/app/applications", label: "Applications", count: (marks.applied || 0) + externalCount },
    { href: "/app/resume-studio", label: "Resume Studio" },
    { href: "/app/activity", label: "Activity" },
    { href: "/app/answers", label: "Answers", count: answersFilled },
  ];
  const secondary: NavLink[] = [
    { href: "/app/archive", label: "Archive", count: marks.archived },
    { href: "/app/insights/skills", label: "Skills" },
    { href: "/app/coverage", label: "Coverage", count: coverageGaps },
  ];
  const moreActive = secondary.some(on);

  const link = (l: NavLink, cls = "site-link") => (
    <Link key={l.href} className={cls} href={l.href} aria-current={on(l) ? "page" : undefined}>
      {l.label}
      {l.count ? <span className="site-count">{l.count.toLocaleString("en-US")}</span> : null}
    </Link>
  );

  return (
    <header className="site">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <div className="site-row">
        <Link className="site-brand brand-name" href="/app" aria-label="ace, overview">
          ace
        </Link>
        <nav className="site-nav" aria-label="Main">
          {primary.map((l) => link(l))}
          <div className="site-more" ref={moreRef}>
            <button
              className="site-link"
              aria-expanded={more}
              aria-haspopup="menu"
              aria-current={moreActive ? "page" : undefined}
              onClick={() => setMore((v) => !v)}
            >
              More
              <span className={`site-caret${more ? " up" : ""}`} aria-hidden="true" />
            </button>
            {more ? (
              <div className="site-menu" role="menu">
                {secondary.map((l) => link(l, "site-menu-item"))}
              </div>
            ) : null}
          </div>
        </nav>
        <span className="spacer" />
        <button className="site-search" onClick={() => setPaletteOpen(true)} title="Command palette">
          <Icon name="search" size={14} />
          <span className="site-search-l">Search or jump to</span>
          <span className="kbd">{mac ? "⌘K" : "Ctrl K"}</span>
        </button>
        <button className="site-icon" onClick={cycleTheme} title="Switch theme" aria-label="Switch theme">
          <Icon name="contrast" />
        </button>
        <Link
          className="site-icon"
          href="/app/settings"
          title="Settings"
          aria-label="Settings"
          aria-current={path.startsWith("/app/settings") ? "page" : undefined}
        >
          <Icon name="gear" />
        </Link>
        <button className="site-icon site-burger" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menu" aria-expanded={menuOpen}>
          <Icon name="menu" />
        </button>
      </div>
      {menuOpen ? (
        <nav className="site-drawer" aria-label="All pages">
          {[...primary, ...secondary, { href: "/app/settings", label: "Settings" }].map((l) => link(l, "site-drawer-item"))}
        </nav>
      ) : null}
    </header>
  );
}
