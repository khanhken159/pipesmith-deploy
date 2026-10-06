import Link from "next/link";

export default function NotFound() {
  return (
    <div className="alert info" role="status">
      <span>Không tìm thấy trang này.</span>
      <Link href="/" className="btn small">
        Về danh sách lần chạy
      </Link>
    </div>
  );
}
