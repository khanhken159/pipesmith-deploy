"use client";

import { useEffect } from "react";

export default function ErrorPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="alert danger" role="alert">
      <span>Màn hình gặp lỗi không mong muốn. Dữ liệu lần chạy vẫn an toàn trên máy chủ.</span>
      <button type="button" className="btn small" onClick={() => retry()}>
        Thử lại
      </button>
    </div>
  );
}
