"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, AlertTriangle, Boxes, ClipboardList, Plus, Workflow } from "lucide-react";
import type { ComponentProps, ComponentType } from "react";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

const mainLinks = [
  { title: "Tổng quan", href: "/dashboard", icon: Activity },
  { title: "Tạo yêu cầu", href: "/dashboard#new-request", icon: Plus },
  { title: "Lần chạy gần đây", href: "/dashboard#recent-runs", icon: ClipboardList },
];

const manageLinks = [
  { title: "Dữ liệu nguồn", href: "/catalog", icon: Boxes },
  { title: "Sổ lỗi", href: "/errors", icon: AlertTriangle },
];

function SidebarLinks({
  items,
}: {
  items: ReadonlyArray<{ title: string; href: string; icon: ComponentType<{ className?: string }> }>;
}) {
  const pathname = usePathname();
  return (
    <SidebarMenu>
      {items.map((item) => {
        const Icon = item.icon;
        const active =
          pathname === item.href ||
          (item.href === "/dashboard" && pathname === "/") ||
          (item.href === "/dashboard#recent-runs" && pathname.startsWith("/runs"));
        return (
          <SidebarMenuItem key={item.href}>
            <SidebarMenuButton render={<Link href={item.href} />} isActive={active} tooltip={item.title}>
              <Icon />
              <span>{item.title}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        );
      })}
    </SidebarMenu>
  );
}

export function AppSidebar({ ...props }: ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader className="p-4">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton render={<Link href="/dashboard" />} className="h-auto py-2">
              <span className="grid size-9 place-items-center rounded-xl bg-primary text-base font-bold text-primary-foreground">
                <Workflow className="size-5" />
              </span>
              <span className="grid gap-0.5 text-left">
                <span className="text-base font-semibold">P-113</span>
                <span className="text-xs text-muted-foreground">Pipeline Agent</span>
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent className="px-2">
        <SidebarGroup>
          <SidebarGroupLabel>Không gian làm việc</SidebarGroupLabel>
          <SidebarLinks items={mainLinks} />
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>Quản lý dữ liệu</SidebarGroupLabel>
          <SidebarLinks items={manageLinks} />
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-4">
        <div className="rounded-xl border bg-background p-3 text-xs">
          <div className="mb-1 flex items-center gap-2 font-medium">
            <span className="size-2 rounded-full bg-emerald-500" />
            Sandbox an toàn
          </div>
          <p className="m-0 text-muted-foreground">Chạy thử bằng DuckDB, không ghi vào production.</p>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
