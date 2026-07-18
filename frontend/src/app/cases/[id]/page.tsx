import type { Metadata } from "next";

import { CaseWorkspace } from "@/features/cases/components/CaseWorkspace";

interface CasePageProps {
  params: {
    id: string;
  };
}

export const metadata: Metadata = {
  title: "Chi tiết hồ sơ | Digital Expert Agents",
};

export default function CasePage({ params }: CasePageProps) {
  return <CaseWorkspace caseId={params.id} />;
}
