"use client";

import { useState, type FormEvent } from "react";

import type { ClarifyQuestion } from "@/lib/types";

import { ErrorBox } from "../ui";
import { useRun } from "./RunContext";

// Form cho các điểm dừng cần người: J1 trả lời câu hỏi làm rõ, cứu hộ. (J1b: PlanReview; J2: màn duyệt.)

export function ClarifyForm({ unknowns, questions }: { unknowns: string[]; questions: ClarifyQuestion[] }) {
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
          <div className="option-pills">
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
          </div>
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

export function RescueForm({ error, attempts }: { error: string; attempts: number }) {
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
