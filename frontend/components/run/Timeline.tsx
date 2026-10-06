"use client";

import { formatNumber } from "@/lib/format";

import { Card, Empty, Loading, PassMark } from "../ui";
import { useRun } from "./RunContext";

export function Timeline() {
  const { detail } = useRun();
  if (!detail) return null;
  const { busy, record } = detail;
  const events = detail.events ?? [];
  return (
    <Card title="Tiến trình" actions={<span className="muted small">✓/✗ do code đo, không phải lời agent</span>}>
      {events.length === 0 && !busy && (
        <Empty>
          Chưa có nhật ký từng bước trong phiên máy chủ này (nhật ký chỉ giữ trong bộ nhớ). Trạng thái và kết quả vẫn
          đầy đủ ở các mục bên dưới.
        </Empty>
      )}
      {events.length > 0 && (
        <ol className="timeline">
          {events.map((event, index) => (
            <li key={`${event.node}-${index}`}>
              <PassMark passed={event.ok} />
              <span className="step">{event.label}</span>
              <span className="detail">{event.detail}</span>
              <span className="meta">
                {event.seconds.toFixed(1)}s{event.tokens > 0 && ` · ${formatNumber(event.tokens)} token`}
              </span>
            </li>
          ))}
        </ol>
      )}
      {busy && <Loading text="Agent đang chạy bước tiếp theo…" />}
      {record.status === "failed" && record.summary.error && (
        <div className="alert danger" role="alert">
          <span>Đã dừng: {record.summary.error}</span>
        </div>
      )}
    </Card>
  );
}
