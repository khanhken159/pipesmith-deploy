"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType, ReactNode, SVGProps } from "react";

import { API_URL } from "@/lib/api";

import { useApp } from "./AppContext";
import { BookIcon, DatabaseIcon, DocIcon, HomeIcon, ListIcon, PlusIcon, SparkIcon } from "./icons";
import { NotificationBell } from "./NotificationBell";
import { RunSearch } from "./RunSearch";
import { AvatarMenu, ModeBadges, ThemeButton } from "./Topbar";

// Bố cục theo mẫu: thanh trên (logo · tab · tìm · chuông · avatar), thanh thao tác nhanh dọc, thẻ kính trên bầu trời.
type IconType = ComponentType<SVGProps<SVGSVGElement> & { size?: number }>;
const NAV: { href: string; label: string; icon: IconType }[] = [
  { href: "/", label: "Trang chủ", icon: HomeIcon },
  { href: "/runs", label: "Lần chạy", icon: ListIcon },
  { href: "/catalog", label: "Dữ liệu nguồn", icon: DatabaseIcon },
  { href: "/errors", label: "Sổ lỗi", icon: BookIcon },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

function TopBar() {
  const pathname = usePathname();
  return (
    <header className="topbar">
      <Link href="/" className="brand">
        <SparkIcon size={22} className="brand-spark" />
        <span>P-113 Agent Studio</span>
      </Link>
      <nav className="nav-pills" aria-label="Điều hướng chính">
        {NAV.map(({ href, label, icon: Glyph }) => (
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
        <NotificationBell />
        <AvatarMenu />
      </div>
    </header>
  );
}

function Rail() {
  const pathname = usePathname();
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
      <Link href="/#request" className="rail-btn" aria-label="Yêu cầu mới" data-tip="Yêu cầu mới">
        <PlusIcon size={18} />
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

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="page">
      <div className="sky" aria-hidden>
        <span className="sky-glow" />
        <span className="sky-orb" />
      </div>
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
