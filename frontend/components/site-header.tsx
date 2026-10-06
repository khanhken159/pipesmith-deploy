"use client";

import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Topbar } from "@/components/Topbar";

export function SiteHeader() {
  return (
    <header className="dashboard-header flex min-h-14 shrink-0 items-center gap-3 border-b px-4 lg:px-6">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="h-5" />
      <div className="min-w-0">
        <p className="m-0 text-sm font-semibold">Không gian làm việc</p>
        <p className="m-0 hidden text-xs text-muted-foreground sm:block">
          Theo dõi pipeline ELT/ETL từ yêu cầu đến duyệt
        </p>
      </div>
      <div className="ml-auto min-w-0">
        <Topbar />
      </div>
    </header>
  );
}
