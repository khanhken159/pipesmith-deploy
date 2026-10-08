"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiGetText, messageOf } from "./api";

export interface Polled<T> {
  data: T | null;
  error: string;
  loading: boolean;
  /** Date.now() lúc nhận `data` (0 = chưa có): để đồng hồ phía trình duyệt chạy tiếp từ số máy chủ trả. */
  fetchedAt: number;
  refresh: () => Promise<void>;
}

/** Tải `path` ngay, rồi tải lại mỗi `intervalMs` (null = chỉ tải một lần). */
export function usePoll<T>(path: string | null, intervalMs: number | null): Polled<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [fetchedAt, setFetchedAt] = useState(0);
  const lastText = useRef("");

  const refresh = useCallback(async () => {
    if (!path) return;
    try {
      const text = await apiGetText(path);
      if (text !== lastText.current) {
        // chỉ cập nhật khi dữ liệu đổi: hỏi định kỳ không làm vẽ lại cả trang
        lastText.current = text;
        setData(JSON.parse(text) as T);
        setFetchedAt(Date.now());
      }
      setError("");
    } catch (exc) {
      setError(messageOf(exc));
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    const first = setTimeout(refresh, 0);
    const timer = intervalMs ? setInterval(refresh, intervalMs) : undefined;
    return () => {
      clearTimeout(first);
      if (timer) clearInterval(timer);
    };
  }, [refresh, intervalMs]);

  return { data, error, loading, fetchedAt, refresh };
}
