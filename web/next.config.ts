import type { NextConfig } from "next";

// The FastAPI backend. Server components fetch it directly; the browser
// calls /api/... on this origin and src/app/api/[...path]/route.ts
// forwards it, reading API_ORIGIN when the server starts rather than
// when the app was built. No CORS is needed.
const API_ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

// No nonces: every page is rendered per request anyway, but nonces would
// force dynamic rendering on purpose and buy little for a one-person app
// with no third-party script. The guide's "without nonces" policy, minus
// upgrade-insecure-requests, which would break plain http://localhost.
// HTTPS and HSTS belong to the proxy in front (deploy/Caddyfile).
const isDev = process.env.NODE_ENV === "development";
const CSP = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data:",
  "font-src 'self'",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const SECURITY_HEADERS = [
  { key: "Content-Security-Policy", value: CSP },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "same-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  poweredByHeader: false,
  devIndicators: false,
  // Old names keep working: bookmarks and muscle memory survive the
  // rename. Temporary (307) until the names are settled.
  async redirects() {
    return [
      { source: "/app/queue", destination: "/app/opportunities", permanent: false },
      { source: "/app/activity", destination: "/app/pulls", permanent: false },
      { source: "/app/dashboard", destination: "/app/analytics", permanent: false },
      { source: "/app/applied", destination: "/app/applications", permanent: false },
      { source: "/app/resume", destination: "/app/resume-studio", permanent: false },
      { source: "/app/skills", destination: "/app/insights/skills", permanent: false },
    ];
  },
  async rewrites() {
    return [
      { source: "/healthz", destination: `${API_ORIGIN}/healthz` },
    ];
  },
};

export default nextConfig;
