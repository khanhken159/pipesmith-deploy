import Link from "next/link";

import styles from "./landing.module.css";

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.footerInner}>
        <Link className={styles.footerBrand} href="#top" aria-label="PipeSmith, đầu trang">
          pipesmith<span className={styles.logoDot}>.</span>
        </Link>
        <span className={styles.footerDescription}>AI data pipeline workspace · P-113</span>
      </div>
    </footer>
  );
}
