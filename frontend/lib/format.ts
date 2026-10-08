// Định dạng hiển thị (tiếng Việt).

import type { Layer, RunStatus } from "./types";

export const STATUS_LABELS: Record<RunStatus, string> = {
  running: "Đang chạy",
  waiting_clarification: "Chờ trả lời câu hỏi",
  waiting_plan_review: "Chờ duyệt kế hoạch",
  waiting_rescue: "Cần cứu hộ",
  waiting_review: "Chờ duyệt",
  approved: "Đã duyệt",
  failed: "Đã dừng",
};

export const STATUS_TONES: Record<RunStatus, string> = {
  running: "info",
  waiting_clarification: "warn",
  waiting_plan_review: "warn",
  waiting_rescue: "danger",
  waiting_review: "warn",
  approved: "ok",
  failed: "danger",
};

export const LAYER_LABELS: Record<Layer, string> = {
  source: "Nguồn (raw)",
  staging: "Staging",
  mart: "Mart (bảng đích)",
};

export function formatTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString("vi-VN");
}

export function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toLocaleString("vi-VN");
}

export function formatUsd(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `$${value.toFixed(4)}`;
}

export function formatPct(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toLocaleString("vi-VN")}%`;
}

export function languageOf(path: string): string {
  if (path.endsWith(".sql")) return "sql";
  if (path.endsWith(".py")) return "python";
  if (path.endsWith(".yml") || path.endsWith(".yaml")) return "yaml";
  return "plaintext";
}

/** Thời gian tương đối: "vừa xong", "5 phút trước", "2 giờ trước", "hôm qua", hoặc ngày. */
export function formatAgo(iso: string, now: number): string {
  const time = new Date(iso).getTime();
  if (Number.isNaN(time) || !now) return formatTime(iso);
  const minutes = Math.max(0, Math.round((now - time) / 60000));
  if (minutes < 1) return "vừa xong";
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.round(hours / 24);
  return days === 1 ? "hôm qua" : days < 7 ? `${days} ngày trước` : new Date(iso).toLocaleDateString("vi-VN");
}

/** Giờ:phút của một mốc thời gian (cho dòng hoạt động). */
export function formatClock(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", hour12: false });
}
