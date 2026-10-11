import type { NextConfig } from "next";

// Triển khai Vercel + backend khác miền: đặt BACKEND_URL (và NEXT_PUBLIC_API_URL=/) TRƯỚC KHI build để trình duyệt chỉ gọi
// cùng miền với web; Next chuyển tiếp /api/v1/* sang backend nên cookie phiên là cookie cùng miền, không cần CORS.
// Không đặt BACKEND_URL thì không có rewrite nào (chạy máy/Docker như cũ).
const backendUrl = (process.env.BACKEND_URL || "").replace(/\/+$/, "").replace(/\/api\/v1$/, "");

const nextConfig: NextConfig = {
  // Bản chạy gọn cho Docker: .next/standalone/server.js (không cần node_modules đầy đủ).
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return backendUrl ? [{ source: "/api/v1/:path*", destination: `${backendUrl}/api/v1/:path*` }] : [];
  },
};

export default nextConfig;
