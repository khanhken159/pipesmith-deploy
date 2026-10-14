import styles from "./landing.module.css";

const agents = [
  {
    number: "E1",
    name: "Planner",
    description: "Đọc yêu cầu và danh mục nguồn để lập đặc tả; hỏi lại khi còn điểm chưa rõ.",
    tone: "blue",
  },
  {
    number: "E3",
    name: "Codegen",
    description: "Tạo model dbt và DAG Airflow dựa trên đặc tả đã được bạn duyệt.",
    tone: "violet",
  },
  {
    number: "E3b",
    name: "Testgen",
    description: "Tự tính kết quả kỳ vọng từ đặc tả và dữ liệu nguồn, độc lập với codegen.",
    tone: "green",
  },
  {
    number: "E4",
    name: "Optimizer",
    description: "Tìm cách tối ưu truy vấn; đề xuất chỉ được dùng sau khi qua bước đối chiếu.",
    tone: "amber",
  },
] as const;

export function AgentsSection() {
  return (
    <section className={styles.agentsSection} id="vai-tro-agent" aria-labelledby="agents-title">
      <div className={styles.container}>
        <p className={styles.sectionEyebrow}>CÁC VAI TRÒ AI</p>
        <h2 className={styles.sectionTitle} id="agents-title">
          Mỗi Agent đảm nhận một phần việc
        </h2>
        <p className={styles.sectionNote}>
          Các Agent hỗ trợ lập kế hoạch, tạo code, kiểm thử và tối ưu — theo những vai trò riêng biệt.
        </p>
        <div className={styles.agentGrid}>
          {agents.map((agent) => (
            <article className={styles.agentCard} key={agent.number}>
              <span className={`${styles.agentCode} ${styles[agent.tone]}`}>{agent.number}</span>
              <h3 className={styles.agentTitle}>{agent.name}</h3>
              <p className={styles.agentDescription}>{agent.description}</p>
            </article>
          ))}
        </div>
        <p className={styles.agentFootnote}>
          Safety và Sandbox là các lớp kiểm tra tự động, không phải AI Agent.
        </p>
      </div>
    </section>
  );
}
