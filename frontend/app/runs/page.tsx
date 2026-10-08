import { RunsTable } from "@/components/RunsTable";

export default function RunsPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Lần chạy</h1>
          <p>Mọi yêu cầu đã gửi: trạng thái, bảng đích, tối ưu, chi phí LLM. Lần chạy cần bạn xử lý được đánh dấu.</p>
        </div>
      </div>
      <RunsTable />
    </>
  );
}
