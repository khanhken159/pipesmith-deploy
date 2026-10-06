"use client";

import { Activity, CircleCheck, Clock3, ListChecks } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { RunRecord } from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const NEEDS_ACTION = new Set(["waiting_clarification", "waiting_plan_review", "waiting_rescue", "waiting_review"]);

function StatCard({
  title,
  value,
  description,
  icon: Icon,
}: {
  title: string;
  value: number;
  description: string;
  icon: LucideIcon;
}) {
  return (
    <Card className="@container/card">
      <CardHeader className="grid-cols-[1fr_auto]">
        <CardDescription>{title}</CardDescription>
        <Icon className="size-4 text-muted-foreground" />
        <CardTitle className="text-3xl tabular-nums">{value.toLocaleString("vi-VN")}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 text-xs text-muted-foreground">{description}</CardContent>
    </Card>
  );
}

export function SectionCards({ runs, loading }: { runs: RunRecord[]; loading: boolean }) {
  const waiting = runs.filter((run) => NEEDS_ACTION.has(run.status)).length;
  const completed = runs.filter((run) => run.status === "approved").length;
  const running = runs.filter((run) => run.status === "running").length;
  const items = [
    { title: "Tổng lần chạy", value: runs.length, description: "Trong danh sách 50 lần chạy gần nhất", icon: Activity },
    { title: "Đã hoàn tất", value: completed, description: "Pipeline đã được duyệt", icon: CircleCheck },
    { title: "Cần bạn xử lý", value: waiting, description: "Đang chờ làm rõ hoặc duyệt", icon: ListChecks },
    { title: "Đang chạy", value: running, description: "Agent đang xử lý trong sandbox", icon: Clock3 },
  ];
  return (
    <div className="grid grid-cols-1 gap-4 px-4 sm:grid-cols-2 lg:grid-cols-4 lg:px-6">
      {items.map((item) => (
        <StatCard key={item.title} {...item} value={loading && runs.length === 0 ? 0 : item.value} />
      ))}
    </div>
  );
}
