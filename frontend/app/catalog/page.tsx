import { CatalogScreen } from "@/components/catalog/CatalogScreen";

export default function SourcesCatalogPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dữ liệu nguồn</h1>
          <p>
            Kho raw của công ty bán lẻ giả lập P113 Retail: bảng nhóm theo hệ thống nguồn, kiểu cột, số dòng, % rỗng,
            trùng khóa, và khóa nối gợi ý kèm % dòng khớp — tất cả đo bằng code trên dữ liệu thật. Sau khi chạy, tab
            “Cấu trúc dữ liệu” của lần chạy cho thấy staging, mart, lineage và JOIN thật.
          </p>
        </div>
      </div>
      <CatalogScreen
        path="/catalog/sources"
        emptyText="Chưa có dữ liệu nguồn. Chạy `python -m src.cli seed` để tạo dữ liệu mẫu."
      />
    </>
  );
}
