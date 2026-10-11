"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Role } from "@/lib/types";

import { useApp, type ThemeChoice } from "./AppContext";
import { LogoutIcon, MonitorIcon, MoonIcon, SunIcon } from "./icons";
import { useDismiss } from "./NotificationBell";

const THEME_LABELS: Record<ThemeChoice, string> = { system: "Theo máy", light: "Sáng", dark: "Tối" };
const THEME_ORDER: ThemeChoice[] = ["system", "light", "dark"];
const THEME_ICONS = { system: MonitorIcon, light: SunIcon, dark: MoonIcon };
export const ROLE_LABELS: Record<Role, string> = { engineer: "Engineer", reviewer: "Reviewer", admin: "Admin" };

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

/** Avatar tròn (chữ cái đầu): bấm mở menu người dùng (vai trò, đăng xuất) + giao diện + chế độ LLM. */
export function AvatarMenu() {
  const { user, logout, theme, setTheme } = useApp();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const box = useDismiss(open, () => setOpen(false));
  if (!user) return null;
  const initials = user.name.slice(0, 2).toUpperCase();

  async function signOut() {
    setLeaving(true);
    await logout();
    router.replace("/login");
  }

  return (
    <div className="popover" ref={box}>
      <button
        type="button"
        className="avatar"
        aria-label={`${user.display_name} (${ROLE_LABELS[user.role]}): mở menu`}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {initials}
      </button>
      {open && (
        <div className="flyout menu" role="dialog" aria-label="Người dùng và giao diện">
          <div className="who">
            <strong>{user.display_name}</strong>
            <span className="muted small">@{user.name}</span>
            <span className={`badge role-${user.role}`}>{ROLE_LABELS[user.role]}</span>
          </div>
          <div className="segmented" role="group" aria-label="Giao diện">
            {THEME_ORDER.map((value) => (
              <button key={value} type="button" aria-pressed={theme === value} onClick={() => setTheme(value)}>
                {THEME_LABELS[value]}
              </button>
            ))}
          </div>
          <ModeBadges />
          <button type="button" className="btn logout-btn" onClick={signOut} disabled={leaving}>
            <LogoutIcon size={16} />
            {leaving ? "Đang đăng xuất…" : "Đăng xuất"}
          </button>
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

/** Nhắc khi bước này dành cho vai trò khác (nút tương ứng bị khóa; backend vẫn trả 403 nếu cố gọi). */
export function RoleNote({ need }: { need: Role }) {
  const { user } = useApp();
  if (!user || user.role === need) return null;
  return (
    <div className="alert info">
      <span>
        Bước này dành cho vai trò {ROLE_LABELS[need]}. Bạn đang đăng nhập với vai trò {ROLE_LABELS[user.role]}.
      </span>
    </div>
  );
}

/** Nhãn vai trò trên thanh trên cùng: màu theo vai trò để luôn biết mình đang đăng nhập với quyền gì. */
export function RoleChip() {
  const { user } = useApp();
  if (!user) return null;
  return (
    <span className={`role-chip role-${user.role}`} title={`Bạn đang đăng nhập với vai trò ${ROLE_LABELS[user.role]}`}>
      <span className="role-dot" aria-hidden />
      {ROLE_LABELS[user.role]}
    </span>
  );
}
