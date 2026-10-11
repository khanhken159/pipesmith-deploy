"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { STATUS_LABELS, formatAgo, formatClock } from "@/lib/format";
import type { AdminUser, AuditEntry, ErrorEntry, RunRecord } from "@/lib/types";
import { useNow } from "@/lib/useNow";
import { usePoll } from "@/lib/usePoll";

import { RUNS_LIMIT, useApp } from "../AppContext";
import { CreateRunForm } from "../CreateRunForm";
import {
  ArrowRightIcon,
  BookIcon,
  BotIcon,
  CheckIcon,
  ClockIcon,
  DatabaseIcon,
  FlowIcon,
  LayersIcon,
  LockIcon,
  PulseIcon,
  SparkIcon,
  UserIcon,
  UsersIcon,
} from "../icons";
import { ENGINEER_ACTION, runHref, waitingFor } from "../NotificationBell";
import { StatusPill } from "../StatusPill";
import { ROLE_LABELS } from "../Topbar";
import { Empty } from "../ui";

// Trang chủ theo vai trò: Engineer (tạo yêu cầu, theo dõi yêu cầu của mình), Reviewer (hàng đợi duyệt),
// Admin (tài khoản + nhật ký). Mọi số là số thật từ API; chưa có thì "—".

interface StatItem {
  icon: ReactNode;
  value: string;
  label: string;
  hint?: string;
}

const count = (n: number | null | undefined) => (n === null || n === undefined ? "—" : String(n));

// ---------- Khối dùng chung ----------

function Hero({ eyebrow, title, sub, cta }: { eyebrow: string; title: ReactNode; sub: string; cta: ReactNode }) {
  return (
    <section className="hero">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p className="hero-sub">{sub}</p>
      {cta}
    </section>
  );
}

