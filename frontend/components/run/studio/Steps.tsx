"use client";

import Link from "next/link";

import type { RunDetail, Stage } from "@/lib/types";

import { CheckIcon } from "../../icons";
import { StatusPill } from "../../StatusPill";
import { Loading, StepCard } from "../../ui";
import { ClarifyForm, RescueForm } from "../PendingAction";
import { PlanReview } from "../PlanReview";
import { useRun } from "../RunContext";
import { SpecBody } from "../SpecCard";
import { LiveNode } from "./LiveNode";

// Bốn bước của màn Studio (bố cục mẫu ai-agent-studio), nội dung là luồng thật: yêu cầu → J1 → J1b → chạy + J2.

const PLANNING = new Set(["planner", "spec_check"]); // nút của giai đoạn lập kế hoạch

/** Đang ở giai đoạn lập kế hoạch: theo node đang chạy thật; chưa có sự kiện nào thì coi là vừa khởi động planner. */
function isPlanning(detail: RunDetail): boolean {
  if (!detail.busy) return false;
  return detail.current ? PLANNING.has(detail.current.stage ?? "") : !detail.spec.target;
}

function stepState(done: boolean, active: boolean): "done" | "active" | "waiting" {
  return done ? "done" : active ? "active" : "waiting";
}

function DoneTag({ text }: { text: string }) {
  return (
    <span className="badge ok">
      <CheckIcon size={12} /> {text}
    </span>
  );
}

function NeedYou() {
  return <span className="badge warn">Cần bạn</span>;
}

export function RequestStep({ detail }: { detail: RunDetail }) {
  const { record } = detail;
  return (
    <StepCard step={1} title="Yêu cầu" state="done" aside={<StatusPill status={record.status} />}>
      <blockquote className="request-quote">{record.request_text}</blockquote>
    </StepCard>
  );
}

export function ClarifyStep({ detail }: { detail: RunDetail }) {
  const pending = detail.pending?.kind === "clarify" ? detail.pending : null;
  const answered = detail.answered ?? [];
  const planned = Boolean(detail.spec.target);
  const planning = isPlanning(detail);
  const state = stepState(!pending && !planning && (answered.length > 0 || planned), Boolean(pending) || planning);
  return (
    <StepCard
      step={2}
      title="Làm rõ (J1)"
      state={state}
      aside={pending ? <NeedYou /> : answered.length > 0 ? <DoneTag text={`${answered.length} câu`} /> : null}
    >
      {pending && (
        <>
          <ClarifyForm unknowns={pending.unknowns} questions={pending.questions} />
        </>
      )}
      {!pending && answered.length > 0 && (
        <ul className="answered">
          {answered.map((item) => (
            <li key={item.id}>
              <span className="muted">{item.question}</span>
              <strong>{item.answer}</strong>
            </li>
          ))}
        </ul>
      )}
      {!pending && answered.length === 0 && planned && <p className="muted">Đủ rõ, không cần hỏi.</p>}
      {!pending && !planned && <p className="muted">{planning ? "Agent đang đọc yêu cầu…" : "Chờ agent."}</p>}
    </StepCard>
  );
}

function PlanGlance({ detail }: { detail: RunDetail }) {
  const { spec } = detail;
  const items = [
    { label: "Bảng đích", value: spec.target, mono: true },
    { label: "Kiểu pipeline", value: spec.mode?.toUpperCase() },
    { label: "Mỗi dòng là", value: spec.grain?.join(", "), mono: true },
    { label: "Cột đầu ra", value: spec.output_columns ? `${spec.output_columns.length} cột` : undefined },
  ];
  return (
    <div className="glance">
      {items.map((item) => (
        <div key={item.label}>
          <span>{item.label}</span>
          <strong className={item.mono ? "mono" : undefined}>{item.value || "—"}</strong>
        </div>
      ))}
    </div>
  );
}

function PlanSkeleton() {
  return (
    <div className="skeleton-plan" aria-hidden>
      <div className="glance">
        {[0, 1, 2, 3].map((i) => (
          <div key={i}>
            <span className="skeleton" style={{ width: "60%" }} />
            <span className="skeleton" style={{ width: "80%", height: 16 }} />
          </div>
        ))}
      </div>
      <span className="skeleton" style={{ width: "92%" }} />
      <span className="skeleton" style={{ width: "74%" }} />
    </div>
  );
}

