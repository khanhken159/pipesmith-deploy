"use client";

import Link from "next/link";
import { ArrowRight, CircleAlert, Clock3, ExternalLink, ShieldCheck } from "lucide-react";

import { CreateRunForm } from "@/components/CreateRunForm";
import { ChartAreaInteractive } from "@/components/chart-area-interactive";
import { SectionCards } from "@/components/section-cards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatPct, formatTime, formatUsd } from "@/lib/format";
import type { RunRecord, RunStatus } from "@/lib/types";
import { usePoll } from "@/lib/usePoll";

const NEEDS_ACTION: RunStatus[] = ["waiting_clarification", "waiting_plan_review", "waiting_rescue", "waiting_review"];

const STATUS_LABEL: Record<RunStatus, string> = {
  running: "Đang chạy",
  waiting_clarification: "Cần làm rõ",
  waiting_plan_review: "Chờ duyệt kế hoạch",
  waiting_rescue: "Cần xử lý",
  waiting_review: "Chờ duyệt code",
  approved: "Hoàn tất",
  failed: "Thất bại",
};

function statusStyle(status: RunStatus) {
  if (status === "approved") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  if (status === "failed") return "border-destructive/30 bg-destructive/10 text-destructive";
  if (NEEDS_ACTION.includes(status)) return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
  return "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300";
}

function runHref(run: RunRecord) {
  return run.status === "waiting_review" ? "/runs/" + run.id + "/review" : "/runs/" + run.id;
}

