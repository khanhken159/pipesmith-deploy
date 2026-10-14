import styles from "./landing.module.css";

const checks = [
  {
    number: "01",
    title: "Soát đặc tả",
    description: "Kiểm tra nguồn, grain và cột đầu ra trước khi bắt đầu tạo code.",
  },
  {
    number: "02",
    title: "Rà soát SQL",
    description: "Chặn câu lệnh rủi ro, rà bảng và cột theo danh mục, rồi kiểm tra truy vấn bằng DuckDB.",
  },
  {
    number: "03",
    title: "Chạy thử trong Sandbox",
    description: "Chạy dbt build trên DuckDB; nếu lỗi, hệ thống chuyển lại để sửa trong giới hạn lượt thử.",
  },
  {
    number: "04",
    title: "Đối chiếu trước khi tối ưu",
    description: "Chỉ áp dụng đề xuất khi kết quả tương đương và phép đo đạt ngưỡng; nếu không, giữ bản gốc.",
  },
];

export function QualitySection() {
  return (
    <section className={styles.qualitySection} id="kiem-soat" aria-labelledby="quality-title">
      <div className={styles.container}>
        <div className={styles.qualityPanel}>
          <p className={styles.qualityEyebrow}>LỚP KIỂM TRA TỰ ĐỘNG</p>
          <h2 className={styles.qualityTitle} id="quality-title">
            Kiểm tra trước khi pipeline đến tay bạn
          </h2>
          <p className={styles.qualityIntro}>
            Hệ thống xác minh đặc tả, rà soát code và chạy thử; kết quả cuối cùng vẫn chờ bạn quyết định.
          </p>
          <ol className={styles.qualityGrid}>
            {checks.map((check) => (
              <li className={styles.qualityCard} key={check.number}>
                <span className={styles.qualityNumber}>{check.number}</span>
                <h3>{check.title}</h3>
                <p>{check.description}</p>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