export function PlanStep({ detail }: { detail: RunDetail }) {
  const pending = detail.pending?.kind === "plan" ? detail.pending : null;
  const planning = isPlanning(detail);
  const approved = Boolean(detail.spec.plan?.length) && !pending;
  const state = stepState(approved, Boolean(pending || planning));
  return (
    <StepCard
      step={3}
      title="Kế hoạch (J1b)"
      state={state}
      aside={pending ? <NeedYou /> : approved ? <DoneTag text="Đã duyệt" /> : null}
    >
      {pending && <PlanReview pending={pending} />}
      {!pending && planning && (
        <div className="stack" style={{ gap: 12 }}>
          {detail.current ? <LiveNode current={detail.current} /> : <Loading text="Đang khởi động agent…" />}
          <PlanSkeleton />
        </div>
      )}
      {!pending && !planning && detail.spec.target && (
        <>
          {!approved && <p className="muted small">Bản nháp — chờ câu trả lời ở bước 2.</p>}
          <PlanGlance detail={detail} />
          {detail.spec.plan_summary && <p className="plan-summary">{detail.spec.plan_summary}</p>}
          <details className="more">
            <summary>Xem chi tiết</summary>
            <SpecBody spec={detail.spec} answered={detail.answered ?? []} />
          </details>
        </>
      )}
      {!pending && !planning && !detail.spec.target && <p className="muted">Chưa có kế hoạch.</p>}
    </StepCard>
  );
}

const STATE_TEXT: Record<Stage["state"], string> = {
  waiting: "Chờ",
  running: "Đang chạy",
  passed: "Đạt",
  failed: "Lỗi",
  human: "Chờ bạn",
};

function TrackerRow({ stage, detail }: { stage: Stage; detail: RunDetail }) {
  const { runId } = useRun();
  if (stage.state === "running" && detail.current && !PLANNING.has(detail.current.stage ?? "")) {
    return (
      <li className="track-row running">
        <LiveNode current={detail.current} />
      </li>
    );
  }
  const glyph = { passed: "✓", failed: "✗", human: "!", running: "", waiting: "" }[stage.state];
  return (
    <li className="track-row" data-state={stage.state} data-kind={stage.kind}>
      <span className="track-dot" aria-hidden>
        {stage.state === "running" ? <span className="spinner" /> : glyph}
      </span>
      <div className="track-text">
        <strong>
          {stage.code} · {stage.label}
        </strong>
        {stage.detail && stage.state !== "running" && <small className="muted">{stage.detail}</small>}
      </div>
      <span className="track-state">
        {stage.id === "review" && stage.state === "human" ? (
          <Link href={`/runs/${runId}/review`} className="btn primary small">
            Mở màn duyệt
          </Link>
        ) : (
          STATE_TEXT[stage.state]
        )}
      </span>
    </li>
  );
}

export function TrackerStep({ detail }: { detail: RunDetail }) {
  const stages = (detail.stages ?? []).filter(
    (s) => !["planner", "clarify", "spec_check", "plan_review"].includes(s.id),
  );
  const started = stages.some((s) => s.state !== "waiting");
  const done = detail.record.status === "approved";
  const rescue = detail.pending?.kind === "rescue" ? detail.pending : null;
  return (
    <StepCard
      step={4}
      title="Chạy và kiểm chứng"
      state={stepState(done, started)}
      aside={
        detail.busy && started ? (
          <span className="badge info">
            <span className="pulse-dot" aria-hidden /> Agent đang chạy
          </span>
        ) : rescue || detail.pending?.kind === "review" ? (
          <NeedYou />
        ) : done ? (
          <DoneTag text="Đã duyệt" />
        ) : null
      }
    >
      {!started && <p className="muted">Bắt đầu sau khi bạn duyệt kế hoạch.</p>}
      {started && (
        <ol className="tracker">
          {stages.map((stage) => (
            <TrackerRow key={stage.id} stage={stage} detail={detail} />
          ))}
        </ol>
      )}
      {rescue && (
        <div className="rescue-box">
          <RescueForm error={rescue.error} attempts={rescue.fix_attempts} />
        </div>
      )}
      {detail.record.status === "failed" && detail.record.summary.error && (
        <div className="alert danger" role="alert">
          <span>Đã dừng: {detail.record.summary.error}</span>
        </div>
      )}
    </StepCard>
  );
}
