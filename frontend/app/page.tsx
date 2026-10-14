"use client";

import { useApp } from "@/components/AppContext";
import { LandingPage } from "@/components/LandingPage";
import { AdminHome, EngineerHome, ReviewerHome } from "@/components/home/Dashboard";

// Trang giới thiệu công khai; người đã đăng nhập vẫn đi thẳng tới workspace theo vai trò.
export default function HomePage() {
  const { auth, user } = useApp();
  if (auth !== "in" || !user) return <LandingPage />;
  if (user?.role === "reviewer") return <ReviewerHome />;
  if (user?.role === "admin") return <AdminHome />;
  return <EngineerHome />;
}
