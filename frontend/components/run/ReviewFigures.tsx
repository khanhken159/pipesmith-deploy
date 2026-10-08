"use client";

// Màn duyệt — số liệu cho người duyệt (CLAUDE.md mục 7.6). Chỉ hiện số đã đo; chưa đo thì ghi "Chưa đo".

import { formatNumber, formatPct, formatUsd } from "@/lib/format";
import type { Optimization, UsageRow } from "@/lib/types";

import { Card, Empty, Stat } from "../ui";
import { useRun } from "./RunContext";

const TASK_LABELS: Record<string, string> = {
  planner: "E1 Lập kế hoạch",
  codegen: "E3 Sinh code",
  testgen: "E3b Sinh test",
  optimizer: "E4 Tối ưu",
};

function NotMeasured() {
  return <span className="not-measured">Chưa đo</span>;
}

function change(before: number | null | undefined, after: number | null | undefined): string | null {
  if (before === null || before === undefined || after === null || after === undefined || before === 0) return null;
  return formatPct(Math.round(((before - after) / before) * 1000) / 10);
}

/** Bảng trước / sau tối ưu: thời gian, bộ nhớ, % cải thiện, quyết định. */
export function OptimizationFigures({ report }: { report: Optimization }) {
  const before = report.before ?? null;
  const after = report.after ?? null;
  const rows = [
    {
      label: "Thời gian (trung vị)",
      before: before ? `${formatNumber(before.median_ms)} ms` : null,
      after: after ? `${formatNumber(after.median_ms)} ms` : null,
      gain: report.improvement_pct != null ? formatPct(report.improvement_pct) : null,
    },
    {
      label: "Bộ nhớ đỉnh",
      before: before?.peak_memory_mb != null ? `${formatNumber(before.peak_memory_mb)} MB` : null,
      after: after?.peak_memory_mb != null ? `${formatNumber(after.peak_memory_mb)} MB` : null,
      gain: change(before?.peak_memory_mb, after?.peak_memory_mb),
    },
  ];
  const applied = report.decision === "applied";
  return (
    <Card
      title="Tối ưu: trước và sau"
      actions={
        report.decision && (
          <span className={applied ? "badge ok" : "badge muted"}>{applied ? "Đã áp dụng" : "Giữ nguyên"}</span>
        )
      }
    >
      {!report.original_sql ? (
        <Empty>Chưa tới bước tối ưu. Bước này chạy sau khi code qua sandbox.</Empty>
      ) : (
        <>
          <div className="table-wrap">
            <table className="figures">
              <thead>
                <tr>
                  <th>Chỉ số</th>
                  <th className="num">Trước</th>
                  <th className="num">Sau</th>
                  <th className="num">Cải thiện</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    <td className="num">{row.before ?? <NotMeasured />}</td>
                    <td className="num">{row.after ?? <NotMeasured />}</td>
                    <td className="num">{row.gain ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ marginTop: 10 }}>
            <strong>{applied ? "Áp dụng" : "Không áp dụng"}:</strong> {report.reason || "—"}
          </p>
          <small className="muted">
            Đo bằng code trên bộ dữ liệu lớn của sandbox DuckDB, lấy trung vị nhiều lần. Số liệu mang tính xu hướng,
            không phải số của kho thật.
          </small>
        </>
      )}
    </Card>
  );
}

/** Kiểm tăng trưởng 1x/10x/100x (V4). Chưa có số đo thì nói rõ, không vẽ biểu đồ giả. */
export function ScaleFigures() {
  return (
    <Card title="Tăng trưởng dữ liệu (1x / 10x / 100x)">
      <p className="not-measured" style={{ margin: 0 }}>
        Chưa đo.
      </p>
      <p className="muted small" style={{ marginTop: 6 }}>
        Bước kiểm tăng trưởng (V4) chưa chạy cho lần chạy này, nên chưa có biểu đồ thời gian và RAM theo kích thước dữ
        liệu, cũng chưa có kết quả chạy lại cùng ngày.
      </p>
    </Card>
  );
}

