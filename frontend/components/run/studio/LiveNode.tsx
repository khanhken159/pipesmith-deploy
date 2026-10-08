"use client";

import { useEffect, useState } from "react";

import type { CurrentNode } from "@/lib/types";
import { useNow } from "@/lib/useNow";

import { useRun } from "../RunContext";

const ROTATE_MS = 3500; // đổi câu mô tả
const TYPE_MS = 18; // tốc độ "gõ" từng ký tự
const SLOW_FACTOR = 1.6; // quá 1,6 lần thời gian thường lệ thì báo "lâu hơn thường lệ"

/** Giây đã chạy: số máy chủ đo lúc trả về + phần trôi qua ở trình duyệt từ lúc nhận (không phụ thuộc lệch đồng hồ). */
export function useElapsed(current: CurrentNode | null | undefined): number {
  const { fetchedAt } = useRun();
  const now = useNow(1000, Boolean(current));
  if (!current) return 0;
  const drift = now && fetchedAt ? Math.max(0, (now - fetchedAt) / 1000) : 0;
  return current.elapsed_s + drift;
}

export function formatSeconds(seconds: number): string {
  const s = Math.floor(seconds);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    const first = setTimeout(update, 0);
    query.addEventListener("change", update);
    return () => {
      clearTimeout(first);
      query.removeEventListener("change", update);
    };
  }, []);
  return reduced;
}

/** Một câu "gõ" dần từng ký tự; gắn key theo câu nên mỗi câu mới bắt đầu lại từ đầu. */
function TypedLine({ text, instant }: { text: string; instant: boolean }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setCount((n) => (n >= text.length ? n : n + 1)), TYPE_MS);
    return () => clearInterval(timer);
  }, [text]);
  const shown = instant ? text : text.slice(0, count);
  return (
    <span className="typed">
      {shown}
      {!instant && count < text.length && <span className="caret" aria-hidden />}
    </span>
  );
}

/**
 * "Agent đang làm gì": luân phiên các câu mô tả việc của bước (ghép từ state thật ở máy chủ). Đây là MÔ TẢ, không phải
 * log đo — hiển thị viền nét đứt, tách khỏi các dòng ✓/✗ do code đo.
 */
export function ActivityTicker({ lines }: { lines: string[] }) {
  const [index, setIndex] = useState(0);
  const reduced = usePrefersReducedMotion();
  useEffect(() => {
    if (lines.length < 2) return;
    const timer = setInterval(() => setIndex((i) => i + 1), ROTATE_MS);
    return () => clearInterval(timer);
  }, [lines.length]);
  if (lines.length === 0) return null;
  const position = index % lines.length;
  const line = lines[position];
  return (
    <div className="activity" aria-live="polite" aria-atomic="true">
      <span className="activity-tag">đang làm</span>
      <TypedLine key={`${position}-${line}`} text={line} instant={reduced} />
      {lines.length > 1 && (
        <span className="activity-count muted" aria-hidden>
          {position + 1}/{lines.length}
        </span>
      )}
    </div>
  );
}

/** Thanh tiến độ: chỉ ước lượng khi có thời gian đo thật các lần trước; không thì chạy vô định (không % giả). */
function Estimate({ elapsed, typical, samples }: { elapsed: number; typical: number | null; samples: number }) {
  if (typical === null || typical <= 0) {
    return (
      <>
        <div className="progress indeterminate" role="progressbar" aria-label="Đang chạy, chưa ước lượng được">
          <span />
        </div>
        <small className="muted">Chưa đủ dữ liệu ước lượng ({samples}/3)</small>
      </>
    );
  }
  const ratio = Math.min(elapsed / typical, 0.95);
  const slow = elapsed > typical * SLOW_FACTOR;
  return (
    <>
      <div
        className="progress"
        role="progressbar"
        aria-label="Ước lượng theo thời gian các lần trước"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(ratio * 100)}
      >
        <span style={{ width: `${ratio * 100}%` }} />
      </div>
      <small className="muted">
        {slow
          ? `Lâu hơn thường lệ (~${formatSeconds(typical)}), vẫn đang chạy`
          : `Thường ~${formatSeconds(typical)} (trung vị ${samples} lần đo)`}
      </small>
    </>
  );
}

function NotifyButton() {
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">("unsupported");
  useEffect(() => {
    const first = setTimeout(() => setPermission("Notification" in window ? Notification.permission : "unsupported"));
    return () => clearTimeout(first);
  }, []);
  if (permission !== "default") return null;
  return (
    <button
      type="button"
      className="btn small"
      onClick={async () => setPermission(await Notification.requestPermission())}
      title="Trình duyệt sẽ báo khi agent cần bạn trả lời hoặc duyệt, kể cả khi bạn đang ở tab khác"
    >
      Báo khi xong
    </button>
  );
}

/** Thẻ "đang chạy": tên bước, đồng hồ, ước lượng (nếu có số đo), mô tả việc đang làm. */
export function LiveNode({ current, compact = false }: { current: CurrentNode; compact?: boolean }) {
  const elapsed = useElapsed(current);
  return (
    <div className="live-node">
      <div className="live-head">
        <span className="row">
          <span className="spinner" aria-hidden />
          <strong>{current.label}</strong>
        </span>
        <span className="row">
          <span className="live-clock" aria-label={`Đã chạy ${formatSeconds(elapsed)}`}>
            {formatSeconds(elapsed)}
          </span>
          {!compact && <NotifyButton />}
        </span>
      </div>
      <Estimate elapsed={elapsed} typical={current.typical_s} samples={current.samples} />
      <ActivityTicker lines={current.activity} />
    </div>
  );
}
