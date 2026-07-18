import type { Metadata } from "next";

import { CaseWorkspace } from "@/features/cases/components/CaseWorkspace";

interface CasePageProps {
  params: Promise<{
    id: string;
  }>;
}

export const metadata: Metadata = {
  title: "Chi tiết hồ sơ | Digital Expert Agents",
};

export default async function CasePage({ params }: CasePageProps) {
  const { id } = await params;
  return <CaseWorkspace caseId={id} />;
}
