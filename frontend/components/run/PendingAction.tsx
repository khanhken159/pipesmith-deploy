"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import type { ClarifyQuestion, Pending } from "@/lib/types";

import { Card, ErrorBox } from "../ui";
import { PlanReview } from "./PlanReview";
import { useRun } from "./RunContext";

function ClarifyForm({ unknowns, questions }: { unknowns: string[]; questions: ClarifyQuestion[] }) {
  const { act } = useRun();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const complete = questions.every((q) => answers[q.id]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSending(true);
    setError(await act("/answers", { answers }));
    setSending(false);
  }

  return (
    <form onSubmit={submit}>
      {unknowns.length > 0 && (
        <div className="alert info" style={{ marginBottom: 12 }}>
          <span>Agent chưa rõ: {unknowns.join("; ")}</span>
        </div>
      )}
      {questions.map((q, index) => (
        <fieldset key={q.id}>
          <legend>
            {index + 1}. {q.question}
          </legend>
          {q.options.map((option) => (
            <label key={option} className="option">
              <input
                type="radio"
                name={q.id}
                value={option}
                checked={answers[q.id] === option}
                onChange={() => setAnswers({ ...answers, [q.id]: option })}
              />
              <span>{option}</span>
            </label>
          ))}
        </fieldset>
      ))}
      {error && <ErrorBox message={error} />}
      <div className="row" style={{ justifyContent: "flex-end", marginTop: 8 }}>
        <button type="submit" className="btn primary" disabled={!complete || sending}>
          {sending ? "Đang gửi…" : "Gửi câu trả lời"}
        </button>
      </div>
    </form>
  );
}

function RescueForm({ error, attempts }: { error: string; attempts: number }) {
  const { act } = useRun();
  const [hint, setHint] = useState("");
  const [sending, setSending] = useState(false);
  const [failure, setFailure] = useState("");

  async function send(action: "retry" | "abort") {
    setSending(true);
    setFailure(await act("/rescue", { action, hint }));
    setSending(false);
  }

  return (
    <div className="stack" style={{ gap: 10 }}>
      <p>Agent đã sửa {attempts} lần nhưng vẫn lỗi. Lỗi cuối (do V-node đo):</p>
      <pre>{error || "(không có chi tiết)"}</pre>
      <label htmlFor="hint">Gợi ý cho agent (ví dụ: cột ngày ở nguồn Tiki dạng dd/mm/yyyy)</label>
      <textarea id="hint" value={hint} onChange={(e) => setHint(e.target.value)} maxLength={2000} />
      {failure && <ErrorBox message={failure} />}
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="btn danger" disabled={sending} onClick={() => send("abort")}>
          Dừng lần chạy
        </button>
        <button type="button" className="btn primary" disabled={sending || !hint.trim()} onClick={() => send("retry")}>
          Gửi gợi ý và thử lại
        </button>
      </div>
    </div>
  );
}

function PendingBody({ pending, runId }: { pending: Pending; runId: string }) {
  if (pending.kind === "clarify") return <ClarifyForm unknowns={pending.unknowns} questions={pending.questions} />;
  if (pending.kind === "plan") return <PlanReview pending={pending} />;
  if (pending.kind === "rescue") return <RescueForm error={pending.error} attempts={pending.fix_attempts} />;
  return (
    <div className="row" style={{ justifyContent: "space-between" }}>
      <span>Code đã chạy thử đạt trong sandbox. Hãy xem diff và bằng chứng rồi quyết định.</span>
      <Link href={`/runs/${runId}/review`} className="btn primary">
        Mở màn duyệt
      </Link>
    </div>
  );
}

const TITLES: Record<Pending["kind"], string> = {
  clarify: "J1 · Agent cần bạn làm rõ",
  plan: "J1b · Duyệt kế hoạch trước khi agent sinh code",
  rescue: "Cứu hộ · Agent cần gợi ý",
  review: "J2 · Chờ bạn duyệt",
};

export function PendingAction() {
  const { detail, runId } = useRun();
  if (!detail?.pending || detail.busy) return null;
  return (
    <Card title={TITLES[detail.pending.kind]} actions={<span className="badge warn">Cần bạn</span>}>
      <PendingBody pending={detail.pending} runId={runId} />
    </Card>
  );
}
