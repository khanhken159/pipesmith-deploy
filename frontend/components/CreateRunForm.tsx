"use client";

import { useRouter } from "next/navigation";
import { ArrowUpRight, LoaderCircle, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { apiPost, messageOf } from "@/lib/api";
import type { Accepted } from "@/lib/types";
import { ErrorBox } from "./ui";

const EXAMPLES = [
  "Gộp đơn hàng 3 nguồn, tính doanh thu ngày",
  "Doanh thu theo ngày và theo nguồn bán, chỉ tính đơn đã giao",
  "Số đơn và giá trị trung bình mỗi đơn theo tháng",
];

export function CreateRunForm() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const tooShort = text.trim().length < 5;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (tooShort || sending) return;
    setSending(true);
    setError("");
    try {
      const accepted = await apiPost<Accepted>("/runs", { request_text: text.trim() });
      router.push("/runs/" + accepted.run_id);
    } catch (exc) {
      setError(messageOf(exc));
      setSending(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <label htmlFor="request" className="sr-only">
        Yêu cầu pipeline
      </label>
      <textarea
        id="request"
        rows={3}
        maxLength={4000}
        className="dashboard-request-textarea min-h-28 w-full resize-y rounded-xl border border-input bg-background px-4 py-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
        placeholder="Ví dụ: Từ shopee_orders và tiki_orders, tính doanh thu theo ngày và nguồn bán…"
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) void submit(event);
        }}
      />
      <div className="flex flex-col-reverse gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2" aria-label="Yêu cầu mẫu">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className="rounded-full border border-dashed border-border bg-background px-3 py-1.5 text-left text-xs text-muted-foreground transition hover:border-primary hover:text-primary"
              onClick={() => setText(example)}
            >
              {example}
            </button>
          ))}
        </div>
        <Button type="submit" disabled={tooShort || sending} className="shrink-0 self-end sm:self-auto">
          {sending ? <LoaderCircle className="animate-spin" /> : <Sparkles />}
          {sending ? "Đang tạo…" : "Tạo pipeline"}
          {!sending && <ArrowUpRight />}
        </Button>
      </div>
      <p className="m-0 flex items-center gap-2 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 font-medium text-foreground">
          <Sparkles className="size-3" /> Ctrl + Enter
        </span>
        Chỉ chạy trong sandbox DuckDB, không ghi vào production.
      </p>
      {error && <ErrorBox message={error} />}
    </form>
  );
}
