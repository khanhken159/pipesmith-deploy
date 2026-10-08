"use client";

import type { AnsweredQuestion, Spec } from "@/lib/types";

import { PlanSteps } from "./PlanReview";

function List({ items }: { items?: string[] }) {
  if (!items?.length) return <span className="muted">—</span>;
  return (
    <ul className="plain">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

/** Đặc tả đầy đủ (đã duyệt): bảng đích, lý do ELT/ETL, grain, chỉ số, lọc, giả định, câu J1, kế hoạch, cột đầu ra. */
export function SpecBody({ spec, answered }: { spec: Spec; answered: AnsweredQuestion[] }) {
  return (
    <>
      <dl className="kv">
        <dt>Bảng đích</dt>
        <dd className="mono">{spec.target}</dd>
        <dt>Vì sao {spec.mode}</dt>
        <dd>{spec.mode_reason || "—"}</dd>
        <dt>Mỗi dòng là</dt>
        <dd className="mono">{spec.grain?.join(", ") || "—"}</dd>
        <dt>Chỉ số</dt>
        <dd>
          <List items={spec.metrics?.map((m) => `${m.name}: ${m.description}`)} />
        </dd>
        <dt>Bộ lọc</dt>
        <dd>
          <List items={spec.filters} />
        </dd>
        <dt>Giả định</dt>
        <dd>
          <List items={spec.assumptions} />
        </dd>
        <dt>Bạn đã chọn (J1)</dt>
        <dd>
          <List items={answered.map((a) => `${a.question} → ${a.answer}`)} />
        </dd>
      </dl>
      {spec.plan && spec.plan.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <h3 className="row">
            Kế hoạch đã duyệt <span className="badge muted">J1b</span>
          </h3>
          {spec.plan_summary && <p className="muted">{spec.plan_summary}</p>}
          <PlanSteps steps={spec.plan} />
        </div>
      )}
      {spec.output_columns && spec.output_columns.length > 0 && (
        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table>
            <thead>
              <tr>
                <th>Cột đầu ra</th>
                <th>Kiểu</th>
                <th>Ý nghĩa</th>
              </tr>
            </thead>
            <tbody>
              {spec.output_columns.map((column) => (
                <tr key={column.name}>
                  <td className="mono">{column.name}</td>
                  <td className="mono muted">{column.type}</td>
                  <td>{column.description || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
