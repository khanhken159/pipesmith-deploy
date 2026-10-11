"use client";

import { useApp } from "@/components/AppContext";
import { AdminHome, EngineerHome, ReviewerHome } from "@/components/home/Dashboard";

// Trang chủ khác nhau theo vai trò: mỗi người thấy trước việc của mình.
export default function HomePage() {
  const { user } = useApp();
  if (user?.role === "reviewer") return <ReviewerHome />;
  if (user?.role === "admin") return <AdminHome />;
  return <EngineerHome />;
}
