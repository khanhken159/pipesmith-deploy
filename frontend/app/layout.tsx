import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppProvider } from "@/components/AppContext";
import { AppShell } from "@/components/AppShell";
import { mono, sans } from "@/lib/fonts";

import "../styles/tokens.css";
import "./globals.css";
import "./marketing.css";

export const metadata: Metadata = {
  title: "PipeSmith — AI Data Pipeline Workspace",
  description: "Từ yêu cầu ngôn ngữ tự nhiên đến pipeline dữ liệu có kiểm tra và phê duyệt.",
};

// Áp dụng giao diện sáng/tối đã lưu trước khi vẽ trang (tránh nháy màu).
const THEME_SCRIPT = `try{var t=localStorage.getItem("p113.theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="vi" className={`${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>
        <AppProvider>
          <AppShell>{children}</AppShell>
        </AppProvider>
      </body>
    </html>
  );
}
