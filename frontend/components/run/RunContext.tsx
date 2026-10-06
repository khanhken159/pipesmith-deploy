"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { apiPost, messageOf } from "@/lib/api";
import type { Accepted, RunDetail } from "@/lib/types";
import { usePoll } from "@/lib/usePoll";

interface RunState {
  runId: string;
  detail: RunDetail | null;
  error: string;
  loading: boolean;
  refresh: () => Promise<void>;
  /** Gửi thao tác (trả lời, duyệt, cứu hộ); trả về thông báo lỗi hoặc chuỗi rỗng. */
  act: (path: string, body: unknown) => Promise<string>;
}

const RunContext = createContext<RunState | null>(null);

export function RunProvider({ runId, children }: { runId: string; children: ReactNode }) {
  const [fast, setFast] = useState(true);
  const polled = usePoll<RunDetail>(`/runs/${runId}`, fast ? 2000 : 10000);
  const detail = polled.data;
  const active = !detail || detail.busy || detail.record.status === "running";
  if (detail && active !== fast) setFast(active);

  const { refresh } = polled;
  const act = useCallback(
    async (path: string, body: unknown) => {
      try {
        await apiPost<Accepted>(`/runs/${runId}${path}`, body);
        setFast(true);
        await refresh();
        return "";
      } catch (exc) {
        return messageOf(exc);
      }
    },
    [runId, refresh],
  );

  const value = useMemo<RunState>(
    () => ({ runId, detail, error: polled.error, loading: polled.loading, refresh, act }),
    [runId, detail, polled.error, polled.loading, refresh, act],
  );
  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRun(): RunState {
  const state = useContext(RunContext);
  if (!state) throw new Error("useRun phải nằm trong RunProvider");
  return state;
}
