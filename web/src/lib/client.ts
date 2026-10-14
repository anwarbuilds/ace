// Browser-side calls. They go to /api on this origin, which
// next.config.ts rewrites to the FastAPI backend.

import type { MarkResult } from "./types";

/** The CSRF token FastAPI set at sign-in. Readable on purpose: copying it
 *  into a header is what another site's page cannot do. */
export function csrfHeader(): Record<string, string> {
  const match = document.cookie.match(/(?:^|;\s*)ace_csrf=([^;]+)/);
  return match ? { "X-CSRF-Token": decodeURIComponent(match[1]) } : {};
}

/** A signed-out answer anywhere sends the reader to sign in. */
function signedOut(res: Response): boolean {
  if (res.status !== 401) return false;
  // A full load on purpose: the session cookie changed, so nothing
  // rendered under the old one may be reused.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
  return true;
}

export class RequestError extends Error {
  constructor(
    public status: number,
    public reason: string,
    message: string,
  ) {
    super(message);
  }
}

async function failure(path: string, res: Response): Promise<RequestError> {
  let reason = "";
  let message = `${path} ${res.status}`;
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (detail && typeof detail === "object") {
      reason = String(detail.reason ?? "");
      message = String(detail.message ?? message);
    } else if (typeof detail === "string") {
      message = detail;
    }
  } catch {
    // Not JSON; the status line is all there is.
  }
  return new RequestError(res.status, reason, message);
}

export async function getJson<T>(path: string, params?: URLSearchParams): Promise<T> {
  const q = params?.toString();
  const res = await fetch(`${path}${q ? `?${q}` : ""}`, { cache: "no-store" });
  signedOut(res);
  if (!res.ok) throw await failure(path, res);
  return (await res.json()) as T;
}

export async function sendJson<T>(
  method: "PUT" | "POST" | "DELETE",
  path: string,
  body?: unknown,
  opts: { redirectOn401?: boolean } = {},
): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", ...csrfHeader() },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (opts.redirectOn401 !== false) signedOut(res);
  if (!res.ok) throw await failure(path, res);
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
  document.cookie = `${name}=${encodeURIComponent(value).replace(/%2F/g, "/")}; path=/; max-age=31536000; samesite=lax`;
}
