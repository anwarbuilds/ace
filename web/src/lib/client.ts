// Browser-side calls. They go to /api on this origin, which
// next.config.ts rewrites to the FastAPI backend.

import type { MarkResult } from "./types";

export async function getJson<T>(path: string, params?: URLSearchParams): Promise<T> {
  const q = params?.toString();
  const res = await fetch(`${path}${q ? `?${q}` : ""}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return (await res.json()) as T;
}

export async function sendJson<T>(method: "PUT" | "POST", path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return (await res.json()) as T;
}

export interface MarkBody {
  saved?: boolean;
  review_state?: "reviewed" | "dismissed";
  clear_review?: boolean;
  applied?: boolean;
  application_status?: string;
  status_note?: string;
}

export function putMark(id: number, body: MarkBody): Promise<MarkResult> {
  return sendJson<MarkResult>("PUT", `/api/marks/${id}`, body);
}

export function setCookie(name: string, value: string): void {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=31536000; samesite=lax`;
}
