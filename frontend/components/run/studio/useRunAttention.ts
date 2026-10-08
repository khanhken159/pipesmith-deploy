"use client";

import { useEffect, useRef } from "react";

import type { RunDetail } from "@/lib/types";

const BASE_TITLE = "P-113 Agent Studio";
const PENDING_TEXT: Record<string, string> = {
  clarify: "Agent cần bạn trả lời câu hỏi",
  plan: "Kế hoạch chờ bạn duyệt",
  rescue: "Agent cần gợi ý cứu hộ",
  review: "Code chạy thử đạt, chờ bạn duyệt",
};

/**
 * Để người dùng rời tab trong lúc chờ LLM: tiêu đề tab cho biết bước đang chạy / cần bạn, và (nếu đã cho phép)
 * trình duyệt báo khi lần chạy chuyển từ "đang chạy" sang "chờ bạn" hoặc dừng — chỉ khi tab đang ẩn.
 */
export function useRunAttention(detail: RunDetail | null): void {
  const wasBusy = useRef(false);
  const busy = Boolean(detail?.busy);
  const pendingKind = detail?.pending?.kind ?? "";
  const label = detail?.current?.label ?? "";
  const status = detail?.record.status ?? "";

  useEffect(() => {
    if (!detail) return;
    if (busy) document.title = `⏳ ${label || "Agent đang chạy"} · ${BASE_TITLE}`;
    else if (pendingKind) document.title = `● Cần bạn · ${BASE_TITLE}`;
    else document.title = BASE_TITLE;
    return () => {
      document.title = BASE_TITLE;
    };
  }, [detail, busy, pendingKind, label]);

  useEffect(() => {
    const finished = wasBusy.current && !busy;
    wasBusy.current = busy;
    if (!finished || !document.hidden || !("Notification" in window) || Notification.permission !== "granted") return;
    const body = pendingKind ? PENDING_TEXT[pendingKind] : status === "failed" ? "Lần chạy đã dừng vì lỗi" : "";
    if (body) new Notification(BASE_TITLE, { body, tag: "p113-run" });
  }, [busy, pendingKind, status]);
}
