import styles from "./landing.module.css";

export function ExampleSection() {
  return (
    <section className={styles.exampleSection} id="vi-du" aria-labelledby="example-title">
      <div className={styles.container}>
        <h2 className={styles.sectionTitle} id="example-title">
          Một câu thành SQL đã kiểm thử
        </h2>
        <p className={styles.sectionNote}>Ví dụ minh họa, không phải kết quả chạy thật.</p>

        <div className={styles.exampleGrid}>
          <article className={styles.exampleCard} aria-labelledby="request-title">
            <h3 className={styles.cardTitle} id="request-title">
              1. Yêu cầu
            </h3>
            <p className={styles.requestText}>“Tạo báo cáo doanh thu theo ngày từ dữ liệu đơn hàng.”</p>
          </article>

          <article className={styles.exampleCard} aria-labelledby="plan-title">
            <div className={styles.cardHeading}>
              <h3 className={styles.cardTitle} id="plan-title">
                2. Kế hoạch
              </h3>
              <span className={styles.approvalBadge}>Bạn duyệt</span>
            </div>
            <dl className={styles.planDetails}>
              <div className={styles.detailRow}>
                <dt>Bảng</dt>
                <dd className={styles.codeText}>orders</dd>
              </div>
              <div className={styles.detailRow}>
                <dt>Nhóm theo</dt>
                <dd>Ngày</dd>
              </div>
              <div className={styles.detailRow}>
                <dt>Lọc</dt>
                <dd>Đơn hoàn tất</dd>
              </div>
            </dl>
          </article>

          <article className={`${styles.exampleCard} ${styles.resultCard}`} aria-labelledby="result-title">
            <div className={styles.cardHeading}>
              <h3 className={styles.cardTitle} id="result-title">
                3. Kết quả
              </h3>
              <span className={styles.approvalBadge}>Bạn duyệt</span>
            </div>
            <div className={styles.codeViewport} tabIndex={0} aria-label="SQL minh họa, cuộn ngang để xem toàn bộ">
              <pre className={styles.sqlCode}>
                <code>
                  <span className={styles.sqlKeyword}>SELECT</span>
                  {"\n  "}
                  <span className={styles.sqlKeyword}>CAST</span>(order_date{" "}
                  <span className={styles.sqlKeyword}>AS</span> <span className={styles.sqlKeyword}>DATE</span>){" "}
                  <span className={styles.sqlKeyword}>AS</span> ngay,
                  {"\n  "}
                  <span className={styles.sqlKeyword}>SUM</span>(total_amount){" "}
                  <span className={styles.sqlKeyword}>AS</span> doanh_thu
                  {"\n"}
                  <span className={styles.sqlKeyword}>FROM</span> orders
                  {"\n"}
                  <span className={styles.sqlKeyword}>WHERE</span> status ={" "}
                  <span className={styles.sqlLiteral}>{"'completed'"}</span>
                  {"\n"}
                  <span className={styles.sqlKeyword}>GROUP BY</span> 1;
                </code>
              </pre>
            </div>
            <p className={styles.successNote}>
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="m5 12.5 4.5 4.5L19 7.5" />
              </svg>
              Kiểm thử đạt
            </p>
          </article>
        </div>
      </div>
    </section>
  );
}
