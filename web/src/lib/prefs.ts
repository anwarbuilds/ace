import "server-only";

import { cookies, headers } from "next/headers";

export type Theme = "dark" | "light" | "system";

export interface Prefs {
  theme: Theme;
  /** The reader's IANA zone, from their browser; UTC until it is known. */
  tz: string;
}

function validZone(tz: string | undefined): string {
  if (!tz) return "UTC";
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: tz });
    return tz;
  } catch {
    return "UTC";
  }
}

export async function getPrefs(): Promise<Prefs> {
  const jar = await cookies();
  const raw = jar.get("ace_theme")?.value;
  const theme: Theme = raw === "light" || raw === "system" ? raw : "dark";
  return { theme, tz: validZone(jar.get("ace_tz")?.value) };
}

/** When the previous visit ended, as worked out by src/proxy.ts. */
export async function getPrevVisit(): Promise<Date | null> {
  const value = Number((await headers()).get("x-ace-prev-visit"));
  return value ? new Date(value) : null;
}
