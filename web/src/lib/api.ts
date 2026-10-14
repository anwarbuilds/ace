import "server-only";

// Server-side reads from the FastAPI backend. Every response describes
// rows the scheduler and the user are both changing, so nothing here is
// cached: a stale queue is simply wrong, and the reader cannot tell.

const API_ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public path: string,
  ) {
    super(`ace api ${path} answered ${status}`);
  }
}

export async function apiGet<T>(path: string, params?: URLSearchParams | Record<string, string>): Promise<T> {
  const query = params ? new URLSearchParams(params).toString() : "";
  const res = await fetch(`${API_ORIGIN}${path}${query ? `?${query}` : ""}`, { cache: "no-store" });
  if (!res.ok) throw new ApiError(res.status, path);
  return (await res.json()) as T;
}

/** Like apiGet, but a failure becomes the fallback instead of an error page. */
export async function apiGetOr<T>(
  path: string,
  fallback: T,
  params?: URLSearchParams | Record<string, string>,
): Promise<T> {
  try {
    return await apiGet<T>(path, params);
  } catch {
    return fallback;
  }
}
