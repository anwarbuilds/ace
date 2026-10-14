import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// "New since your last visit" needs to know when the last visit was,
// before the page renders. A visit is a run of requests with no gap of
// 30 minutes or more; the previous visit is when the last such run
// ended. Kept in cookies so the server can read it, and computed here
// so the page sees the answer for this request, not the next one.

const GAP_MS = 30 * 60 * 1000;
const YEAR = 60 * 60 * 24 * 365;

export function proxy(request: NextRequest) {
  const now = Date.now();
  const current = Number(request.cookies.get("ace_visit")?.value) || 0;
  let previous = Number(request.cookies.get("ace_prev")?.value) || 0;

  if (current && now - current >= GAP_MS) previous = current;

  const headers = new Headers(request.headers);
  if (previous) headers.set("x-ace-prev-visit", String(previous));
  else headers.delete("x-ace-prev-visit");

  const response = NextResponse.next({ request: { headers } });
  const opts = { path: "/", maxAge: YEAR, sameSite: "lax" as const };
  response.cookies.set("ace_visit", String(now), opts);
  if (previous) response.cookies.set("ace_prev", String(previous), opts);
  return response;
}

export const config = {
  matcher: "/app/:path*",
};
