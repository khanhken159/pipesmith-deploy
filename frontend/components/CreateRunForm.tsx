"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { apiPost, messageOf } from "@/lib/api";
import type { Accepted } from "@/lib/types";

import { useHasRole } from "./AppContext";
import { ArrowRightIcon } from "./icons";
import { RoleNote } from "./Topbar";
import { ErrorBox } from "./ui";

// Nhãn ngắn trên nút gợi ý; bấm vào điền câu yêu cầu đầy đủ.
const EXAMPLES = [
  { label: "Doanh thu ngày, 3 nguồn", text: "Gộp đơn hàng 3 nguồn, tính doanh thu ngày" },
  { label: "Theo nguồn bán", text: "Doanh thu theo ngày và theo nguồn bán, chỉ tính đơn đã giao" },
  { label: "Giá trị đơn theo tháng", text: "Số đơn và giá trị trung bình mỗi đơn theo tháng" },
];

export function CreateRunForm() {
  const router = useRouter();
  const box = useRef<HTMLTextAreaElement>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const engineer = useHasRole("engineer");
  const tooShort = text.trim().length < 5;

  // "Bắt đầu ngay" / "Yêu cầu mới" trỏ tới #request: đưa con trỏ vào ô nhập
  useEffect(() => {
    const focus = () => {
      if (window.location.hash === "#request") box.current?.focus();
    };
    const first = setTimeout(focus, 0);
    window.addEventListener("hashchange", focus);
    return () => {
      clearTimeout(first);
      window.removeEventListener("hashchange", focus);
    };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (tooShort || sending || !engineer) return;
    setSending(true);
    setError("");
    try {
      const accepted = await apiPost<Accepted>("/runs", { request_text: text.trim() });
      router.push(`/runs/${accepted.run_id}`);
    } catch (exc) {
      setError(messageOf(exc));
      setSending(false);
    }
  }

  return (
    <form onSubmit={submit} className="request-form">
      <label htmlFor="request-text" className="sr-only">
        Yêu cầu pipeline
      </label>
      <textarea
        id="request-text"
        ref={box}
        rows={3}
        maxLength={4000}
        placeholder="Ví dụ: gộp đơn hàng 3 nguồn, tính doanh thu ngày"
        title="Ctrl + Enter để gửi. Agent chỉ chạy trong sandbox DuckDB."
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) void submit(e);
        }}
      />
      <div className="request-actions">
        <div className="chips" aria-label="Gợi ý">
          {EXAMPLES.map((example) => (
            <button
              key={example.label}
              type="button"
              className="chip"
              aria-pressed={text === example.text}
              title={example.text}
              onClick={() => setText(example.text)}
            >
              {example.label}
            </button>
          ))}
        </div>
        <button type="submit" className="btn dark pill-btn" disabled={tooShort || sending || !engineer}>
          {sending ? "Đang gửi…" : "Gửi"} <ArrowRightIcon size={15} />
        </button>
      </div>
      <RoleNote need="engineer" />
      {error && <ErrorBox message={error} />}
    </form>
  );
}
