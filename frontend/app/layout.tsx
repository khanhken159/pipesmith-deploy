import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppProvider } from "@/components/AppContext";
import { AppShell } from "@/components/AppShell";
import { mono, sans } from "@/lib/fonts";

import "../styles/tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "P-113 Pipeline Agent",
  description:
    "Agent sinh và tối ưu pipeline ELT/ETL (dbt + Airflow), chạy thử trong sandbox DuckDB, DE duyệt trước khi merge.",
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
