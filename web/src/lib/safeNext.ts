/** Where to go after signing in. Only a path on this site: "//host" and
 *  "/\host" are other sites to a browser, so they fall back to Pulls. */
export function safeNext(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return "/app/pulls";
  return value;
}
