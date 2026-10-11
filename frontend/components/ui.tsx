// Thành phần giao diện nhỏ dùng chung: trạng thái tải, lỗi, nhãn trạng thái, thẻ.

import type { ReactNode } from "react";

import { STATUS_LABELS, STATUS_TONES } from "@/lib/format";
import type { RunStatus } from "@/lib/types";

import { CheckIcon } from "./icons";

export function Loading({ text = "Đang tải…" }: { text?: string }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden />
      {text}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="alert danger" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="btn small" onClick={onRetry}>
          Thử lại
        </button>
      )}
    </div>
  );
}

export function StatusBadge({ status }: { status: RunStatus }) {
  return <span className={`badge ${STATUS_TONES[status]}`}>{STATUS_LABELS[status]}</span>;
}

export function Card({ title, actions, children }: { title: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      <header className="card-head">
        <h2>{title}</h2>
        {actions}
      </header>
      <div className="card-body">{children}</div>
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="stat" title={hint}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function PassMark({ passed }: { passed: boolean | null }) {
  if (passed === null)
    return (
      <span className="mark info" aria-label="Thông tin">
        •
      </span>
    );
  return passed ? (
    <span className="mark ok" aria-label="Đạt">
      ✓
    </span>
  ) : (
    <span className="mark danger" aria-label="Không đạt">
      ✗
    </span>
  );
}

/** Thẻ một bước của luồng (bố cục Studio): số thứ tự tròn, tiêu đề, nhãn bên phải; `state` đổi màu số. */
export function StepCard({
  step,
  title,
  aside,
  state = "idle",
  children,
}: {
  step: ReactNode;
  title: ReactNode;
  aside?: ReactNode;
  state?: "idle" | "active" | "done" | "waiting";
  children: ReactNode;
}) {
  return (
    <section className="card step-card" data-state={state}>
      <header className="step-head">
        <div className="step-title">
          <span className="step-num" aria-hidden>
            {step}
          </span>
          <h2>{title}</h2>
        </div>
        {aside}
      </header>
      <div className="step-body">{children}</div>
    </section>
  );
}

/** Ô chọn kiểu "nút bóng" (ô vuông bo tròn, tô gradient khi chọn): vẫn là checkbox thật, bàn phím/đọc màn hình dùng được. */
export function Checkbox({
  checked,
  onChange,
  disabled,
  children,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="check" data-disabled={disabled || undefined}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className="check-box" aria-hidden>
        <CheckIcon size={14} strokeWidth={3} />
      </span>
      <span className="check-label">{children}</span>
    </label>
  );
}
