"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";

import { useApp } from "@/components/AppContext";
import { EyeIcon, EyeOffIcon } from "@/components/icons";
import { messageOf } from "@/lib/api";
import { landingBody, landingDisplay, landingMono } from "@/lib/landing-fonts";

import styles from "./login.module.css";

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
    <section className={styles.formPane} aria-labelledby="login-title">
      <Link href="/" className={styles.backLink}>
        <span aria-hidden="true">←</span> Về trang giới thiệu
      </Link>
      <div className={styles.authCard}>
        <div className={styles.eyebrow}>
          <span className={styles.eyebrowDot} aria-hidden="true" />
          BƯỚC TIẾP THEO / ĐĂNG NHẬP
        </div>
        <h1 id="login-title">Chào mừng trở lại.</h1>
        <p className={styles.subtitle}>Đăng nhập để tiếp tục vào không gian làm việc PipeSmith.</p>

        <form className={styles.loginForm} method="post" onSubmit={submit} aria-labelledby="login-title" noValidate>
          <label htmlFor="login-user" className={styles.formLabel}>
            Email hoặc tên đăng nhập
          </label>
          <input
            className={styles.textInput}
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

          <label htmlFor="login-password" className={styles.formLabel}>
            Mật khẩu
          </label>
          <div className={styles.passwordField}>
            <input
              className={styles.textInput}
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
              className={styles.passwordToggle}
              onClick={() => setShowPassword((visible) => !visible)}
              aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              aria-pressed={showPassword}
            >
              {showPassword ? <EyeIcon size={18} /> : <EyeOffIcon size={18} />}
            </button>
          </div>

          <label className={styles.remember}>
            <input type="checkbox" checked={keep} onChange={(event) => setKeep(event.target.checked)} />
            <span>Ghi nhớ tên đăng nhập</span>
          </label>

          {error && (
            <p className={styles.loginError} role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            className={styles.submitButton}
            disabled={sending || !username.trim() || !password}
          >
            {sending ? "Đang đăng nhập…" : "Đăng nhập"}
            {!sending && <span aria-hidden="true">↗</span>}
          </button>
        </form>

        <p className={styles.formHelp}>
          Chưa có tài khoản? <strong>Liên hệ quản trị viên</strong> để được cấp.
        </p>
      </div>
      <p className={styles.secureNote}><span aria-hidden="true">✓</span> Không gian làm việc dành cho thành viên được cấp quyền</p>
    </section>
  );
}

export default function LoginPage() {
  return (
    <main className={`${styles.loginRoot} ${landingDisplay.variable} ${landingBody.variable} ${landingMono.variable}`} aria-label="Đăng nhập PipeSmith">
      <div className={styles.loginShell}>
        <section className={styles.showcase} aria-label="Không gian làm việc PipeSmith">
          <header className={styles.showcaseHeader}>
            <Link className={styles.brand} href="/" aria-label="PipeSmith về trang giới thiệu">
              <span className={styles.brandMark} aria-hidden="true"><span /></span>
              <span>pipe<span className={styles.brandAccent}>smith</span><span className={styles.brandDot}>.</span></span>
            </Link>
            <span className={styles.productTag}>AI DATA WORKSPACE</span>
          </header>

          <div className={styles.showcaseCopy}>
            <p className={styles.kicker}><span aria-hidden="true" /> PIPELINE CÓ AI, BẠN GIỮ QUYỀN KIỂM SOÁT</p>
            <h2>Biến dữ liệu<br />thành <em>giá trị.</em></h2>
            <p>Tiếp tục vào workspace để khám phá quy trình kết hợp AI Agent với quyền kiểm soát của con người.</p>
          </div>

          <div className={styles.workflowCard} aria-label="Minh họa các bước của pipeline">
            <div className={styles.workflowTop}>
              <span className={styles.windowDots} aria-hidden="true"><i /><i /><i /></span>
              <span>pipesmith / workspace</span>
              <span className={styles.liveBadge}><i /> WORKSPACE</span>
            </div>
            <div className={styles.workflowBody}>
              <div className={styles.workflowTitle}>
                <span className={styles.workflowIcon} aria-hidden="true">⌘</span>
                <div><small>YÊU CẦU DỮ LIỆU</small><strong>Pipeline rõ ràng, từ đầu đến cuối.</strong></div>
              </div>
              <div className={styles.stepsLabel}><span>QUY TRÌNH</span><span>6 giai đoạn chính</span></div>
              <div className={styles.stepGrid}>
                <div><i className={styles.stepBlue}>01</i><span>Planner</span></div>
                <div><i className={styles.stepAmber}>02</i><span>Duyệt kế hoạch</span></div>
                <div><i className={styles.stepViolet}>03</i><span>Codegen</span></div>
                <div><i className={styles.stepGreen}>04</i><span>Testgen</span></div>
                <div><i className={styles.stepSlate}>05</i><span>Safety + Sandbox</span></div>
                <div><i className={styles.stepBlue}>06</i><span>Optimizer</span></div>
              </div>
              <div className={styles.reviewNote}><span aria-hidden="true">✓</span> Bạn duyệt kế hoạch và kết quả trước khi hoàn tất</div>
            </div>
          </div>

          <footer className={styles.showcaseFooter}><span>AI-POWERED DATA PIPELINE WORKSPACE</span><span>P·113</span></footer>
        </section>

        <Suspense fallback={<section className={styles.formPane} aria-busy="true" aria-label="Đang tải biểu mẫu đăng nhập" />}>
          <LoginForm />
        </Suspense>
      </div>
    </main>
  );
}
