"use client";

import { NavIcon } from "@/components/shell/NavIcon";
import { setCookie } from "@/lib/client";

type VisibleTheme = "dark" | "light";

function currentTheme(): VisibleTheme {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit === "light" || explicit === "dark") return explicit;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function PublicThemeToggle() {
  function toggle() {
    const next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    setCookie("ace_theme", next);
  }

  return (
    <button className="wine-theme-toggle" type="button" onClick={toggle} aria-label="Switch Day or Night mode">
      <span className="theme-day"><NavIcon name="sun" size="sm" /> Day mode</span>
      <span className="theme-night"><NavIcon name="moon" size="sm" /> Night mode</span>
    </button>
  );
}
