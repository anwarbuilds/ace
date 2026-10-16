import "server-only";

import { cookies, headers } from "next/headers";
import { redirect, unstable_rethrow } from "next/navigation";

// Server-side reads from the FastAPI backend. Every response describes
// rows the scheduler and the user are both changing, so nothing here is
// cached: a stale queue is simply wrong, and the reader cannot tell.
//
// The owner's session cookie is passed through, so FastAPI makes the one
// decision about who may read; a 401 sends the reader to sign in.

const API_ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public path: string,
  ) {
    super(`ace api ${path} answered ${status}`);
  }
}

async function sessionHeaders(): Promise<HeadersInit> {
  const session = (await cookies()).get("ace_session")?.value;
  return session ? { cookie: `ace_session=${session}` } : {};
}

/** The sign-in page, with the page asked for as where to return. The
 *  path comes from proxy.ts, which sees every /app request. */
export async function signInPath(): Promise<string> {
  const asked = (await headers()).get("x-ace-path");
  return asked ? `/login?next=${encodeURIComponent(asked)}` : "/login";
}

export async function apiGet<T>(path: string, params?: URLSearchParams | Record<string, string>): Promise<T> {
  const query = params ? new URLSearchParams(params).toString() : "";
  const res = await fetch(`${API_ORIGIN}${path}${query ? `?${query}` : ""}`, {
    cache: "no-store",
    headers: await sessionHeaders(),
  });
  if (res.status === 401) redirect(await signInPath());
  if (!res.ok) throw new ApiError(res.status, path);
  return (await res.json()) as T;
}

/** Like apiGet, but a failure becomes the fallback instead of an error page.
 *  Signing out is not a failure: the redirect to /login still happens. */
export async function apiGetOr<T>(
  path: string,
  fallback: T,
  params?: URLSearchParams | Record<string, string>,
): Promise<T> {
  try {
    return await apiGet<T>(path, params);
  } catch (err) {
    unstable_rethrow(err);
    return fallback;
  }
}

export interface AuthStatus {
  auth: "required" | "disabled";
  owner_exists: boolean;
  signed_in: boolean;
  kind: "session" | "token" | "local" | null;
  email: string | null;
  reset_by_email: boolean;
  google_sign_in: boolean;
  setup_allowed: boolean;
  setup_needs_token: boolean;
}

/** Never redirects: the sign-in page itself needs this. */
export async function authStatus(): Promise<AuthStatus | null> {
  try {
    const res = await fetch(`${API_ORIGIN}/api/auth/status`, {
      cache: "no-store",
      headers: await sessionHeaders(),
    });
    return res.ok ? ((await res.json()) as AuthStatus) : null;
  } catch {
    return null;
  }
}
