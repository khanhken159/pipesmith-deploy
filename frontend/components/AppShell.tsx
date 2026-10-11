"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ComponentType, type ReactNode, type SVGProps } from "react";

import { API_URL } from "@/lib/api";

import { useApp } from "./AppContext";
import type { Role } from "@/lib/types";

import {
  BookIcon,
  CheckIcon,
  DatabaseIcon,
  DocIcon,
  HomeIcon,
  ListIcon,
  PlusIcon,
  SparkIcon,
  UsersIcon,
} from "./icons";
import { NotificationBell } from "./NotificationBell";
import { RunSearch } from "./RunSearch";
import { AvatarMenu, ModeBadges, RoleChip, ThemeButton } from "./Topbar";

// Bố cục theo mẫu: thanh trên (logo · tab · tìm · chuông · avatar), thanh thao tác nhanh dọc, thẻ kính trên bầu trời.
type IconType = ComponentType<SVGProps<SVGSVGElement> & { size?: number }>;
type NavItem = { href: string; label: string; icon: IconType };
const HOME: NavItem = { href: "/", label: "Trang chủ", icon: HomeIcon };
const RUNS: NavItem = { href: "/runs", label: "Lần chạy", icon: ListIcon };
const SOURCES: NavItem = { href: "/catalog", label: "Dữ liệu nguồn", icon: DatabaseIcon };
const ERRORS: NavItem = { href: "/errors", label: "Sổ lỗi", icon: BookIcon };
// Mỗi vai trò thấy trước việc của mình (ẩn mục chỉ để gọn; quyền thật kiểm ở backend).
const NAV: Record<Role, NavItem[]> = {
  engineer: [HOME, RUNS, SOURCES, ERRORS],
  reviewer: [{ ...HOME, label: "Hàng đợi" }, RUNS, ERRORS, SOURCES],
  admin: [HOME, { href: "/admin", label: "Người dùng", icon: UsersIcon }, RUNS, SOURCES],
};
// Nút nhanh thứ hai trên thanh dọc theo vai trò
const QUICK: Record<Role, NavItem> = {
  engineer: { href: "/#request", label: "Yêu cầu mới", icon: PlusIcon },
  reviewer: { href: "/#queue", label: "Hàng đợi duyệt", icon: CheckIcon },
  admin: { href: "/admin", label: "Cấp tài khoản", icon: UsersIcon },
};

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

function TopBar() {
  const pathname = usePathname();
  const { user } = useApp();
  const nav = NAV[user?.role ?? "engineer"];
  return (
    <header className="topbar">
      <Link href="/" className="brand">
        <SparkIcon size={22} className="brand-spark" />
        <span>P-113 Agent Studio</span>
      </Link>
      <nav className="nav-pills" aria-label="Điều hướng chính">
        {nav.map(({ href, label, icon: Glyph }) => (
          <Link
            key={href}
            href={href}
            className={isActive(pathname, href) ? "nav-pill active" : "nav-pill"}
            aria-current={isActive(pathname, href) ? "page" : undefined}
          >
            <Glyph size={16} />
            <span>{label}</span>
          </Link>
        ))}
      </nav>
      <div className="topbar-tools">
        <RunSearch />
        <RoleChip />
        <NotificationBell />
        <AvatarMenu />
      </div>
    </header>
  );
}

function Rail() {
  const pathname = usePathname();
  const { user } = useApp();
  const { href, label, icon: Quick } = QUICK[user?.role ?? "engineer"];
  return (
    <aside className="rail" aria-label="Thao tác nhanh">
      <Link
        href="/"
        className={pathname === "/" ? "rail-btn active" : "rail-btn"}
        aria-label="Trang chủ"
        data-tip="Trang chủ"
      >
        <HomeIcon size={18} />
      </Link>
      <Link href={href} className="rail-btn" aria-label={label} data-tip={label}>
        <Quick size={18} />
      </Link>
      <a
        href={`${API_URL}/docs`}
        target="_blank"
        rel="noreferrer"
        className="rail-btn"
        aria-label="Tài liệu API (mở tab mới)"
        data-tip="Tài liệu API"
      >
        <DocIcon size={18} />
      </a>
      <ThemeButton />
    </aside>
  );
}

function Footer() {
  const { status, statusError } = useApp();
  return (
    <footer className="footer">
      <span className="row">
        <span className={statusError ? "dot fail" : status ? "dot ok" : "dot"} aria-hidden />
        {statusError ? "Mất kết nối API" : status ? (status.agent ?? "API") : "Đang kiểm tra API…"}
      </span>
      <ModeBadges />
    </footer>
  );
}

/** Màn chờ khi đang kiểm phiên hoặc đang chuyển sang trang đăng nhập. */
function Splash({ text }: { text: string }) {
  return (
    <div className="splash" role="status" aria-live="polite">
      <SparkIcon size={28} className="brand-spark" />
      <span>{text}</span>
    </div>
  );
}

function Sky() {
  return (
    <div className="sky" aria-hidden>
      <span className="sky-glow" />
      <span className="sky-orb" />
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { auth, user } = useApp();
  const onLogin = pathname.startsWith("/login");

  // Mọi trang (trừ đăng nhập) cần phiên; hết phiên → về đăng nhập, quay lại đúng trang sau khi đăng nhập
  useEffect(() => {
    if (auth === "out" && !onLogin) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [auth, onLogin, pathname, router]);

  if (onLogin) return <>{children}</>;
  if (auth !== "in") {
    return (
      <div className="page">
        <Sky />
        <Splash text={auth === "checking" ? "Đang kiểm tra phiên đăng nhập…" : "Đang chuyển tới trang đăng nhập…"} />
      </div>
    );
  }
  return (
    <div className="page" data-role={user?.role}>
      <Sky />
      <a href="#main" className="skip-link">
        Bỏ qua tới nội dung
      </a>
      <div className="frame">
        <TopBar />
        <div className="body">
          <Rail />
          <main id="main" className="content">
            {children}
          </main>
        </div>
        <Footer />
      </div>
    </div>
  );
}
