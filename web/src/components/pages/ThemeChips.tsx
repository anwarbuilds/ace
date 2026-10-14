"use client";

import { THEME_LABEL, useApp, type ThemeChoice } from "@/components/shell/AppProvider";

export function ThemeChips() {
  const { theme, setTheme } = useApp();
  return (
    <div className="controls" style={{ paddingLeft: 0 }}>
      {(["dark", "light", "system"] as ThemeChoice[]).map((t) => (
        <button key={t} className={`chip${theme === t ? " on" : ""}`} aria-pressed={theme === t} onClick={() => setTheme(t)}>
          {THEME_LABEL[t]}
        </button>
      ))}
    </div>
  );
}