function RunTable({ runs }: { runs: RunRecord[] }) {
  const sortedRuns = [...runs].sort((left, right) => right.updated_at.localeCompare(left.updated_at));

  if (sortedRuns.length === 0) {
    return (
      <div className="grid min-h-40 place-items-center px-6 py-10 text-center text-sm text-muted-foreground">
        <div>
          <p className="mb-1 font-medium text-foreground">Chưa có lần chạy nào</p>
          <p className="m-0">Tạo yêu cầu đầu tiên ở phía trên để bắt đầu.</p>
        </div>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="pl-5">Yêu cầu</TableHead>
          <TableHead>Trạng thái</TableHead>
          <TableHead>Bảng đích</TableHead>
          <TableHead>Tối ưu</TableHead>
          <TableHead className="text-right">Chi phí</TableHead>
          <TableHead className="pr-5 text-right">Cập nhật</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sortedRuns.slice(0, 8).map((run) => (
          <TableRow key={run.id}>
            <TableCell className="max-w-[360px] pl-5">
              <Link
                href={runHref(run)}
                className="line-clamp-2 font-medium text-foreground hover:text-primary"
                title={run.request_text}
              >
                {run.request_text}
              </Link>
              <span className="mt-1 block truncate font-mono text-xs text-muted-foreground">
                {run.id} · {run.requester}
              </span>
            </TableCell>
            <TableCell>
              <Badge variant="outline" className={statusStyle(run.status)}>
                {STATUS_LABEL[run.status]}
              </Badge>
            </TableCell>
            <TableCell className="max-w-40 truncate font-mono text-xs">{run.summary.target || "—"}</TableCell>
            <TableCell className="tabular-nums">
              {run.summary.optimization === "applied" ? "+" + formatPct(run.summary.improvement_pct) : "—"}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {run.summary.simulated ? "Mô phỏng" : formatUsd(run.summary.cost_usd)}
            </TableCell>
            <TableCell className="pr-5 text-right text-xs text-muted-foreground">
              {formatTime(run.updated_at)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function NeedsAttention({ runs }: { runs: RunRecord[] }) {
  const attention = [...runs]
    .filter((run) => NEEDS_ACTION.includes(run.status))
    .sort((left, right) => right.updated_at.localeCompare(left.updated_at))
    .slice(0, 4);

  return (
    <Card className="h-full">
      <CardHeader className="border-b">
        <div className="flex items-center gap-2">
          <Clock3 className="size-4 text-amber-500" />
          <CardTitle>Cần bạn xử lý</CardTitle>
        </div>
        <CardDescription>Các pipeline đang chờ làm rõ hoặc duyệt</CardDescription>
        <CardAction>
          <Badge variant="secondary">{attention.length}</Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="pt-2">
        {attention.length === 0 ? (
          <div className="flex min-h-36 items-center gap-3 text-sm text-muted-foreground">
            <ShieldCheck className="size-5 text-emerald-600" />
            Hiện không có pipeline nào chờ bạn xử lý.
          </div>
        ) : (
          <ul className="m-0 divide-y p-0">
            {attention.map((run) => (
              <li key={run.id} className="list-none py-3 first:pt-2 last:pb-1">
                <Link href={runHref(run)} className="group flex items-start gap-3 text-foreground hover:no-underline">
                  <CircleAlert className="mt-0.5 size-4 shrink-0 text-amber-500" />
                  <span className="min-w-0 flex-1">
                    <span className="line-clamp-2 block text-sm font-medium group-hover:text-primary">
                      {run.request_text}
                    </span>
                    <span className="mt-1 block text-xs text-muted-foreground">
                      {STATUS_LABEL[run.status]} · {formatTime(run.updated_at)}
                    </span>
                  </span>
                  <ArrowRight className="mt-1 size-4 shrink-0 text-muted-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function DashboardContent() {
  const { data, error, loading, refresh } = usePoll<RunRecord[]>("/runs?limit=50", 5000);
  const runs = data ?? [];
  const waitingCount = runs.filter((run) => NEEDS_ACTION.includes(run.status)).length;

  return (
    <div id="dashboard-root" className="@container/main flex min-w-0 flex-1 flex-col">
      <div className="flex flex-col gap-5 px-4 py-6 lg:gap-6 lg:px-8 lg:py-8">
        <div className="flex flex-wrap items-end justify-between gap-3 px-1">
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
              P-113 · Pipeline Agent
            </p>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Bảng điều khiển</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              Tạo pipeline, theo dõi agent xử lý và duyệt kết quả chạy trong sandbox.
            </p>
          </div>
          <Badge variant="outline" className="gap-1.5 px-2.5 py-1">
            <span className="size-2 rounded-full bg-emerald-500" />
            DuckDB sandbox
          </Badge>
        </div>

        <Card id="new-request" className="scroll-mt-24">
          <CardHeader className="border-b">
            <CardTitle>Yêu cầu mới</CardTitle>
            <CardDescription>Mô tả bảng và chỉ số cần tạo; agent sẽ hỏi lại nếu dữ liệu chưa đủ rõ.</CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            <CreateRunForm />
          </CardContent>
        </Card>

        {error && (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          >
            <span>Không tải được danh sách lần chạy: {error}</span>
            <Button variant="outline" size="sm" onClick={() => void refresh()}>
              Thử lại
            </Button>
          </div>
        )}

        <SectionCards runs={runs} loading={loading} />

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.65fr)_minmax(280px,1fr)]">
          <ChartAreaInteractive runs={runs} />
          <NeedsAttention runs={runs} />
        </div>

        <Card id="recent-runs" className="scroll-mt-24">
          <CardHeader className="border-b">
            <div>
              <CardTitle>Lần chạy gần đây</CardTitle>
              <CardDescription className="mt-1">
                Theo dõi trạng thái, bảng đích và chi phí của từng yêu cầu.
              </CardDescription>
            </div>
            <CardAction className="flex items-center gap-2">
              {waitingCount > 0 && (
                <Badge variant="secondary" className="hidden sm:inline-flex">
                  {waitingCount} cần xử lý
                </Badge>
              )}
              <Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}>
                Làm mới
              </Button>
            </CardAction>
          </CardHeader>
          {loading && !data ? (
            <CardContent className="py-10 text-center text-sm text-muted-foreground">Đang tải lần chạy…</CardContent>
          ) : (
            <RunTable runs={runs} />
          )}
          <div className="flex justify-end border-t px-5 py-3">
            <Link
              href="#recent-runs"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              Hiển thị tối đa 8 lần chạy
              <ExternalLink className="size-3" />
            </Link>
          </div>
        </Card>

        <p className="m-0 px-1 text-xs text-muted-foreground">
          Kết quả được tạo và kiểm tra trong sandbox; agent không tự đẩy code lên production.
        </p>
      </div>
    </div>
  );
}
