import { ErrorBook } from "@/components/ErrorBook";

export default function ErrorsPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Sổ lỗi</h1>
          <p>
            Lỗi agent từng gặp khi chạy sandbox. Chỉ mục bạn duyệt mới được đưa vào gợi ý cho Codegen lần sau (tối đa 3
            mục, không tự áp dụng).
          </p>
        </div>
      </div>
      <ErrorBook />
    </>
  );
}
