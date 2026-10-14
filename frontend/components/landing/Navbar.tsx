import Link from "next/link";

import styles from "./landing.module.css";

export function Navbar() {
  return (
    <header className={styles.header}>
      <div className={styles.headerInner}>
        <Link className={styles.brand} href="#top" aria-label="PipeSmith, đầu trang">
          <span className={styles.logoMark} aria-hidden="true"><span /></span>
          <span>pipesmith<span className={styles.logoDot}>.</span></span>
        </Link>
        <nav className={styles.nav} aria-label="Điều hướng chính">
          <Link className={styles.navLink} href="#vi-du">
            Ví dụ
          </Link>
          <Link className={styles.navLink} href="#vai-tro-agent">
            Các Agent
          </Link>
          <Link className={styles.navLink} href="#cach-hoat-dong">
            Cách hoạt động
          </Link>
          <Link className={styles.navLink} href="#kiem-soat">
            Kiểm soát
          </Link>
          <Link className={styles.navLink} href="/login">
            Đăng nhập
          </Link>
          <Link className={styles.navCta} href="/login">
            Dùng thử
          </Link>
        </nav>
      </div>
    </header>
  );
}
