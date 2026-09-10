import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Proxy API calls to FastAPI so the browser sees one origin.
  // Same origin means the session cookie flows automatically and there is
  // no CORS configuration to get wrong.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
