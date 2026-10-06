"use client";

import dynamic from "next/dynamic";

import { languageOf } from "@/lib/format";

import { useApp } from "./AppContext";
import { Loading } from "./ui";

// Monaco chỉ chạy trên trình duyệt; bản editor tải từ CDN jsDelivr (mặc định của @monaco-editor/react).
const loading = () => <Loading text="Đang tải trình xem code…" />;
const DiffEditor = dynamic(() => import("@monaco-editor/react").then((m) => m.DiffEditor), { ssr: false, loading });
const Editor = dynamic(() => import("@monaco-editor/react").then((m) => m.Editor), { ssr: false, loading });

const OPTIONS = {
  readOnly: true,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  fontSize: 13,
  automaticLayout: true,
  wordWrap: "on" as const,
};

interface CodeDiffProps {
  path: string;
  original: string;
  modified: string;
}

/** So sánh hai bản; không có bản trước (vòng duyệt đầu) thì hiện code mới ở chế độ chỉ đọc. */
export function CodeDiff({ path, original, modified }: CodeDiffProps) {
  const { dark } = useApp();
  const common = { height: "56vh", language: languageOf(path), theme: dark ? "vs-dark" : "light", loading: loading() };
  return (
    <div className="diff-box" aria-label={`Code ${path}`}>
      {original ? (
        <DiffEditor
          {...common}
          original={original}
          modified={modified}
          options={{ ...OPTIONS, originalEditable: false, renderSideBySide: true }}
        />
      ) : (
        <Editor {...common} value={modified} options={OPTIONS} />
      )}
    </div>
  );
}
