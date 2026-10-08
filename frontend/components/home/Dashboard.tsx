"use client";

import Link from "next/link";

import { STATUS_LABELS, formatAgo, formatClock } from "@/lib/format";
import type { RunRecord } from "@/lib/types";
import { useNow } from "@/lib/useNow";

import { RUNS_LIMIT, useApp } from "../AppContext";
import { CreateRunForm } from "../CreateRunForm";
import {
  ArrowRightIcon,
  BotIcon,
  CheckIcon,
  ClockIcon,
  DatabaseIcon,
  FlowIcon,
  LayersIcon,
  PulseIcon,
  SparkIcon,
} from "../icons";
import { NEEDS_ACTION, runHref } from "../NotificationBell";
import { StatusPill } from "../StatusPill";
import { Empty } from "../ui";

// Trang chủ theo bố cục mẫu. Mọi số là số thật từ /runs; chưa có thì "—".

export function SystemOverview() {
  const { runs, status, statusError } = useApp();
  const list = runs ?? [];
  const approved = list.filter((r) => r.status === "approved").length;
  const failed = list.filter((r) => r.status === "failed").length;
  const waiting = list.filter((r) => NEEDS_ACTION.includes(r.status)).length;
  const finished = approved + failed;
  const count = runs ? `${list.length}${list.length === RUNS_LIMIT ? "+" : ""}` : "—";
  const stats = [
    { icon: <LayersIcon size={18} />, value: count, label: "Lần chạy", hint: "" },
    { icon: <CheckIcon size={18} />, value: runs ? String(approved) : "—", label: "Đã duyệt", hint: "" },
    { icon: <ClockIcon size={18} />, value: runs ? String(waiting) : "—", label: "Chờ bạn", hint: "" },
    {
      icon: <PulseIcon size={18} />,
      value: finished ? `${Math.round((approved / finished) * 100)}%` : "—",
      label: "Duyệt / kết thúc",
      hint: `${approved} duyệt trên ${finished} lần chạy đã kết thúc (n=${finished}); không tính lần đang chờ`,
    },
  ];
  return (
    <section className="glass overview">
      <header className="panel-row">
        <h2>Tổng quan</h2>
        <span className="row small muted">
          <span className={statusError ? "dot fail" : status ? "dot ok" : "dot"} aria-hidden />
          {statusError ? "Mất kết nối" : status ? "Hệ thống hoạt động" : "Đang kiểm tra…"}
        </span>
      </header>
      <div className="overview-grid">
        {stats.map((stat) => (
          <div key={stat.label} className="overview-stat" title={stat.hint || undefined}>
            <span className="stat-icon">{stat.icon}</span>
            <strong>{stat.value}</strong>
            <span>{stat.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function RunIcon({ run }: { run: RunRecord }) {
  const Glyph = run.summary.mode === "ETL" ? FlowIcon : run.status === "approved" ? DatabaseIcon : SparkIcon;
  return (
    <span className="run-icon" aria-hidden>
      <Glyph size={18} />
    </span>
  );
}

export function RecentRunsCard() {
  const { runs } = useApp();
  const now = useNow(60000);
  const list = (runs ?? []).slice(0, 5);
  return (
    <section className="glass recent">
      <header className="panel-row">
        <h2 className="row">
          <ClockIcon size={20} /> Lần chạy gần đây
        </h2>
        <Link href="/runs" className="small link-arrow">
          Xem tất cả <ArrowRightIcon size={14} />
        </Link>
      </header>
      {runs && list.length === 0 && <Empty>Chưa có lần chạy nào.</Empty>}
      <ul className="recent-list">
        {list.map((run) => (
          <li key={run.id}>
            <Link href={runHref(run)} className="recent-item">
              <RunIcon run={run} />
              <span className="recent-text">
                <strong className="truncate">{run.summary.target ?? "Chưa có bảng đích"}</strong>
                <small className="truncate">{run.request_text}</small>
              </span>
              <span className="recent-meta">
                <StatusPill status={run.status} />
                <small suppressHydrationWarning>{formatAgo(run.updated_at, now)}</small>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function NewRequestCard() {
  return (
    <section className="glass new-request" id="request">
      <span className="orb" aria-hidden />
      <p className="eyebrow-sm row">
        <SparkIcon size={16} /> Yêu cầu mới
      </p>
      <h2>Mô tả pipeline bạn cần</h2>
      <CreateRunForm />
    </section>
  );
}

export function ActivityFeed() {
  const { runs } = useApp();
  const recent = [...(runs ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 5);
  return (
    <section className="glass activity-feed">
      <header className="panel-row">
        <h2 className="row">
          <PulseIcon size={20} /> Hoạt động mới nhất
        </h2>
        <Link href="/runs" className="small link-arrow">
          Xem tất cả <ArrowRightIcon size={14} />
        </Link>
      </header>
      {runs && recent.length === 0 && <Empty>Chưa có hoạt động.</Empty>}
      <ul className="feed">
        {recent.map((run) => (
          <li key={run.id} data-status={run.status}>
            <span className="feed-dot" aria-hidden />
            <time suppressHydrationWarning>{formatClock(run.updated_at)}</time>
            <Link href={runHref(run)} className="truncate">
              <strong>{run.summary.target ?? run.id}</strong> · {STATUS_LABELS[run.status].toLowerCase()}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Hero() {
  return (
    <section className="hero">
      <p className="eyebrow">Mô tả · Kiểm chứng · Duyệt</p>
      <h1>
        AI Agent cho
        <br />
        pipeline dữ liệu
      </h1>
      <p className="hero-sub">Nói bảng bạn cần — agent sinh dbt + Airflow, code kiểm chứng, bạn duyệt.</p>
      <a href="#request" className="btn cta">
        <BotIcon size={18} /> Bắt đầu ngay <ArrowRightIcon size={16} />
      </a>
    </section>
  );
}