function totals(rows: UsageRow[]) {
  return rows.reduce(
    (sum, row) => ({
      calls: sum.calls + row.calls,
      input: sum.input + row.input_tokens,
      output: sum.output + row.output_tokens,
      cached: sum.cached + row.cached_tokens,
      cost: sum.cost + row.cost_usd,
      seconds: sum.seconds + row.seconds,
    }),
    { calls: 0, input: 0, output: 0, cached: 0, cost: 0, seconds: 0 },
  );
}

function StepTimes() {
  const { detail } = useRun();
  const events = detail?.events ?? [];
  if (events.length === 0)
    return <Empty>Thời gian từng bước: chưa đo trong phiên máy chủ này (nhật ký bước chỉ giữ trong bộ nhớ).</Empty>;
  return (
    <div className="table-wrap">
      <table className="figures">
        <thead>
          <tr>
            <th>Bước (theo thứ tự đã chạy)</th>
            <th className="num">Thời gian</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event, index) => (
            <tr key={`${event.node}-${index}`}>
              <td>{event.label}</td>
              <td className="num">{event.seconds.toFixed(1)} s</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Token, chi phí ước tính, thời gian gọi LLM theo node, tỉ lệ trúng cache. */
export function CostFigures() {
  const { detail } = useRun();
  const usage = detail?.usage;
  const rows = usage?.rows ?? [];
  const simulated = usage?.simulated ?? false;
  const sum = totals(rows);
  const show = (text: string) => (simulated ? "mô phỏng" : text);
  return (
    <Card title="Chi phí và thời gian">
      <div className="stack" style={{ gap: 12 }}>
        {simulated && (
          <div className="alert warn">
            <span>Chế độ mô phỏng: token và chi phí dưới đây không phải số thật.</span>
          </div>
        )}
        <div className="stats">
          <Stat label="Lượt gọi LLM" value={sum.calls} />
          <Stat label="Token" value={show(formatNumber(sum.input + sum.output))} />
          <Stat label="Chi phí ước tính" value={show(formatUsd(sum.cost))} hint="Theo bảng giá công khai" />
          <Stat
            label="Token trúng cache"
            value={
              usage?.cache_hit_rate == null ? <NotMeasured /> : formatPct(Math.round(usage.cache_hit_rate * 1000) / 10)
            }
            hint="Phần token đầu vào nhà cung cấp lấy từ cache"
          />
        </div>
        {rows.length === 0 ? (
          <Empty>Lần chạy chưa gọi LLM.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="figures">
              <thead>
                <tr>
                  <th>Bước gọi LLM</th>
                  <th className="num">Lượt</th>
                  <th className="num">Token vào</th>
                  <th className="num">Token ra</th>
                  <th className="num">Trúng cache</th>
                  <th className="num">Chi phí</th>
                  <th className="num">Thời gian</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.task}>
                    <td>{TASK_LABELS[row.task] ?? row.task}</td>
                    <td className="num">{row.calls}</td>
                    <td className="num">{show(formatNumber(row.input_tokens))}</td>
                    <td className="num">{show(formatNumber(row.output_tokens))}</td>
                    <td className="num">{show(formatNumber(row.cached_tokens))}</td>
                    <td className="num">{show(formatUsd(row.cost_usd))}</td>
                    <td className="num">{show(`${row.seconds.toFixed(1)} s`)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td>Tổng</td>
                  <td className="num">{sum.calls}</td>
                  <td className="num">{show(formatNumber(sum.input))}</td>
                  <td className="num">{show(formatNumber(sum.output))}</td>
                  <td className="num">{show(formatNumber(sum.cached))}</td>
                  <td className="num">{show(formatUsd(sum.cost))}</td>
                  <td className="num">{show(`${sum.seconds.toFixed(1)} s`)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
        <StepTimes />
      </div>
    </Card>
  );
}
