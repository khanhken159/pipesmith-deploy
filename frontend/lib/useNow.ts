"use client";

import { useEffect, useState } from "react";

/** Date.now() cập nhật mỗi `intervalMs` (0 trước lần cập nhật đầu, tránh lệch khi render phía máy chủ). */
export function useNow(intervalMs = 1000, active = true): number {
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (!active) return;
    const tick = () => setNow(Date.now());
    const first = setTimeout(tick, 0);
    const timer = setInterval(tick, intervalMs);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [intervalMs, active]);
  return now;
}
