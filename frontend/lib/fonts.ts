// Phông giao diện (mục 7.3-1): Be Vietnam Pro đủ dấu tiếng Việt; JetBrains Mono cho code (Monaco, khối <pre>).
// next/font tự lưu phông cùng trang, trình duyệt không gọi Google khi xem.

import { Be_Vietnam_Pro, JetBrains_Mono } from "next/font/google";

export const sans = Be_Vietnam_Pro({
  subsets: ["vietnamese", "latin"],
  weight: ["200", "300", "400", "500", "600", "700", "800"],
  display: "swap",
  variable: "--font-sans",
});

export const mono = JetBrains_Mono({
  subsets: ["vietnamese", "latin"],
  weight: ["400", "600"],
  display: "swap",
  variable: "--font-mono",
});
