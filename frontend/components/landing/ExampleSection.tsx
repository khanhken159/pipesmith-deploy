import styles from "./landing.module.css";

export function ExampleSection() {
  return (
    <section className={styles.exampleSection} id="vi-du" aria-labelledby="example-title">
      <div className={styles.container}>
        <h2 className={styles.sectionTitle} id="example-title">
          Từ yêu cầu đến SQL có kiểm tra
        </h2>
        <p className={styles.sectionNote}>Ví dụ minh họa, không phải kết quả chạy thật.</p>

        <div className={styles.exampleGrid}>
          <article className={styles.exampleCard} aria-labelledby="request-title">
            <h3 className={styles.cardTitle} id="request-title">
              1. Yêu cầu
            </h3>
            <p className={styles.requestText}>“Tạo báo cáo doanh thu theo ngày từ dữ liệu đơn hàng.”</p>
            <p className={styles.exampleCaption}>Planner sẽ cần xác định nguồn đơn hàng, cột ngày, cột tiền và cách tính doanh thu.</p>
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
                <dt>Ngày</dt>
                <dd className={styles.codeText}>order_date</dd>
              </div>
              <div className={styles.detailRow}>
                <dt>Tính</dt>
                <dd className={styles.codeText}>SUM(total_amount)</dd>
              </div>
              <div className={styles.detailRow}>
                <dt>Lọc</dt>
                <dd className={styles.codeText}>status = completed</dd>
              </div>
              <div className={styles.detailRow}>
                <dt>Gộp theo</dt>
                <dd>Ngày</dd>
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
              Tự kiểm tra khi chạy
            </p>
          </article>
        </div>

        <aside className={styles.inputGuide} aria-labelledby="input-guide-title">
          <div className={styles.inputGuideIntro}>
            <p className={styles.sectionEyebrow}>ĐẦU VÀO CẦN CHUẨN BỊ</p>
            <h3 id="input-guide-title">Muốn tạo báo cáo này, cần những gì?</h3>
            <p>Không cần viết SQL. Hãy mô tả dữ liệu và cách bạn muốn tính; phần chưa rõ có thể được Planner hỏi lại.</p>
          </div>
          <ul className={styles.inputList}>
            <li><span>01</span><div><strong>Nguồn đơn hàng</strong><p>Bảng hoặc file đã thêm vào workspace.</p></div></li>
            <li><span>02</span><div><strong>Ngày cần thống kê</strong><p>Ví dụ: ngày đặt hàng hay ngày thanh toán.</p></div></li>
            <li><span>03</span><div><strong>Định nghĩa doanh thu</strong><p>Cột tiền cần cộng và cách xử lý đơn hủy/hoàn.</p></div></li>
            <li><span>04</span><div><strong>Điều kiện báo cáo</strong><p>Trạng thái đơn, khoảng ngày hoặc kênh bán nếu cần lọc.</p></div></li>
          </ul>
          <p className={styles.inputGuideNote}>Tên bảng, cột và trạng thái trong ví dụ chỉ để minh họa. Planner sẽ đối chiếu với danh mục nguồn thực tế.</p>
        </aside>
      </div>
    </section>
  );
}
