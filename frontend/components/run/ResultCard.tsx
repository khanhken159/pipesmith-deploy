"use client";

import { formatNumber, formatPct, formatUsd } from "@/lib/format";

import { Card, Empty, Stat } from "../ui";
import { useRun } from "./RunContext";

function Summary() {
  const { detail } = useRun();
  if (!detail) return null;
  const { summary } = detail.record;
  const simulated = summary.simulated;
  return (
    <div className="stats">
      <Stat label="Vòng sửa lỗi" value={summary.fix_attempts ?? 0} />
      <Stat label="Lần cứu hộ" value={summary.rescue_count ?? 0} />
      <Stat label="Vòng duyệt" value={summary.review_rounds ?? 0} />
      <Stat label="Lượt gọi LLM" value={summary.llm_calls ?? 0} />
      <Stat label="Token" value={simulated ? "mô phỏng" : formatNumber(summary.tokens)} />
      <Stat
        label="Chi phí"
        value={simulated ? "mô phỏng" : formatUsd(summary.cost_usd)}
        hint="Ước tính theo bảng giá"
      />
      <Stat
        label="Tối ưu"
        value={
          summary.optimization === "applied" ? `+${formatPct(summary.improvement_pct)}` : (summary.optimization ?? "—")
        }
      />
    </div>
  );
}

function SampleTable({ rows }: { rows: Record<string, string>[] }) {
  const columns = Object.keys(rows[0] ?? {});
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column} className="mono">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column} className="mono">
                  {row[column]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ResultCard() {
  const { detail } = useRun();
  if (!detail) return null;
  const sandbox = detail.sandbox ?? {};
  const codeNotes = detail.code_notes ?? [];
  return (
    <Card title="Kết quả chạy thử (sandbox)">
      <Summary />
      {!sandbox.passed && <Empty>Chưa có kết quả chạy thử đạt.</Empty>}
      {sandbox.passed && (
        <div className="stack" style={{ gap: 10, marginTop: 12 }}>
          <div className="row small">
            <span className="badge ok">
              {sandbox.models_ok}/{sandbox.models_total} model chạy được
            </span>
            <span className="badge ok">
              {sandbox.tests_ok}/{sandbox.tests_total} test đạt
            </span>
            <span className="muted">Bảng đích có {formatNumber(sandbox.target_rows)} dòng · vài dòng mẫu:</span>
          </div>
          {sandbox.sample && sandbox.sample.length > 0 && <SampleTable rows={sandbox.sample} />}
        </div>
      )}
      {codeNotes.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <h3>
            Agent mô tả code <span className="badge muted">LLM nói, chưa kiểm chứng</span>
          </h3>
          <ul className="claimed-list">
            {codeNotes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
