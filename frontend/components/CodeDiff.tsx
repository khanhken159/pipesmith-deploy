"use client";

import type { DiffOnMount, Monaco, OnMount } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef } from "react";

import { mono } from "@/lib/fonts";
import { languageOf } from "@/lib/format";
import { useMediaQuery } from "@/lib/useMediaQuery";

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
  fontFamily: mono.style.fontFamily,
  automaticLayout: true,
  wordWrap: "on" as const,
};

/** Dòng cần Reviewer chú ý (mục 9: điều kiện cứng theo giá trị), tô nền + chú thích khi rê chuột. */
export interface LineHighlight {
  line: number;
  message: string;
}

interface CodeDiffProps {
  path: string;
  original: string;
  modified: string;
  highlights?: LineHighlight[];
}

/** Tô sáng dòng trên bản code mới (bên phải). */
function useHighlights(highlights: LineHighlight[]) {
  const target = useRef<{ code: editor.ICodeEditor; monaco: Monaco } | null>(null);
  const collection = useRef<editor.IEditorDecorationsCollection | null>(null);
  const key = JSON.stringify(highlights);
  const apply = useCallback(() => {
    const current = target.current;
    if (!current) return;
    const items = (JSON.parse(key) as LineHighlight[]).filter((h) => h.line > 0);
    collection.current?.clear();
    collection.current = current.code.createDecorationsCollection(
      items.map((h) => ({
        range: new current.monaco.Range(h.line, 1, h.line, 1),
        options: {
          isWholeLine: true,
          className: "value-filter-line",
          linesDecorationsClassName: "value-filter-mark",
          hoverMessage: { value: h.message },
        },
      })),
    );
  }, [key]);
  useEffect(apply, [apply]);
  const onEditor: OnMount = (code, monaco) => {
    target.current = { code, monaco };
    apply();
  };
  const onDiff: DiffOnMount = (diff, monaco) => {
    target.current = { code: diff.getModifiedEditor(), monaco };
    apply();
  };
  return { onEditor, onDiff };
}

/** So sánh hai bản; không có bản trước (vòng duyệt đầu) thì hiện code mới ở chế độ chỉ đọc. */
export function CodeDiff({ path, original, modified, highlights = [] }: CodeDiffProps) {
  const { dark } = useApp();
  const { onEditor, onDiff } = useHighlights(highlights);
  const narrow = useMediaQuery("(max-width: 900px)"); // màn hẹp: xem một cột
  const common = { height: "56vh", language: languageOf(path), theme: dark ? "vs-dark" : "light", loading: loading() };
  return (
    <div className="diff-box" aria-label={`Code ${path}`}>
      {original ? (
        <DiffEditor
          {...common}
          original={original}
          modified={modified}
          options={{ ...OPTIONS, originalEditable: false, renderSideBySide: !narrow }}
          onMount={onDiff}
        />
      ) : (
        <Editor {...common} value={modified} options={OPTIONS} onMount={onEditor} />
      )}
    </div>
  );
}
