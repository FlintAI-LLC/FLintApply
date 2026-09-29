import type { NextConfig } from "next";
import { securityResponseHeaders } from "./lib/securityHeaders";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["localhost", "127.0.0.1", "192.168.88.24", "192.168.88.31"],
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityResponseHeaders(),
      },
    ];
  },
};

export default nextConfig;
