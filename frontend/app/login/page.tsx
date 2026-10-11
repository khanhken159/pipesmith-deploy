"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";

import { useApp } from "@/components/AppContext";
import { EyeIcon, EyeOffIcon, SparkIcon, UserIcon } from "@/components/icons";
import { Checkbox } from "@/components/ui";
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

/** Phong cảnh đồng cỏ vẽ bằng SVG (màu lấy từ tokens.css, tự đổi theo sáng/tối). */
function Meadow() {
  return (
    <div className="meadow" aria-hidden>
      <span className="meadow-sun" />
      <svg viewBox="0 0 1440 900" preserveAspectRatio="xMidYMax slice">
        <path
          className="hill-far"
          d="M0 470 C 220 400 380 430 560 455 S 900 380 1100 410 S 1350 450 1440 430 V900 H0Z"
        />
        <path
          className="hill-mid"
          d="M0 560 C 200 500 420 520 640 560 S 1000 600 1200 540 S 1400 520 1440 530 V900 H0Z"
        />
        <g className="hill-trees">
          <circle cx="1130" cy="520" r="34" />
          <circle cx="1175" cy="508" r="44" />
          <circle cx="1225" cy="515" r="38" />
          <circle cx="1270" cy="526" r="30" />
          <circle cx="1310" cy="520" r="40" />
          <circle cx="1360" cy="528" r="34" />
          <circle cx="1405" cy="518" r="42" />
          <circle cx="1440" cy="526" r="32" />
          <circle cx="96" cy="548" r="26" />
          <circle cx="132" cy="540" r="32" />
          <circle cx="168" cy="550" r="24" />
        </g>
        <path className="hill-near" d="M0 650 C 260 590 520 610 760 660 S 1180 720 1440 640 V900 H0Z" />
        <path className="hill-front" d="M0 770 C 300 720 620 740 900 790 S 1300 820 1440 780 V900 H0Z" />
        <g className="grass">
          <path d="M60 900 Q 70 840 52 800 M90 900 Q 96 850 120 812 M130 900 Q 128 860 108 830" />
          <path d="M1250 900 Q 1262 846 1240 804 M1290 900 Q 1296 852 1322 816 M1330 900 Q 1326 864 1306 834" />
          <path d="M1380 900 Q 1388 850 1372 812 M1410 900 Q 1418 858 1440 828" />
        </g>
      </svg>
    </div>
  );
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
    // method="post": nếu bấm trước khi trang sẵn sàng (chưa hydrate), mật khẩu không bao giờ lọt lên URL
    <form className="login-card" method="post" onSubmit={submit} aria-labelledby="login-title" noValidate>
      <div className="login-brand">
        <SparkIcon size={18} />
        <span>P-113 Agent Studio</span>
      </div>
      <h1 id="login-title">Đăng nhập</h1>
      <p className="login-sub">Chào mừng trở lại, hãy đăng nhập bằng tài khoản doanh nghiệp được cấp.</p>

      <div className="login-field">
        <label htmlFor="login-user" className="sr-only">
          Tên đăng nhập
        </label>
        <input
          id="login-user"
          name="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          placeholder="Tên đăng nhập"
          maxLength={64}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          aria-invalid={Boolean(error) || undefined}
          required
        />
        <span className="login-field-icon" aria-hidden>
          <UserIcon size={20} />
        </span>
      </div>

      <div className="login-field">
        <label htmlFor="login-password" className="sr-only">
          Mật khẩu
        </label>
        <input
          id="login-password"
          name="password"
          type={showPassword ? "text" : "password"}
          autoComplete="current-password"
          placeholder="Mật khẩu"
          maxLength={256}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={Boolean(error) || undefined}
          required
        />
        <button
          type="button"
          className="login-field-icon login-eye"
          onClick={() => setShowPassword(!showPassword)}
          aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
          aria-pressed={showPassword}
        >
          {showPassword ? <EyeIcon size={20} /> : <EyeOffIcon size={20} />}
        </button>
      </div>

      <Checkbox checked={keep} onChange={setKeep}>
        Ghi nhớ tên đăng nhập
      </Checkbox>

      {error && (
        <p className="login-error" role="alert">
          {error}
        </p>
      )}

      <button type="submit" className="login-btn" disabled={sending || !username.trim() || !password}>
        {sending ? "Đang đăng nhập…" : "Đăng nhập"}
      </button>

      <p className="login-foot">
        Chưa có tài khoản? <strong>Liên hệ quản trị viên</strong> để được cấp.
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="login-page">
      <Meadow />
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
