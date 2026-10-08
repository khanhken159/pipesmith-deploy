"use client";

import { useState } from "react";

import type { PlanPending, PlanStep, Spec } from "@/lib/types";

import { ErrorBox } from "../ui";
import { useRun } from "./RunContext";

export function PlanSteps({ steps }: { steps: PlanStep[] }) {
  return (
    <ol className="plan-steps">
      {steps.map((step, index) => (
        <li key={`${index}-${step.title}`}>
          <span className="plan-index" aria-hidden>
            {index + 1}
          </span>
          <div>
            <strong>{step.title}</strong>
            {step.detail && <p>{step.detail}</p>}
            {step.reason && (
              <p className="plan-reason">
                <span>Vì sao:</span> {step.reason}
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

function SpecGlance({ spec, sources }: { spec: Spec; sources: string[] }) {
  return (
    <dl className="kv">
      <dt>Bảng đích</dt>
      <dd className="mono">{spec.target}</dd>
      <dt>Đọc từ</dt>
      <dd className="mono">{sources.join(", ") || "—"}</dd>
      <dt>Mỗi dòng là</dt>
      <dd className="mono">{spec.grain?.join(", ") || "—"}</dd>
      <dt>Cột đầu ra</dt>
      <dd className="mono">{spec.output_columns?.map((c) => `${c.name} (${c.type})`).join(", ") || "—"}</dd>
      <dt>Kiểu pipeline</dt>
      <dd>
        {spec.mode} — {spec.mode_reason}
      </dd>
      <dt>Giả định</dt>
      <dd>
        {spec.assumptions?.length ? (
          <ul className="plain">
            {spec.assumptions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          "—"
        )}
      </dd>
    </dl>
  );
}

export function PlanReview({ pending }: { pending: PlanPending }) {
  const { act } = useRun();
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function decide(decision: "approve" | "revise") {
    setSending(true);
    setError(await act("/plan", { decision, note }));
    setSending(false);
  }

  return (
    <div className="stack" style={{ gap: 14 }}>
      <p className="plan-summary">{pending.summary}</p>
      <div className="grid-2">
        <div>
          <h3 className="row">
            Các bước agent sẽ làm <span className="badge muted">LLM lập, bạn kiểm tra</span>
          </h3>
          <PlanSteps steps={pending.steps} />
        </div>
        <div>
          <h3>Đặc tả</h3>
          <SpecGlance spec={pending.spec} sources={pending.sources} />
        </div>
      </div>
      <div className="alert info">
        <span>{pending.next_steps}</span>
      </div>
      <label htmlFor="plan-note">Muốn sửa? Ghi rõ cần thay đổi gì (agent sẽ lập lại kế hoạch)</label>
      <textarea
        id="plan-note"
        rows={3}
        maxLength={2000}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Ví dụ: thêm cột kênh bán; loại đơn hoàn tiền khỏi doanh thu"
      />
      {error && <ErrorBox message={error} />}
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button
          type="button"
          className="btn danger"
          disabled={sending || !note.trim()}
          onClick={() => decide("revise")}
        >
          Yêu cầu sửa kế hoạch
        </button>
        <button type="button" className="btn ok" disabled={sending} onClick={() => decide("approve")}>
          Đồng ý, sinh code
        </button>
      </div>
    </div>
  );
}
