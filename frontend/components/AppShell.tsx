"use client";

import type { CSSProperties, ReactNode } from "react";
import { usePathname } from "next/navigation";

import { AppSidebar } from "@/components/app-sidebar";
import { SiteHeader } from "@/components/site-header";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isDashboard = pathname === "/dashboard";

  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 64)",
          "--header-height": "calc(var(--spacing) * 14)",
        } as CSSProperties
      }
    >
      <a href="#main" className="skip-link">
        Bỏ qua tới nội dung
      </a>
      <AppSidebar />
      <SidebarInset>
        <SiteHeader />
        <main id="main" className={isDashboard ? "min-w-0 flex-1" : "content"}>
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
