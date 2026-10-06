import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Bản chạy gọn cho Docker: .next/standalone/server.js (không cần node_modules đầy đủ).
  output: "standalone",
  poweredByHeader: false,
};

export default nextConfig;
