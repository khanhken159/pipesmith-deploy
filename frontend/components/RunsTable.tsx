"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { formatPct, formatTime, formatUsd } from "@/lib/format";
import type { RunRecord } from "@/lib/types";

import { useApp } from "./AppContext";
import { NEEDS_ACTION, runHref } from "./NotificationBell";
import { StatusPill } from "./StatusPill";
import { Card, Empty, ErrorBox, Loading } from "./ui";

function RunRow({ run }: { run: RunRecord }) {
  const router = useRouter();
  const href = runHref(run);
  return (
    <tr className="clickable" onClick={() => router.push(href)}>
      <td>
        <Link href={href} className="truncate" title={run.request_text} onClick={(e) => e.stopPropagation()}>
          {run.request_text}
        </Link>
        <small className="muted mono">
          {run.id} · {run.requester}
        </small>
      </td>
      <td>
        <StatusPill status={run.status} />
      </td>
      <td className="mono">{run.summary.target ?? "—"}</td>
      <td>{run.summary.optimization === "applied" ? `+${formatPct(run.summary.improvement_pct)}` : "—"}</td>
      <td className="num">{run.summary.simulated ? "mô phỏng" : formatUsd(run.summary.cost_usd)}</td>
      <td className="muted small">{formatTime(run.updated_at)}</td>
    </tr>
  );
}

export function RunsTable() {
  const { runs: data, runsError: error, refreshRuns: refresh } = useApp();
  const loading = !data && !error;
  const waiting = data?.filter((r) => NEEDS_ACTION.includes(r.status)).length ?? 0;
  return (
    <Card
      title="Lần chạy gần đây"
      actions={waiting > 0 && <span className="badge warn">{waiting} lần chạy cần bạn xử lý</span>}
    >
      {error && <ErrorBox message={error} onRetry={refresh} />}
      {loading && !data && <Loading text="Đang tải danh sách lần chạy…" />}
      {data && data.length === 0 && <Empty>Chưa có lần chạy nào. Hãy mô tả pipeline bạn cần ở ô phía trên.</Empty>}
      {data && data.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Yêu cầu</th>
                <th>Trạng thái</th>
                <th>Bảng đích</th>
                <th>Tối ưu</th>
                <th className="num">Chi phí LLM</th>
                <th>Cập nhật</th>
              </tr>
            </thead>
            <tbody>
              {data.map((run) => (
                <RunRow key={run.id} run={run} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
