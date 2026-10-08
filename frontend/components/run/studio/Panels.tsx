"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { formatNumber, formatUsd } from "@/lib/format";
import type { RunDetail } from "@/lib/types";

import { ChartIcon, CopyIcon, CpuIcon, DatabaseIcon, FlowIcon, LayersIcon, TerminalIcon } from "../../icons";
import { useRun } from "../RunContext";
import { formatSeconds, useElapsed } from "./LiveNode";

// Cột phải của màn Studio. Mọi số lấy từ API (đo thật); chưa đo → "—", LLM mock → "mô phỏng".

function PanelHead({ icon, title, aside }: { icon: React.ReactNode; title: string; aside?: React.ReactNode }) {
  return (
    <header className="panel-head">
      <span className="row">
        <span className="panel-icon">{icon}</span>
        <h2>{title}</h2>
      </span>
      {aside}
    </header>
  );
}

export function MetricsPanel({ detail }: { detail: RunDetail }) {
  const rows = detail.usage?.rows ?? [];
  const simulated = detail.usage?.simulated ?? detail.record.summary.simulated;
  const sum = (key: "input_tokens" | "output_tokens" | "cost_usd" | "seconds" | "calls") =>
    rows.reduce((total, row) => total + row[key], 0);
  const tokens = rows.length ? sum("input_tokens") + sum("output_tokens") : null;
  const sandbox = detail.sandbox ?? {};
  const cache = detail.usage?.cache_hit_rate;
  const stats = [
    { label: "Token LLM", value: simulated ? "mô phỏng" : formatNumber(tokens), sub: `${sum("calls")} lượt gọi` },
    {
      label: "Chi phí ước tính",
      value: simulated ? "mô phỏng" : rows.length ? formatUsd(sum("cost_usd")) : "—",
      sub: "theo bảng giá",
    },
    {
      label: "Thời gian LLM",
      value: simulated ? "mô phỏng" : rows.length ? formatSeconds(sum("seconds")) : "—",
      sub: "tổng các lượt gọi",
    },
    {
      label: "Test chạy thử",
      value: sandbox.tests_total ? `${sandbox.tests_ok}/${sandbox.tests_total}` : "—",
      sub: "V2 đo bằng dbt",
    },
    {
      label: "Trúng cache",
      value: simulated ? "mô phỏng" : cache === null || cache === undefined ? "—" : `${Math.round(cache * 100)}%`,
      sub: "token đầu vào",
    },
    { label: "Vòng sửa lỗi", value: String(detail.record.summary.fix_attempts ?? 0), sub: "sau lỗi V1/V2" },
  ];
  return (
    <section className="card panel">
      <PanelHead icon={<ChartIcon />} title="Chỉ số đo được" />
      <div className="metric-grid">
        {stats.map((stat) => (
          <div key={stat.label} className="metric">
            <span>{stat.label}</span>
            <strong>{stat.value}</strong>
            <small>{stat.sub}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

export function FlowPanel({ detail }: { detail: RunDetail }) {
  const { runId } = useRun();
  const sources = detail.spec.sources ?? [];
  const target = detail.spec.target;
  const flowing = detail.busy;
  const rows = detail.sandbox?.target_rows;
  return (
    <section className="card panel">
      <PanelHead
        icon={<FlowIcon />}
        title="Luồng dữ liệu"
        aside={
          <Link href={`/runs/${runId}/catalog`} className="small">
            Chi tiết →
          </Link>
        }
      />
      {!target ? (
        <p className="empty">Hiện khi có kế hoạch.</p>
      ) : (
        <div className="flow" data-flowing={flowing}>
          <div className="flow-col">
            {sources.length === 0 && <div className="flow-node muted">—</div>}
            {sources.map((source) => (
              <div key={source.name} className="flow-node" title={source.name}>
                <span className="flow-icon">
                  <DatabaseIcon size={14} />
                </span>
                <span>
                  <strong className="mono">{source.name}</strong>
                  <small>{source.kind}</small>
                </span>
              </div>
            ))}
          </div>
          <div className="flow-link" aria-hidden />
          <div className="flow-col">
            <div className="flow-node agent">
              <span className="flow-tag">{detail.spec.mode?.toUpperCase() ?? "dbt"}</span>
              <span className="flow-icon">
                <CpuIcon size={14} />
              </span>
              <span>
                <strong>dbt staging → mart</strong>
                <small>{sources.length} model staging</small>
              </span>
            </div>
          </div>
          <div className="flow-link" aria-hidden />
          <div className="flow-col">
            <div className="flow-node" title={target}>
              <span className="flow-icon">
                <LayersIcon size={14} />
              </span>
              <span>
                <strong className="mono">{target}</strong>
                <small>{rows === undefined ? "chưa chạy thử" : `${formatNumber(rows)} dòng (sandbox)`}</small>
              </span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function clock(epochSeconds?: number): string {
  if (!epochSeconds) return "--:--:--";
  return new Date(epochSeconds * 1000).toLocaleTimeString("vi-VN", { hour12: false });
}

export function RuntimeConsole({ detail }: { detail: RunDetail }) {
  const events = detail.events ?? [];
  const current = detail.busy ? detail.current : null;
  const elapsed = useElapsed(current);
  const [copied, setCopied] = useState(false);
  const screen = useRef<HTMLDivElement>(null);
  const activity = current?.activity ?? [];
  const lineIndex = activity.length ? Math.floor(elapsed / 3.5) % activity.length : 0;

  useEffect(() => {
    if (screen.current) screen.current.scrollTop = screen.current.scrollHeight;
  }, [events.length, current?.node]);

  async function copy() {
    const text = events
      .map((e) => `[${clock(e.finished_at)}] ${e.ok ? "OK  " : "LỖI "} ${e.label}: ${e.detail} (${e.seconds}s)`)
      .join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // trình duyệt chặn clipboard: bỏ qua
    }
  }

  return (
    <section className="card panel">
      <PanelHead
        icon={<TerminalIcon />}
        title="Console"
        aside={
          <button type="button" className="btn small" onClick={copy} disabled={events.length === 0}>
            <CopyIcon size={13} /> {copied ? "Đã chép" : "Chép"}
          </button>
        }
      />
      <div className="console" ref={screen} role="log" aria-label="Nhật ký các bước">
        {events.length === 0 && !current && (
          <div className="console-line muted-line">Chưa có nhật ký trong phiên máy chủ này.</div>
        )}
        {events.map((event, index) => (
          <div key={`${event.node}-${index}`} className="console-line">
            <span className="c-time">[{clock(event.finished_at)}]</span>
            <span className={event.ok ? "c-ok" : "c-fail"}>{event.ok ? "OK  " : "LỖI "}</span>
            <span className="c-step">{event.label}</span>
            <span className="c-msg">
              {event.detail}
              <span className="c-time">
                {" "}
                · {event.seconds.toFixed(1)}s{event.tokens > 0 && ` · ${formatNumber(event.tokens)} token`}
              </span>
            </span>
          </div>
        ))}
        {current && (
          <div className="console-line live-line">
            <span className="c-time">[{formatSeconds(elapsed).padStart(7)}]</span>
            <span className="c-live">CHẠY</span>
            <span className="c-step">{current.label}</span>
            <span className="c-msg c-live-msg">
              {activity[lineIndex] ?? "…"} <em>(mô tả)</em>
            </span>
          </div>
        )}
      </div>
      <div className="console-foot small">
        <span title="OK/LỖI do code đo; CHẠY là mô tả việc đang làm, không phải log đo">
          OK/LỖI: code đo · CHẠY: mô tả
        </span>
        <span className="row">
          <span className={detail.busy ? "dot ok pulse" : "dot"} aria-hidden />
          {detail.busy ? "Trực tiếp" : "Nghỉ"}
        </span>
      </div>
    </section>
  );
}
