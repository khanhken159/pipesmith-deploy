"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { STATUS_LABELS } from "@/lib/format";
import type { RunRecord, RunStatus } from "@/lib/types";

import { useApp } from "./AppContext";
import { BellIcon } from "./icons";

export const NEEDS_ACTION: RunStatus[] = [
  "waiting_clarification",
  "waiting_plan_review",
  "waiting_review",
  "waiting_rescue",
];

export function runHref(run: RunRecord): string {
  return run.status === "waiting_review" ? `/runs/${run.id}/review` : `/runs/${run.id}`;
}

/** Đóng khung nổi khi bấm ra ngoài hoặc nhấn Esc. */
export function useDismiss(open: boolean, close: () => void) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const handle = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !box.current?.contains(event.target as Node))
        close();
    };
    document.addEventListener("mousedown", handle);
    document.addEventListener("keydown", handle);
    return () => {
      document.removeEventListener("mousedown", handle);
      document.removeEventListener("keydown", handle);
    };
  }, [open, close]);
  return box;
}

/** Chuông: các lần chạy đang chờ bạn (dữ liệu thật), không có thông báo dựng sẵn. */
export function NotificationBell() {
  const { runs } = useApp();
  const [open, setOpen] = useState(false);
  const box = useDismiss(open, () => setOpen(false));
  const waiting = (runs ?? []).filter((run) => NEEDS_ACTION.includes(run.status));

  return (
    <div className="popover" ref={box}>
      <button
        type="button"
        className="icon-btn"
        aria-label={`Thông báo: ${waiting.length} lần chạy cần bạn`}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <BellIcon />
        {waiting.length > 0 && <span className="bell-count">{waiting.length}</span>}
      </button>
      {open && (
        <div className="flyout" role="dialog" aria-label="Lần chạy cần bạn">
          <div className="flyout-head">
            <strong>Cần bạn xử lý</strong>
            <span className="muted small">{waiting.length}</span>
          </div>
          {waiting.length === 0 ? (
            <p className="empty">Không có gì đang chờ bạn.</p>
          ) : (
            <ul className="flyout-list">
              {waiting.slice(0, 12).map((run) => (
                <li key={run.id}>
                  <Link href={runHref(run)} onClick={() => setOpen(false)}>
                    <strong className="truncate">{run.summary.target ?? run.request_text}</strong>
                    <span className="small muted">{STATUS_LABELS[run.status]}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
