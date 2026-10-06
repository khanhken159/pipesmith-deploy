"use client";

import { useState } from "react";

import type { RunFiles } from "@/lib/types";
import { usePoll } from "@/lib/usePoll";

import { CodeDiff } from "../CodeDiff";
import { Card, Empty, ErrorBox, Loading } from "../ui";
import { DecisionForm } from "./DecisionForm";
import { EvidencePanel } from "./EvidencePanel";
import { useRun } from "./RunContext";

interface FileGroup {
  title: string;
  paths: string[];
}

function groupFiles(files: RunFiles): FileGroup[] {
  const code = Object.keys(files.code_files).sort();
  return [
    { title: "Model dbt", paths: code.filter((p) => p.startsWith("models/")) },
    { title: "DAG Airflow", paths: code.filter((p) => p.startsWith("dags/")) },
    { title: "Khác", paths: code.filter((p) => !p.startsWith("models/") && !p.startsWith("dags/")) },
    { title: "Test (sinh mù code)", paths: Object.keys(files.test_files).sort() },
  ].filter((group) => group.paths.length > 0);
}

function FileList({ files, selected, onSelect }: { files: RunFiles; selected: string; onSelect: (p: string) => void }) {
  const hasPrevious = Object.keys(files.previous_files).length > 0;
  const current = { ...files.code_files, ...files.test_files };
  return (
    <nav className="file-list" aria-label="Các file sinh ra">
      {groupFiles(files).map((group) => (
        <div key={group.title}>
          <h3>{group.title}</h3>
          {group.paths.map((path) => (
            <button
              key={path}
              type="button"
              className={path === selected ? "file-btn active" : "file-btn"}
              onClick={() => onSelect(path)}
              aria-current={path === selected}
            >
              <span>{path.split("/").pop()}</span>
              {hasPrevious && files.previous_files[path] !== current[path] && (
                <span className="badge warn" title="Đổi so với vòng trước">
                  đổi
                </span>
              )}
            </button>
          ))}
        </div>
      ))}
    </nav>
  );
}

function DiffCard({ files }: { files: RunFiles }) {
  const all = { ...files.code_files, ...files.test_files };
  const paths = Object.keys(all);
  const [picked, setPicked] = useState("");
  const selected = paths.includes(picked)
    ? picked
    : (paths.find((p) => p.includes("/marts/") && p.endsWith(".sql")) ?? paths[0]);
  const hasPrevious = Object.keys(files.previous_files).length > 0;
  if (!selected) return <Empty>Agent chưa sinh code.</Empty>;
  return (
    <div className="review-layout">
      <FileList files={files} selected={selected} onSelect={setPicked} />
      <div className="stack" style={{ gap: 8 }}>
        <div className="row small muted">
          <span className="mono">{selected}</span>
          <span>·</span>
          <span>
            {hasPrevious ? "Trái: bản bạn từ chối ở vòng trước · Phải: bản mới" : "Vòng duyệt đầu: toàn bộ là code mới"}
          </span>
        </div>
        <CodeDiff path={selected} original={files.previous_files[selected] ?? ""} modified={all[selected]} />
      </div>
    </div>
  );
}

export function ReviewScreen() {
  const { runId, detail } = useRun();
  const version = detail?.record.updated_at ?? "";
  const files = usePoll<RunFiles>(detail ? `/runs/${runId}/files?v=${encodeURIComponent(version)}` : null, null);
  return (
    <>
      <Card title="Code sinh ra">
        {files.error && <ErrorBox message={files.error} onRetry={files.refresh} />}
        {!files.data && !files.error && <Loading text="Đang tải code…" />}
        {files.data && <DiffCard files={files.data} />}
      </Card>
      <div className="grid-2">
        <EvidencePanel />
        <div className="decision">
          <DecisionForm />
        </div>
      </div>
    </>
  );
}
