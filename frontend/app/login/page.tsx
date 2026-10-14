"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";

import { useApp } from "@/components/AppContext";
import { EyeIcon, EyeOffIcon } from "@/components/icons";
import { messageOf } from "@/lib/api";

// Đăng nhập bằng tài khoản doanh nghiệp cấp. KHÔNG có đăng ký tự do (CLAUDE.md mục 1–2).
// "Ghi nhớ" chỉ lưu TÊN đăng nhập trên máy này; mật khẩu không bao giờ lưu ở trình duyệt.
const REMEMBER_KEY = "p113.lastUser";

/** Chỉ quay lại đường dẫn nội bộ (chặn chuyển hướng ra trang ngoài qua ?next=). */
function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/login") ? next : "/";
}

function readRemembered(): string {
  try {
    return localStorage.getItem(REMEMBER_KEY) ?? "";
  } catch {
    return "";
  }
}

function remember(username: string | null): void {
  try {
    if (username) localStorage.setItem(REMEMBER_KEY, username);
    else localStorage.removeItem(REMEMBER_KEY);
  } catch {
    // trình duyệt chặn lưu trữ: bỏ qua
  }
}

function LoginForm() {
  const { auth, login } = useApp();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [keep, setKeep] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const first = setTimeout(() => {
      const saved = readRemembered();
      if (saved) {
        setUsername((typed) => typed || saved); // người dùng đã gõ trước thì giữ nguyên
        setKeep(true);
      }
    }, 0);
    return () => clearTimeout(first);
  }, []);

  // Đã đăng nhập (mở lại tab, bấm Back) → về trang đang cần
  useEffect(() => {
    if (auth === "in") router.replace(next);
  }, [auth, next, router]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (sending || !username.trim() || !password) return;
    setSending(true);
    setError("");
    try {
      await login(username.trim(), password);
      remember(keep ? username.trim().toLowerCase() : null);
      setPassword("");
      router.replace(next);
    } catch (exc) {
      setError(messageOf(exc));
      setSending(false);
    }
  }

  return (
    <div className="auth-form-wrap">
      <Link href="/" className="back-link">
        ← Về trang giới thiệu
      </Link>
      <div className="auth-card">
        <div className="eyebrow">
          <span className="eyebrow-dot" />
          BƯỚC TIẾP THEO / ĐĂNG NHẬP
        </div>
        <h1 id="login-title">
          Chào mừng
          <br />
          trở lại.
        </h1>
        <p className="subtitle">Đăng nhập để tiếp tục vào không gian làm việc PipeSmith.</p>

        <form className="auth-login-form" method="post" onSubmit={submit} aria-labelledby="login-title" noValidate>
          <label htmlFor="login-user" className="formlabel">
            Email hoặc tên đăng nhập
          </label>
          <input
            id="login-user"
            name="username"
            type="text"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="you@company.com"
            maxLength={64}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            aria-invalid={Boolean(error) || undefined}
            required
          />

          <label htmlFor="login-password" className="formlabel">
            Mật khẩu
          </label>
          <div className="password-field">
            <input
              id="login-password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Nhập mật khẩu"
              maxLength={256}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={Boolean(error) || undefined}
              required
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword((visible) => !visible)}
              aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              aria-pressed={showPassword}
            >
              {showPassword ? <EyeIcon size={18} /> : <EyeOffIcon size={18} />}
            </button>
          </div>

          <label className="auth-remember">
            <input type="checkbox" checked={keep} onChange={(event) => setKeep(event.target.checked)} />
            <span>Ghi nhớ tên đăng nhập</span>
          </label>

          {error && (
            <p className="login-error" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            className="btn btn-dark auth-submit"
            disabled={sending || !username.trim() || !password}
          >
            {sending ? "Đang đăng nhập…" : "Đăng nhập"}
            {!sending && <span className="arrow">↗</span>}
          </button>
        </form>

        <p className="form-help">
          Chưa có tài khoản? <strong>Liên hệ quản trị viên</strong> để được cấp.
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="marketingRoot">
      <main className="auth-page" aria-label="Đăng nhập PipeSmith">
        <div className="auth-side">
          <Link className="brand" href="/" aria-label="PipeSmith về trang giới thiệu">
            <span className="brandmark" aria-hidden="true">
              <span />
            </span>
            pipesmith.
          </Link>
          <div className="auth-content">
            <div className="auth-kicker">WELCOME TO YOUR DATA WORKSPACE</div>
            <h2>
              Biến dữ liệu
              <br />
              thành <em>giá trị.</em>
            </h2>
            <p>Tiếp tục vào workspace để khám phá quy trình kết hợp AI Agent với quyền kiểm soát của con người.</p>
          </div>
          <div className="auth-bottom">PIPE SMITH / AI DATA WORKFLOW</div>
        </div>
        <Suspense fallback={<div className="auth-form-wrap" aria-busy="true" />}>
          <LoginForm />
        </Suspense>
      </main>
    </div>
  );
}
