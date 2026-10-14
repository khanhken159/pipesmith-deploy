import styles from "./landing.module.css";

const steps = [
  {
    number: "01",
    title: "Mô tả yêu cầu",
    detail: "Chọn nguồn dữ liệu, nêu chỉ số, cách nhóm và bộ lọc. Nếu thiếu thông tin, Planner sẽ hỏi lại.",
    approval: false,
  },
  {
    number: "02",
    title: "Duyệt kế hoạch",
    detail: "Xem nguồn, cột, cách tính và giả định. Bạn duyệt hoặc yêu cầu Planner chỉnh trước khi tạo code.",
    approval: true,
  },
  {
    number: "03",
    title: "Tạo và kiểm thử",
    detail: "Codegen tạo dbt và DAG; Testgen tính kết quả độc lập. Safety và Sandbox rà soát, chạy thử rồi chuyển lỗi về sửa.",
    approval: false,
  },
  {
    number: "04",
    title: "Duyệt kết quả",
    detail: "Xem SQL, kết quả mẫu và kiểm tra. Chấp nhận để hoàn tất hoặc từ chối kèm ghi chú chỉnh sửa.",
    approval: true,
  },
];

export function StepsSection() {
  return (
    <section className={styles.stepsSection} id="cach-hoat-dong" aria-labelledby="steps-title">
      <div className={styles.container}>
        <h2 className={styles.sectionTitle} id="steps-title">
          Bốn bước, hai lần bạn quyết định
        </h2>
        <ol className={styles.stepsGrid}>
          {steps.map((step) => (
            <li className={`${styles.stepCard} ${step.approval ? styles.approvalCard : ""}`} key={step.number}>
              <div className={styles.stepHeading}>
                <span className={styles.stepNumber}>{step.number}</span>
                {step.approval && <span className={styles.approvalBadge}>Bạn duyệt</span>}
              </div>
              <h3 className={styles.cardTitle}>{step.title}</h3>
              <p className={styles.stepDetail}>{step.detail}</p>
            </li>
          ))}
        </ol>
        <p className={styles.agentSequence}>Planner → Codegen → Testgen → Safety + Sandbox → Optimizer</p>
      </div>
    </section>
  );
}
