"use client";

import { ResultCard } from "../ResultCard";
import { useRun } from "../RunContext";
import { FlowPanel, MetricsPanel, RuntimeConsole } from "./Panels";
import { ClarifyStep, PlanStep, RequestStep, TrackerStep } from "./Steps";
import { useRunAttention } from "./useRunAttention";

/** Màn tổng quan lần chạy theo bố cục Studio: 4 bước bên trái, chỉ số + sơ đồ + console bên phải. */
export function RunStudio() {
  const { detail } = useRun();
  useRunAttention(detail);
  if (!detail) return null;
  return (
    <div className="studio">
      <div className="studio-main">
        <RequestStep detail={detail} />
        <ClarifyStep detail={detail} />
        <PlanStep detail={detail} />
        <TrackerStep detail={detail} />
        {(detail.sandbox?.passed || (detail.code_notes ?? []).length > 0) && <ResultCard />}
      </div>
      <aside className="studio-side">
        <MetricsPanel detail={detail} />
        <FlowPanel detail={detail} />
        <RuntimeConsole detail={detail} />
      </aside>
    </div>
  );
}
