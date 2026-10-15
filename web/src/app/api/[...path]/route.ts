import type { NextRequest } from "next/server";

// The browser calls /api/* on this origin and this handler forwards it to
// FastAPI. A route handler rather than a next.config rewrite because
// rewrites are fixed at build time: a production build made without
// API_ORIGIN sent every browser request to port 8000 for good. Here the
// address is read on each request, so `API_ORIGIN=... npm start` is enough.

export const dynamic = "force-dynamic";

const HOP_BY_HOP = ["connection", "keep-alive", "transfer-encoding", "content-length", "content-encoding", "host"];

async function forward(request: NextRequest): Promise<Response> {
  const origin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";
  const url = new URL(request.url);
  const headers = new Headers(request.headers);
  for (const h of HOP_BY_HOP) headers.delete(h);
  headers.set("x-forwarded-host", request.headers.get("host") ?? "");

  let upstream: Response;
  try {
    upstream = await fetch(`${origin}${url.pathname}${url.search}`, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { detail: { reason: "api_down", message: `ace's API at ${origin} is not answering. Start it, then retry.` } },
      { status: 502 },
    );
  }

  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.includes(key) && key !== "set-cookie") out.set(key, value);
  });
  // Several cookies may be set at once (session and CSRF); keep each.
  for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
