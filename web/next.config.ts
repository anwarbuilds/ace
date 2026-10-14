import type { NextConfig } from "next";

// The FastAPI backend. Server components fetch it directly; the browser
// reaches it through the rewrites below, so client code calls /api/...
// on its own origin and no CORS is needed.
const API_ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` },
      { source: "/healthz", destination: `${API_ORIGIN}/healthz` },
    ];
  },
};

export default nextConfig;
