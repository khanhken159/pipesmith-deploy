import Link from "next/link";

import styles from "./landing.module.css";

export function CtaBand() {
  return (
    <section className={styles.ctaSection} aria-labelledby="cta-title">
      <div className={styles.container}>
        <div className={styles.ctaPanel}>
          <h2 className={styles.ctaTitle} id="cta-title">
            AI làm phần lặp lại. Bạn giữ quyền quyết định.
          </h2>
          <Link className={styles.ctaButton} href="/login">
            Dùng thử
          </Link>
        </div>
      </div>
    </section>
  );
}
