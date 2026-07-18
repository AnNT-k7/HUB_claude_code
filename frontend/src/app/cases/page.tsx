import type { Metadata } from "next";

import { CasesDashboard } from "@/features/cases/components/CasesDashboard";

export const metadata: Metadata = {
  title: "Hồ sơ tín dụng | Digital Expert Agents",
  description: "Quản lý và theo dõi hồ sơ thẩm định tín dụng doanh nghiệp.",
};

export default function CasesPage() {
  return <CasesDashboard />;
}
