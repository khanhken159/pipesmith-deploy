"use client";

import { useState, type FormEvent } from "react";

import { useApp } from "@/components/AppContext";
import { RoleNote, ROLE_LABELS } from "@/components/Topbar";
import { Card, Checkbox, ErrorBox, Loading } from "@/components/ui";
import { apiPatch, apiPost, messageOf } from "@/lib/api";
import type { AdminUser, Role } from "@/lib/types";
import { usePoll } from "@/lib/usePoll";

// Quản lý tài khoản (chỉ Admin; backend kiểm từng API). Không có đăng ký tự do: Admin cấp tài khoản + mật khẩu tạm.
const ROLES: Role[] = ["engineer", "reviewer", "admin"];
const MIN_PASSWORD = 12;

/** Mật khẩu tạm ngẫu nhiên (crypto của trình duyệt), chỉ hiện cho Admin một lần để đưa riêng cho người dùng. */
function randomPassword(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(12));
  return btoa(String.fromCharCode(...bytes))
    .replace(/[+/=]/g, "")
    .slice(0, 16);
}

function formatTime(value: string | null): string {
  return value ? new Date(value).toLocaleString("vi-VN") : "Chưa đăng nhập";
}

function CreateUser({ onDone }: { onDone: () => Promise<void> }) {
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<Role>("engineer");
  const [password, setPassword] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSending(true);
    setError("");
    try {
      await apiPost("/admin/users", { username, display_name: displayName, role, password });
      setCreated(
        `Đã tạo ${username.toLowerCase()} (${ROLE_LABELS[role]}). Đưa mật khẩu tạm cho người dùng qua kênh riêng.`,
      );
      setUsername("");
      setDisplayName("");
      setPassword("");
      await onDone();
    } catch (exc) {
      setError(messageOf(exc));
    } finally {
      setSending(false);
    }
  }

  return (
    <Card title="Cấp tài khoản mới">
      <form className="admin-form" onSubmit={submit}>
        <label>
          <span>Tên đăng nhập</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="vd: nguyen.an"
            maxLength={32}
            autoComplete="off"
            required
          />
        </label>
        <label>
          <span>Tên hiển thị</span>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={80} />
        </label>
        <label>
          <span>Vai trò</span>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Mật khẩu tạm (≥ {MIN_PASSWORD} ký tự)</span>
          <div className="row" style={{ gap: 6 }}>
            <input
              className="mono"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
            <button type="button" className="btn small" onClick={() => setPassword(randomPassword())}>
              Tạo ngẫu nhiên
            </button>
          </div>
        </label>
        <div className="admin-form-actions">
          <button
            type="submit"
            className="btn primary"
            disabled={sending || !username.trim() || password.length < MIN_PASSWORD}
          >
            {sending ? "Đang tạo…" : "Tạo tài khoản"}
          </button>
        </div>
      </form>
      {error && <ErrorBox message={error} />}
      {created && <div className="alert ok">{created}</div>}
    </Card>
  );
}

function UserRow({ user, self, onDone }: { user: AdminUser; self: boolean; onDone: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [resetting, setResetting] = useState(false);
  const [password, setPassword] = useState("");

  async function update(body: Partial<{ role: Role; is_active: boolean; password: string }>) {
    setBusy(true);
    setError("");
    try {
      await apiPatch(`/admin/users/${user.id}`, body);
      setResetting(false);
      setPassword("");
      await onDone();
    } catch (exc) {
      setError(messageOf(exc));
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr data-inactive={!user.is_active || undefined}>
      <td>
        <strong>{user.display_name}</strong>
        <div className="muted small mono">@{user.username}</div>
      </td>
      <td>
        <select
          aria-label={`Vai trò của ${user.username}`}
          value={user.role}
          disabled={busy || self}
          onChange={(e) => update({ role: e.target.value as Role })}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r]}
            </option>
          ))}
        </select>
      </td>
      <td>
        <Checkbox checked={user.is_active} disabled={busy || self} onChange={(v) => update({ is_active: v })}>
          {user.is_active ? "Đang hoạt động" : "Đã khóa"}
        </Checkbox>
      </td>
      <td className="muted small">{formatTime(user.last_login_at)}</td>
      <td>
        {resetting ? (
          <div className="row" style={{ gap: 6 }}>
            <input
              className="mono"
              aria-label={`Mật khẩu mới cho ${user.username}`}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
            <button type="button" className="btn small" onClick={() => setPassword(randomPassword())}>
              Ngẫu nhiên
            </button>
            <button
              type="button"
              className="btn small primary"
              disabled={busy || password.length < MIN_PASSWORD}
              onClick={() => update({ password })}
            >
              Lưu
            </button>
          </div>
        ) : (
          <button type="button" className="btn small" onClick={() => setResetting(true)}>
            Đặt lại mật khẩu
          </button>
        )}
        {error && (
          <div className="small" style={{ color: "var(--fail)" }}>
            {error}
          </div>
        )}
      </td>
    </tr>
  );
}

export default function AdminPage() {
  const { user } = useApp();
  const isAdmin = user?.role === "admin";
  const { data, error, loading, refresh } = usePoll<AdminUser[]>(isAdmin ? "/admin/users" : null, null);
  if (!isAdmin) return <RoleNote need="admin" />;
  return (
    <div className="stack">
      <header className="page-head">
        <h1>Người dùng</h1>
        <p className="muted">
          Cấp, khóa tài khoản và đổi vai trò. Khóa, đổi vai trò hoặc đặt lại mật khẩu sẽ đăng xuất người đó ngay trên
          mọi thiết bị. Mọi thao tác được ghi vào nhật ký kiểm toán.
        </p>
      </header>
      <CreateUser onDone={refresh} />
      <Card title="Tài khoản">
        {loading && !data ? (
          <Loading text="Đang tải tài khoản…" />
        ) : !data ? (
          <ErrorBox message={error || "Không tải được danh sách."} onRetry={refresh} />
        ) : (
          <div className="table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Người dùng</th>
                  <th>Vai trò</th>
                  <th>Trạng thái</th>
                  <th>Đăng nhập gần nhất</th>
                  <th>Mật khẩu</th>
                </tr>
              </thead>
              <tbody>
                {data.map((u) => (
                  <UserRow key={u.id} user={u} self={u.id === user.id} onDone={refresh} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
