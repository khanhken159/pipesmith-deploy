"use client";

import * as React from "react";
import { Area, AreaChart, CartesianGrid, XAxis } from "recharts";

import type { RunRecord } from "@/lib/types";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useIsMobile } from "@/hooks/use-mobile";

type Range = "7d" | "30d" | "90d";

const chartConfig = {
  created: { label: "Yêu cầu mới", color: "var(--chart-1)" },
  approved: { label: "Đã duyệt", color: "var(--chart-2)" },
} satisfies ChartConfig;

function dayKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return year + "-" + month + "-" + day;
}

export function ChartAreaInteractive({ runs }: { runs: RunRecord[] }) {
  const isMobile = useIsMobile();
  const [selectedRange, setSelectedRange] = React.useState<Range | null>(null);
  const range = selectedRange ?? (isMobile ? "7d" : "30d");

  const chartData = React.useMemo(() => {
    const count = Number.parseInt(range, 10);
    const days: { date: string; created: number; approved: number }[] = [];
    const today = new Date();
    const start = new Date(today);
    start.setDate(today.getDate() - count + 1);
    start.setHours(0, 0, 0, 0);

    for (let offset = 0; offset < count; offset += 1) {
      const date = new Date(start);
      date.setDate(start.getDate() + offset);
      days.push({ date: dayKey(date), created: 0, approved: 0 });
    }

    const byDate = new Map(days.map((day) => [day.date, day]));
    for (const run of runs) {
      const createdAt = new Date(run.created_at);
      if (Number.isNaN(createdAt.getTime())) continue;
      const bucket = byDate.get(dayKey(createdAt));
      if (!bucket) continue;
      bucket.created += 1;
      if (run.status === "approved") bucket.approved += 1;
    }

    return days;
  }, [range, runs]);

  const formatDay = (value: string) =>
    new Date(value + "T12:00:00").toLocaleDateString("vi-VN", { day: "numeric", month: "short" });

  return (
    <Card className="@container/card">
      <CardHeader className="border-b">
        <CardTitle>Lượt chạy pipeline</CardTitle>
        <CardDescription>Số yêu cầu được tạo và pipeline đã duyệt trong khoảng thời gian chọn</CardDescription>
        <CardAction>
          <ToggleGroup
            multiple={false}
            value={[range]}
            onValueChange={(value) => setSelectedRange((value[0] as Range | undefined) ?? "30d")}
            variant="outline"
            className="hidden *:data-[slot=toggle-group-item]:px-3! @[767px]/card:flex"
          >
            <ToggleGroupItem value="90d">90 ngày</ToggleGroupItem>
            <ToggleGroupItem value="30d">30 ngày</ToggleGroupItem>
            <ToggleGroupItem value="7d">7 ngày</ToggleGroupItem>
          </ToggleGroup>
          <Select value={range} onValueChange={(value) => value && setSelectedRange(value as Range)}>
            <SelectTrigger className="w-28 @[767px]/card:hidden" size="sm" aria-label="Chọn khoảng thời gian">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="90d">90 ngày</SelectItem>
              <SelectItem value="30d">30 ngày</SelectItem>
              <SelectItem value="7d">7 ngày</SelectItem>
            </SelectContent>
          </Select>
        </CardAction>
      </CardHeader>
      <CardContent className="px-2 pt-5 sm:px-6">
        <ChartContainer config={chartConfig} className="aspect-auto h-[260px] w-full">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="fillCreated" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-created)" stopOpacity={0.55} />
                <stop offset="95%" stopColor="var(--color-created)" stopOpacity={0.03} />
              </linearGradient>
              <linearGradient id="fillApproved" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-approved)" stopOpacity={0.8} />
                <stop offset="95%" stopColor="var(--color-approved)" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={28}
              tickFormatter={formatDay}
            />
            <ChartTooltip
              cursor={false}
              content={<ChartTooltipContent labelFormatter={(value) => formatDay(String(value))} />}
            />
            <Area
              dataKey="created"
              type="monotone"
              stroke="var(--color-created)"
              fill="url(#fillCreated)"
              strokeWidth={2}
            />
            <Area
              dataKey="approved"
              type="monotone"
              stroke="var(--color-approved)"
              fill="url(#fillApproved)"
              strokeWidth={2}
            />
          </AreaChart>
        </ChartContainer>
        <p className="mt-3 px-4 text-xs text-muted-foreground">
          Biểu đồ tính từ 50 lần chạy gần nhất được tải từ ứng dụng.
        </p>
      </CardContent>
    </Card>
  );
}
