import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // Agent turns stream for a while; keep the rewrite proxy from cutting
    // them off at the default 30 seconds.
    proxyTimeout: 120_000,
  },
  async rewrites() {
    const backendUrl =
      process.env.FASTAPI_BACKEND_URL;

    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
