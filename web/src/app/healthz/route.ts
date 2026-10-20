// Liveness of the API behind this web app, read at request time like
// every /api call (see src/app/api/[...path]/route.ts), so no address
// is baked into the build.
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const origin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";
  const commit = process.env.ACE_BUILD_SHA ?? process.env.NEXT_PUBLIC_ACE_BUILD_SHA ?? "unversioned";
  try {
    const res = await fetch(`${origin}/healthz`, { cache: "no-store" });
    const text = await res.text();
    let api: unknown = text;
    try {
      api = JSON.parse(text);
    } catch {}
    return Response.json({
      status: res.ok ? "ok" : "api_down",
      frontend: { commit },
      api,
    }, {
      status: res.status,
      headers: { "X-Ace-Frontend-Commit": commit },
    });
  } catch {
    return Response.json(
      { status: "api_down", frontend: { commit }, api: null },
      { status: 502, headers: { "X-Ace-Frontend-Commit": commit } },
    );
  }
}
