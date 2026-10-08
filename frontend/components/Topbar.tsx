"use client";

import { useState, type FormEvent } from "react";

import type { Role } from "@/lib/types";

import { useApp, type ThemeChoice } from "./AppContext";
import { MonitorIcon, MoonIcon, SunIcon } from "./icons";
import { useDismiss } from "./NotificationBell";

const THEME_LABELS: Record<ThemeChoice, string> = { system: "Theo máy", light: "Sáng", dark: "Tối" };
const THEME_ORDER: ThemeChoice[] = ["system", "light", "dark"];
const THEME_ICONS = { system: MonitorIcon, light: SunIcon, dark: MoonIcon };
const NAME_PATTERN = /^[A-Za-z0-9._-]{1,32}$/;

export function ModeBadges() {
  const { status, statusError } = useApp();
  if (statusError) return <span className="badge danger">Mất kết nối API</span>;
  if (!status) return <span className="badge muted">Đang kiểm tra API…</span>;
  return status.simulated ? (
    <span className="badge warn" title="LLM_PROVIDER=mock: câu trả lời LLM là cố định, không phải chất lượng thật">
      Mô phỏng
    </span>
  ) : (
    <span className="badge ok" title={status.models}>
      LLM thật · {status.llm_provider}
    </span>
  );
}

function UserForm() {
  const { user, setUser, status } = useApp();
  const [name, setName] = useState<string | null>(null);
  const separate = status?.require_separate_reviewer ?? false;
  const draft = name ?? user.name;
  const valid = NAME_PATTERN.test(draft);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid) setUser({ ...user, name: draft });
    setName(null);
  }

  return (
    <form className="stack" style={{ gap: 8 }} onSubmit={submit}>
      <label htmlFor="user-name" className="small muted">
        Tên người dùng
      </label>
      <input
        id="user-name"
        value={draft}
        onChange={(e) => setName(e.target.value)}
        onBlur={submit}
        aria-invalid={!valid}
        title="Chữ không dấu, số, . _ - (tối đa 32 ký tự)"
      />
      {separate && (
        <select
          aria-label="Vai trò"
          value={user.role === "de" ? "engineer" : user.role}
          onChange={(e) => setUser({ ...user, role: e.target.value as Role })}
        >
          <option value="engineer">Engineer</option>
          <option value="reviewer">Reviewer</option>
        </select>
      )}
    </form>
  );
}

/** Avatar tròn (chữ cái đầu): bấm mở menu người dùng + giao diện + chế độ LLM. */
export function AvatarMenu() {
  const { user, theme, setTheme } = useApp();
  const [open, setOpen] = useState(false);
  const box = useDismiss(open, () => setOpen(false));
  const initials = user.name.slice(0, 2).toUpperCase();
  return (
    <div className="popover" ref={box}>
      <button
        type="button"
        className="avatar"
        aria-label={`Người dùng ${user.name}: mở menu`}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {initials}
      </button>
      {open && (
        <div className="flyout menu" role="dialog" aria-label="Người dùng và giao diện">
          <UserForm />
          <div className="segmented" role="group" aria-label="Giao diện">
            {THEME_ORDER.map((value) => (
              <button key={value} type="button" aria-pressed={theme === value} onClick={() => setTheme(value)}>
                {THEME_LABELS[value]}
              </button>
            ))}
          </div>
          <ModeBadges />
        </div>
      )}
    </div>
  );
}

/** Một nút đổi giao diện: Theo máy → Sáng → Tối (thanh dọc). */
export function ThemeButton() {
  const { theme, setTheme } = useApp();
  const next = THEME_ORDER[(THEME_ORDER.indexOf(theme) + 1) % THEME_ORDER.length];
  const Glyph = THEME_ICONS[theme];
  return (
    <button
      type="button"
      className="rail-btn"
      onClick={() => setTheme(next)}
      aria-label={`Giao diện: ${THEME_LABELS[theme]}. Bấm để chuyển sang ${THEME_LABELS[next]}`}
      data-tip={`Giao diện: ${THEME_LABELS[theme]}`}
    >
      <Glyph size={18} />
    </button>
  );
}
