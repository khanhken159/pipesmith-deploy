import styles from "./landing.module.css";

const steps = [
  { number: "01", title: "Mô tả yêu cầu", detail: "Nói điều bạn cần.", approval: false },
  { number: "02", title: "Duyệt kế hoạch", detail: "Xem trước khi viết code.", approval: true },
  { number: "03", title: "Tạo và kiểm thử", detail: "Chạy thử trong sandbox, tự sửa nếu lỗi.", approval: false },
  { number: "04", title: "Duyệt kết quả", detail: "Chấp nhận để hoàn tất.", approval: true },
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
