"use client";

import { useCallback, useEffect, useState } from "react";

import { apiGet, messageOf } from "./api";

export interface Polled<T> {
  data: T | null;
  error: string;
  loading: boolean;
  refresh: () => Promise<void>;
}

/** Tải `path` ngay, rồi tải lại mỗi `intervalMs` (null = chỉ tải một lần). */
export function usePoll<T>(path: string | null, intervalMs: number | null): Polled<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!path) return;
    try {
      setData(await apiGet<T>(path));
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

  return { data, error, loading, refresh };
}
