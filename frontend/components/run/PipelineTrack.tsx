"use client";

import type { Stage, StageState } from "@/lib/types";

import { useRun } from "./RunContext";

const STATE_TEXT: Record<StageState, string> = {
  waiting: "chưa tới",
  running: "đang chạy",
  passed: "đạt",
  failed: "lỗi",
  human: "chờ bạn",
};

function StageIcon({ state }: { state: StageState }) {
  if (state === "running") return <span className="spinner" aria-hidden />;
  const glyph = { waiting: "", passed: "✓", failed: "✗", human: "!" }[state];
  return <span aria-hidden>{glyph}</span>;
}

function StageItem({ stage, afterPassed }: { stage: Stage; afterPassed: boolean }) {
  const title = `${stage.code} ${stage.label}: ${STATE_TEXT[stage.state]}${stage.detail ? ` — ${stage.detail}` : ""}`;
  return (
    <li
      className={afterPassed ? "stage after-passed" : "stage"}
      data-kind={stage.kind}
      data-state={stage.state}
      title={title}
      aria-current={stage.state === "running" || stage.state === "human" ? "step" : undefined}
    >
      <span className="stage-dot">
        {/* key theo trạng thái: hiệu ứng chỉ chạy khi nút đổi trạng thái */}
        <span className="stage-icon" key={stage.state}>
          <StageIcon state={stage.state} />
        </span>
      </span>
      <span className="stage-code">{stage.code}</span>
      <span className="stage-label">{stage.label}</span>
      <span className="sr-only">{STATE_TEXT[stage.state]}</span>
    </li>
  );
}

/** Đường ống E/V/J theo luồng thật; trạng thái từng nút do máy chủ suy từ dữ liệu thật. */
export function PipelineTrack() {
  const { detail } = useRun();
  const stages = detail?.stages ?? [];
  if (stages.length === 0) return null;
  return (
    <section className="pipeline" aria-label="Đường ống tiến trình">
      <ol className="pipeline-track">
        {stages.map((stage, index) => (
          <StageItem key={stage.id} stage={stage} afterPassed={index > 0 && stages[index - 1].state === "passed"} />
        ))}
      </ol>
      <div className="pipeline-legend">
        <span title="E: agent thực thi (gọi LLM)">
          <i className="e" />
          Agent
        </span>
        <span title="V: code kiểm chứng, 0 token">
          <i className="v" />
          Code kiểm
        </span>
        <span title="J: con người quyết định">
          <i className="j" />
          Bạn
        </span>
      </div>
    </section>
  );
}
