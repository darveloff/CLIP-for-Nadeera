import type { NextConfig } from "next";

const API = process.env.CLIPMARKET_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/backend/:path*", destination: `${API}/:path*` },
    ];
  },
};

export default nextConfig;
