// Liveness of the API behind this web app, read at request time like
// every /api call (see src/app/api/[...path]/route.ts), so no address
// is baked into the build.
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const origin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";
  try {
    const res = await fetch(`${origin}/healthz`, { cache: "no-store" });
    return new Response(await res.text(), {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json({ status: "api_down" }, { status: 502 });
  }
}
