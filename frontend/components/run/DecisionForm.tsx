"use client";

import { useState } from "react";

import { STATUS_LABELS } from "@/lib/format";

import { useApp } from "../AppContext";
import { Card, ErrorBox } from "../ui";
import { useRun } from "./RunContext";

function SeparateModeHint({ requester }: { requester: string }) {
  const { user } = useApp();
  if (user.role === "reviewer" && user.name !== requester) return null;
  return (
    <div className="alert warn">
      <span>
        Đang bật chế độ 2 người: cần vai trò Reviewer và khác người tạo yêu cầu ({requester}). Đổi ở thanh trên cùng.
      </span>
    </div>
  );
}

export function DecisionForm() {
  const { detail, act } = useRun();
  const { status } = useApp();
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  if (!detail) return null;
  const waiting = detail.record.status === "waiting_review" && !detail.busy;

  async function decide(decision: "approve" | "reject") {
    setSending(true);
    setError(await act("/review", { decision, note }));
    setSending(false);
  }

  return (
    <Card title="Quyết định (J2)">
      <div className="stack" style={{ gap: 10 }}>
        {!waiting && (
          <div className={detail.record.status === "approved" ? "alert ok" : "alert info"}>
            <span>
              {detail.busy ? "Agent đang chạy, chờ một chút." : `Trạng thái: ${STATUS_LABELS[detail.record.status]}.`}
            </span>
          </div>
        )}
        {waiting && status?.require_separate_reviewer && <SeparateModeHint requester={detail.record.requester} />}
        <label htmlFor="review-note">Ghi chú (bắt buộc khi từ chối — agent sẽ sửa theo ghi chú)</label>
        <textarea
          id="review-note"
          rows={4}
          maxLength={2000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Ví dụ: loại đơn hoàn khỏi doanh thu; đổi tên cột revenue thành revenue_vnd"
          disabled={!waiting}
        />
        {error && <ErrorBox message={error} />}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button
            type="button"
            className="btn danger"
            disabled={!waiting || sending || !note.trim()}
            onClick={() => decide("reject")}
          >
            Từ chối, yêu cầu sửa
          </button>
          <button type="button" className="btn ok" disabled={!waiting || sending} onClick={() => decide("approve")}>
            Duyệt
          </button>
        </div>
        <small className="muted">
          Duyệt xong: tải gói code (.zip) ở góc trên, đưa vào repo và mở Pull Request để CI/CD chạy. Agent không tự
          push.
        </small>
      </div>
    </Card>
  );
}
