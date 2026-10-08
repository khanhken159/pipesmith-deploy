"use client";

import Link from "next/link";
import { useState } from "react";

import { useApp } from "./AppContext";
import { runHref, useDismiss } from "./NotificationBell";
import { StatusPill } from "./StatusPill";

function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.5-3.5" />
    </svg>
  );
}

/** Tìm lần chạy theo yêu cầu, bảng đích hoặc mã (trên danh sách thật đã tải). */
export function RunSearch() {
  const { runs } = useApp();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const box = useDismiss(open, () => setOpen(false));
  const needle = query.trim().toLowerCase();
  const found = needle
    ? (runs ?? [])
        .filter((run) =>
          [run.request_text, run.summary.target ?? "", run.id].some((text) => text.toLowerCase().includes(needle)),
        )
        .slice(0, 8)
    : [];
  return (
    <div className="popover search" ref={box}>
      <label className="search-box">
        <SearchIcon />
        <span className="sr-only">Tìm lần chạy</span>
        <input
          type="search"
          placeholder="Tìm lần chạy…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
        />
      </label>
      {open && needle && (
        <div className="flyout" role="dialog" aria-label="Kết quả tìm">
          {found.length === 0 ? (
            <p className="empty">Không thấy lần chạy nào.</p>
          ) : (
            <ul className="flyout-list">
              {found.map((run) => (
                <li key={run.id}>
                  <Link
                    href={runHref(run)}
                    onClick={() => {
                      setOpen(false);
                      setQuery("");
                    }}
                  >
                    <strong className="truncate">{run.summary.target ?? run.request_text}</strong>
                    <span className="row small">
                      <StatusPill status={run.status} />
                      <span className="muted truncate">{run.request_text}</span>
                    </span>
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
