// Nhãn trạng thái có biểu tượng (kiểu mẫu: ✓ Hoàn thành, ✗ Thất bại, • Đang chạy).

import { STATUS_LABELS, STATUS_TONES } from "@/lib/format";
import type { RunStatus } from "@/lib/types";

const GLYPH: Record<RunStatus, string> = {
  running: "",
  waiting_clarification: "?",
  waiting_plan_review: "!",
  waiting_rescue: "!",
  waiting_review: "!",
  approved: "✓",
  failed: "✗",
};

export function StatusPill({ status }: { status: RunStatus }) {
  return (
    <span className={`status-pill ${STATUS_TONES[status]}`}>
      <span className="status-glyph" aria-hidden>
        {status === "running" ? <span className="pulse-dot" /> : GLYPH[status]}
      </span>
      {STATUS_LABELS[status]}
    </span>
  );
}
