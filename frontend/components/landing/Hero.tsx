import Link from "next/link";

import styles from "./landing.module.css";

export function Hero() {
  return (
    <section className={styles.hero} id="top" aria-labelledby="landing-title">
      <div className={styles.container}>
        <div className={styles.heroGrid}>
          <div className={styles.heroCopy}>
            <h1 className={styles.heroTitle} id="landing-title">
              Mô tả báo cáo bạn cần. Nhận SQL đã kiểm thử.
            </h1>
            <p className={styles.heroSubtitle}>Bạn duyệt kế hoạch trước, duyệt kết quả sau.</p>
            <div className={styles.heroActions}>
              <Link className={styles.primaryButton} href="/login">
                Dùng thử
              </Link>
              <Link className={styles.secondaryButton} href="#vi-du">
                Xem ví dụ
              </Link>
            </div>
          </div>

          <aside className={styles.heroExample} aria-label="Ví dụ yêu cầu đang chờ duyệt kế hoạch">
            <p className={styles.heroPrompt}>Tạo báo cáo doanh thu theo ngày từ dữ liệu đơn hàng.</p>
            <div className={styles.heroExampleMeta}>
              <span className={styles.approvalBadge}>Chờ bạn duyệt kế hoạch</span>
              <span className={styles.caption}>Minh họa</span>
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}
