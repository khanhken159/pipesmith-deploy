import type { ReactNode } from "react";

import { RunProvider } from "@/components/run/RunContext";
import { RunHeader } from "@/components/run/RunHeader";

export default async function RunLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <RunProvider runId={id}>
      <RunHeader />
      {children}
    </RunProvider>
  );
}