function StatsPanel({ title, stats }: { title: string; stats: StatItem[] }) {
  const { status, statusError } = useApp();
  return (
    <section className="glass overview">
      <header className="panel-row">
        <h2>{title}</h2>
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

function RunListCard({
  id,
  title,
  icon,
  runs,
  loaded,
  empty,
  showRequester = false,
}: {
  id?: string;
  title: string;
  icon: ReactNode;
  runs: RunRecord[];
  loaded: boolean;
  empty: string;
  showRequester?: boolean;
}) {
  const now = useNow(60000);
  return (
    <section className="glass recent" id={id}>
      <header className="panel-row">
        <h2 className="row">
          {icon} {title}
        </h2>
        <Link href="/runs" className="small link-arrow">
          Xem tất cả <ArrowRightIcon size={14} />
        </Link>
      </header>
      {loaded && runs.length === 0 && <Empty>{empty}</Empty>}
      <ul className="recent-list">
        {runs.map((run) => (
          <li key={run.id}>
            <Link href={runHref(run)} className="recent-item">
              <RunIcon run={run} />
              <span className="recent-text">
                <strong className="truncate">{run.summary.target ?? "Chưa có bảng đích"}</strong>
                <small className="truncate">
                  {showRequester ? `${run.requester} · ` : ""}
                  {run.request_text}
                </small>
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

function ActivityFeed({ runs, title = "Hoạt động mới nhất" }: { runs: RunRecord[] | null; title?: string }) {
  const recent = [...(runs ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 5);
  return (
    <section className="glass activity-feed">
      <header className="panel-row">
        <h2 className="row">
          <PulseIcon size={20} /> {title}
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

// ---------- Engineer ----------

function NewRequestCard() {
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

export function EngineerHome() {
  const { runs, user, status } = useApp();
  const mine = (runs ?? []).filter((r) => r.requester === user?.name);
  const approved = mine.filter((r) => r.status === "approved").length;
  const loaded = runs !== null;
  return (
    <div className="dashboard">
      <Hero
        eyebrow={`Engineer · Chào ${user?.display_name ?? ""}`}
        title={
          <>
            AI Agent cho
            <br />
            pipeline dữ liệu
          </>
        }
        sub="Nói bảng bạn cần — agent sinh dbt + Airflow, code kiểm chứng, Reviewer duyệt trước khi merge."
        cta={
          <a href="#request" className="btn cta">
            <BotIcon size={18} /> Bắt đầu ngay <ArrowRightIcon size={16} />
          </a>
        }
      />
      <StatsPanel
        title="Yêu cầu của tôi"
        stats={[
          {
            icon: <LayersIcon size={18} />,
            value: loaded ? `${mine.length}${mine.length === RUNS_LIMIT ? "+" : ""}` : "—",
            label: "Đã tạo",
          },
          {
            icon: <ClockIcon size={18} />,
            value: loaded ? String(waitingFor(user, runs, status?.require_separate_reviewer ?? true).length) : "—",
            label: "Chờ tôi",
          },
          {
            icon: <UserIcon size={18} />,
            value: loaded ? String(mine.filter((r) => r.status === "waiting_review").length) : "—",
            label: status?.require_separate_reviewer ? "Chờ Reviewer" : "Chờ duyệt",
          },
          { icon: <CheckIcon size={18} />, value: loaded ? String(approved) : "—", label: "Đã duyệt" },
        ]}
      />
      <RunListCard
        title="Yêu cầu gần đây của tôi"
        icon={<ClockIcon size={20} />}
        runs={mine.slice(0, 5)}
        loaded={loaded}
        empty="Bạn chưa tạo yêu cầu nào — mô tả bảng bạn cần ở khung bên phải."
      />
      <div className="dash-side">
        <NewRequestCard />
        <ActivityFeed runs={mine} title="Hoạt động của tôi" />
      </div>
    </div>
  );
}

// ---------- Reviewer ----------

function ErrorBookCard({ entries }: { entries: ErrorEntry[] | null }) {
  return (
    <section className="glass">
      <header className="panel-row">
        <h2 className="row">
          <BookIcon size={20} /> Sổ lỗi chờ duyệt
        </h2>
        <Link href="/errors" className="small link-arrow">
          Mở sổ lỗi <ArrowRightIcon size={14} />
        </Link>
      </header>
      {entries && entries.length === 0 && <Empty>Không có bài học nào chờ duyệt.</Empty>}
      <ul className="feed">
        {(entries ?? []).slice(0, 4).map((entry) => (
          <li key={entry.id}>
            <span className="feed-dot" aria-hidden />
            <span className="mono small">{entry.code}</span>
            <span className="truncate">{entry.description}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ReviewerHome() {
  const { runs, user } = useApp();
  const errors = usePoll<ErrorEntry[]>("/errors", 60000);
  const queue = [...waitingFor(user, runs)].sort((a, b) => a.updated_at.localeCompare(b.updated_at)); // cũ nhất trước
  const decided = (runs ?? []).filter((r) => r.status === "approved" || r.status === "failed");
  const loaded = runs !== null;
  const next = queue[0];
  return (
    <div className="dashboard">
      <Hero
        eyebrow={`Reviewer · Chào ${user?.display_name ?? ""}`}
        title={
          <>
            Hàng đợi
            <br />
            duyệt code
          </>
        }
        sub={
          loaded
            ? queue.length
              ? `${queue.length} lần chạy đang chờ bạn. Xem diff, số đo, điều kiện lọc cứng trước khi duyệt.`
              : "Không có lần chạy nào chờ duyệt. Code chỉ được merge khi bạn duyệt."
            : "Đang tải hàng đợi…"
        }
        cta={
          next ? (
            <Link href={runHref(next)} className="btn cta">
              <CheckIcon size={18} /> Duyệt lần chạy cũ nhất <ArrowRightIcon size={16} />
            </Link>
          ) : (
            <Link href="/runs" className="btn cta">
              <LayersIcon size={18} /> Xem mọi lần chạy <ArrowRightIcon size={16} />
            </Link>
          )
        }
      />
      <StatsPanel
        title="Tổng quan duyệt"
        stats={[
          { icon: <ClockIcon size={18} />, value: loaded ? String(queue.length) : "—", label: "Chờ duyệt" },
          {
            icon: <CheckIcon size={18} />,
            value: loaded ? String(decided.filter((r) => r.status === "approved").length) : "—",
            label: "Đã duyệt",
          },
          { icon: <BookIcon size={18} />, value: count(errors.data?.length), label: "Sổ lỗi chờ" },
          {
            icon: <LayersIcon size={18} />,
            value: loaded ? String((runs ?? []).filter((r) => ENGINEER_ACTION.includes(r.status)).length) : "—",
            label: "Đang chờ Engineer",
            hint: "Lần chạy đang chờ Engineer trả lời, duyệt kế hoạch hoặc cứu hộ",
          },
        ]}
      />
      <RunListCard
        id="queue"
        title="Chờ bạn duyệt (cũ nhất trước)"
        icon={<CheckIcon size={20} />}
        runs={queue.slice(0, 8)}
        loaded={loaded}
        empty="Hàng đợi trống."
        showRequester
      />
      <div className="dash-side">
        <ErrorBookCard entries={errors.data} />
        <ActivityFeed runs={decided} title="Đã quyết gần đây" />
      </div>
    </div>
  );
}

// ---------- Admin ----------

const ACTION_LABELS: Record<string, string> = {
  login: "Đăng nhập",
  logout: "Đăng xuất",
  "run.create": "Tạo yêu cầu",
  "code.generate": "Sinh code",
  "sandbox.run": "Chạy sandbox",
  "plan.approve": "Duyệt kế hoạch",
  "plan.revise": "Yêu cầu sửa kế hoạch",
  "review.approve": "Duyệt code",
  "review.reject": "Từ chối code",
  "error_book.approve": "Duyệt sổ lỗi",
  "error_book.discard": "Bỏ mục sổ lỗi",
  "user.create": "Cấp tài khoản",
  "user.update": "Sửa tài khoản",
  "user.lock": "Khóa tài khoản",
  "user.unlock": "Mở khóa",
  "permission.denied": "Bị chặn quyền",
};
const OUTCOME_TONES: Record<string, string> = { ok: "ok", fail: "danger", denied: "danger", locked: "warn" };

function AuditCard({ entries }: { entries: AuditEntry[] | null }) {
  return (
    <section className="glass recent">
      <header className="panel-row">
        <h2 className="row">
          <PulseIcon size={20} /> Nhật ký kiểm toán
        </h2>
        <span className="small muted">chỉ ghi thêm, mới nhất trước</span>
      </header>
      {entries && entries.length === 0 && <Empty>Chưa có hoạt động.</Empty>}
      <ul className="audit-list">
        {(entries ?? []).slice(0, 14).map((e, i) => (
          <li key={`${e.at}-${i}`}>
            <time suppressHydrationWarning>{formatClock(e.at)}</time>
            <strong className="truncate">{e.actor_name}</strong>
            <span className="truncate">
              {ACTION_LABELS[e.action] ?? e.action}
              {e.target && e.target !== e.actor_name ? <span className="muted"> · {e.target}</span> : null}
            </span>
            <span className={`badge ${OUTCOME_TONES[e.outcome] ?? "muted"}`}>{e.outcome}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function RolesCard({ users }: { users: AdminUser[] | null }) {
  const active = (users ?? []).filter((u) => u.is_active);
  const total = Math.max(active.length, 1);
  return (
    <section className="glass">
      <header className="panel-row">
        <h2 className="row">
          <UsersIcon size={20} /> Vai trò đang hoạt động
        </h2>
        <Link href="/admin" className="small link-arrow">
          Quản lý <ArrowRightIcon size={14} />
        </Link>
      </header>
      <ul className="role-bars">
        {(["engineer", "reviewer", "admin"] as const).map((role) => {
          const n = active.filter((u) => u.role === role).length;
          return (
            <li key={role} data-role={role}>
              <span>{ROLE_LABELS[role]}</span>
              <span className="role-bar" aria-hidden>
                <span style={{ width: `${(n / total) * 100}%` }} />
              </span>
              <strong>{users ? n : "—"}</strong>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function AdminHome() {
  const { user, status } = useApp();
  const users = usePoll<AdminUser[]>("/admin/users", 60000);
  const audit = usePoll<AuditEntry[]>("/admin/audit?limit=200", 15000);
  const list = users.data;
  const now = useNow(60000);
  const dayAgo = now - 24 * 3600 * 1000;
  const failed = (audit.data ?? []).filter(
    (e) => e.action === "login" && e.outcome !== "ok" && new Date(e.at).getTime() > dayAgo,
  ).length;
  return (
    <div className="dashboard">
      <Hero
        eyebrow={`Admin · Chào ${user?.display_name ?? ""}`}
        title={
          <>
            Tài khoản
            <br />& nhật ký
          </>
        }
        sub="Cấp, khóa tài khoản và đổi vai trò; xem ai làm gì, khi nào. Không có đăng ký tự do."
        cta={
          <Link href="/admin" className="btn cta">
            <UsersIcon size={18} /> Quản lý người dùng <ArrowRightIcon size={16} />
          </Link>
        }
      />
      <StatsPanel
        title="Hệ thống"
        stats={[
          { icon: <UsersIcon size={18} />, value: count(list?.length), label: "Tài khoản" },
          {
            icon: <CheckIcon size={18} />,
            value: count(list?.filter((u) => u.is_active).length),
            label: "Đang hoạt động",
          },
          { icon: <LockIcon size={18} />, value: count(list?.filter((u) => !u.is_active).length), label: "Đã khóa" },
          {
            icon: <PulseIcon size={18} />,
            value: audit.data && now ? String(failed) : "—",
            label: "Đăng nhập lỗi 24h",
            hint: status?.simulated ? "LLM: mô phỏng" : `LLM: ${status?.llm_provider ?? "—"}`,
          },
        ]}
      />
      <AuditCard entries={audit.data} />
      <div className="dash-side">
        <RolesCard users={list} />
      </div>
    </div>
  );
}
