"use client";

import { useState } from "react";

import { apiPost, messageOf } from "@/lib/api";
import type { ErrorEntry } from "@/lib/types";
import { usePoll } from "@/lib/usePoll";

import { Card, Empty, ErrorBox, Loading } from "./ui";

function EntryCard({ entry, onDone }: { entry: ErrorEntry; onDone: () => Promise<void> }) {
  const [fix, setFix] = useState(entry.fix);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function send(action: "approve" | "discard") {
    setSending(true);
    try {
      await apiPost(`/errors/${entry.id}/${action}`, action === "approve" ? { fix } : {});
      await onDone();
    } catch (exc) {
      setError(messageOf(exc));
      setSending(false);
    }
  }

  return (
    <Card
      title={<span className="mono">{entry.code}</span>}
      actions={<span className="badge muted">gặp {entry.occurrences} lần</span>}
    >
      <div className="stack" style={{ gap: 10 }}>
        <p>{entry.description}</p>
        {entry.cause && <p className="muted">Nguyên nhân: {entry.cause}</p>}
        {entry.sql_before && (
          <details>
            <summary>SQL lúc lỗi</summary>
            <pre>{entry.sql_before}</pre>
          </details>
        )}
        <label htmlFor={`fix-${entry.id}`}>Cách sửa (agent sẽ được gợi ý khi gặp lỗi giống vậy)</label>
        <textarea id={`fix-${entry.id}`} value={fix} onChange={(e) => setFix(e.target.value)} maxLength={2000} />
        {error && <ErrorBox message={error} />}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn danger" disabled={sending} onClick={() => send("discard")}>
            Bỏ
          </button>
          <button type="button" className="btn ok" disabled={sending || !fix.trim()} onClick={() => send("approve")}>
            Duyệt bài học
          </button>
        </div>
      </div>
    </Card>
  );
}

export function ErrorBook() {
  const { data, error, loading, refresh } = usePoll<ErrorEntry[]>("/errors", null);
  if (loading && !data) return <Loading text="Đang tải sổ lỗi…" />;
  if (!data) return <ErrorBox message={error || "Không tải được sổ lỗi."} onRetry={refresh} />;
  if (data.length === 0) return <Empty>Không có mục nào chờ duyệt.</Empty>;
  return (
    <div className="grid-2">
      {data.map((entry) => (
        <EntryCard key={entry.id} entry={entry} onDone={refresh} />
      ))}
    </div>
  );
}
