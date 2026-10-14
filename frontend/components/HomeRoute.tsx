"use client";

import type { ReactNode } from "react";

import { useApp } from "@/components/AppContext";
import { AdminHome, EngineerHome, ReviewerHome } from "@/components/home/Dashboard";

export function HomeRoute({ landingPage }: { landingPage: ReactNode }) {
  const { auth, user } = useApp();
  if (auth !== "in" || !user) return landingPage;
  if (user.role === "reviewer") return <ReviewerHome />;
  if (user.role === "admin") return <AdminHome />;
  return <EngineerHome />;
}
