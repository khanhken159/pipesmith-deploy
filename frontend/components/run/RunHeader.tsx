"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { downloadUrl } from "@/lib/api";
import { formatTime } from "@/lib/format";

import { ErrorBox, Loading, StatusBadge } from "../ui";
import { PipelineTrack } from "./PipelineTrack";
import { useRun } from "./RunContext";

function Tabs({ runId }: { runId: string }) {
  const pathname = usePathname();
  const { detail } = useRun();
  const base = `/runs/${runId}`;
  const tabs = [
    { href: base, label: "Tổng quan" },
    { href: `${base}/review`, label: "Duyệt code", flag: detail?.record.status === "waiting_review" },
    { href: `${base}/optimize`, label: "Tối ưu" },
    { href: `${base}/catalog`, label: "Cấu trúc dữ liệu" },
  ];
  return (
    <nav className="tabs" aria-label="Các mục của lần chạy">
      {tabs.map((tab) => (
        <Link
          key={tab.href}
          href={tab.href}
          className={pathname === tab.href ? "tab active" : "tab"}
          aria-current={pathname === tab.href ? "page" : undefined}
        >
          {tab.label}
          {tab.flag && <span className="badge warn">chờ bạn</span>}
        </Link>
      ))}
    </nav>
  );
}

export function RunHeader() {
  const { runId, detail, error, loading, refresh } = useRun();
  if (loading && !detail) return <Loading text="Đang tải lần chạy…" />;
  if (!detail) return <ErrorBox message={error || "Không tải được lần chạy."} onRetry={refresh} />;
  const { record } = detail;
  const hasCode = record.status === "waiting_review" || record.status === "approved"; // đã có code chạy thử đạt
  return (
    <div className="run-head">
      <div className="run-title">
        <div>
          <div className="row">
            <Link href="/runs" className="small">
              ← Lần chạy
            </Link>
            <span className="muted small mono">{record.id}</span>
          </div>
          <h1>{record.request_text}</h1>
          <div className="row muted small">
            <StatusBadge status={record.status} />
            {detail.busy && <span className="badge info">agent đang chạy…</span>}
            <span>{record.requester}</span>
            <span>·</span>
            <span title={record.model}>{record.provider}</span>
            <span>·</span>
            <span>{formatTime(record.created_at)}</span>
          </div>
        </div>
        {hasCode && (
          <a className="btn" href={downloadUrl(runId)} download>
            Tải gói code (.zip)
          </a>
        )}
      </div>
      <PipelineTrack />
      {error && <ErrorBox message={`Mất kết nối, đang thử lại… (${error})`} />}
      <Tabs runId={runId} />
    </div>
  );
}
