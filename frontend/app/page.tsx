import type { Metadata } from "next";

import { HomeRoute } from "@/components/HomeRoute";
import { LandingPage } from "@/components/LandingPage";

export const metadata: Metadata = {
  title: "PipeSmith — AI Data Pipeline Workspace",
  description: "Mô tả báo cáo bạn cần. Nhận SQL đã kiểm thử. Bạn duyệt kế hoạch trước, duyệt kết quả sau.",
};

export default function HomePage() {
  return <HomeRoute landingPage={<LandingPage />} />;
}
