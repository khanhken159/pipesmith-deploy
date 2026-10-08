"use client";

import { formatNumber, formatPct, formatUsd } from "@/lib/format";
import type { Optimization } from "@/lib/types";

import { CodeDiff } from "../CodeDiff";
import { Card, Empty, PassMark, Stat } from "../ui";
import { useRun } from "./RunContext";

function Metrics({ report }: { report: Optimization }) {
  const applied = report.decision === "applied";
  return (
    <Card
      title="Kết luận (V3 đo bằng code)"
      actions={<span className={applied ? "badge ok" : "badge muted"}>{applied ? "Đã áp dụng" : "Giữ nguyên"}</span>}
    >
      <div className="stats">
        <Stat label="Trước (trung vị)" value={report.before ? `${formatNumber(report.before.median_ms)} ms` : "—"} />
        <Stat label="Sau (trung vị)" value={report.after ? `${formatNumber(report.after.median_ms)} ms` : "—"} />
        <Stat label="Cải thiện" value={formatPct(report.improvement_pct)} />
        <Stat label="Số lần thử" value={report.attempts ?? 0} />
        <Stat label="Chi phí LLM" value={formatUsd(report.llm_cost_usd)} />
      </div>
      <p style={{ marginTop: 12 }}>
        <strong>Lý do:</strong> {report.reason || "—"}
      </p>
      <small className="muted">
        Đo trên bộ dữ liệu large: 1 lần khởi động + {report.before?.runs ?? "N"} lần, lấy trung vị. Chỉ áp dụng khi kết
        quả giống hệt trên mọi bộ và đạt ngưỡng lợi ích.
      </small>
    </Card>
  );
}

function Equivalence({ report }: { report: Optimization }) {
  const checks = report.equivalence ?? [];
  return (
    <Card title="Đối chiếu kết quả hai chiều">
      {checks.length === 0 && <Empty>Không có bản viết lại nào cần đối chiếu.</Empty>}
      <ul className="measured-list">
        {checks.map((check) => (
          <li key={check.dataset}>
            <PassMark passed={check.equal} />
            <span>
              <strong className="mono">{check.dataset}</strong>: {check.detail}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Findings({ report }: { report: Optimization }) {
  return (
    <Card title="Dấu hiệu chậm (sqlglot + EXPLAIN)">
      {!report.findings?.length && <Empty>Không phát hiện dấu hiệu chậm.</Empty>}
      <ul className="plain">
        {report.findings?.map((finding) => (
          <li key={finding.rule}>
            <span className="mono">{finding.rule}</span>: {finding.message}
          </li>
        ))}
      </ul>
      {report.explanation && (
        <div style={{ marginTop: 12 }}>
          <h3>
            LLM giải thích <span className="badge muted">chưa kiểm chứng</span>
          </h3>
          <p className="claimed-box">{report.explanation}</p>
        </div>
      )}
      {report.warehouse_hints && report.warehouse_hints.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <h3>Gợi ý cho kho khác (không thực thi)</h3>
          <ul className="plain muted">
            {report.warehouse_hints.map((hint) => (
              <li key={hint}>{hint}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

export function OptimizationScreen() {
  const { detail } = useRun();
  if (!detail) return null;
  const report = detail.optimization;
  if (!report.original_sql) {
    return (
      <Card title="Tối ưu query">
        <Empty>Chưa tới bước tối ưu (E4 chạy sau khi code qua sandbox).</Empty>
      </Card>
    );
  }
  return (
    <>
      <div className="grid-2">
        <div className="stack">
          <Metrics report={report} />
          <Equivalence report={report} />
        </div>
        <Findings report={report} />
      </div>
      <Card title="SQL bảng đích: bản gốc ↔ bản đề xuất">
        {report.proposed_sql ? (
          <CodeDiff path="target.sql" original={report.original_sql} modified={report.proposed_sql} />
        ) : (
          <Empty>Không có bản đề xuất (giữ nguyên bản gốc).</Empty>
        )}
      </Card>
    </>
  );
}
