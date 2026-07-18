"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { CaseCreationModal } from "@/features/cases/components/CaseCreationModal";
import { useCasesQuery } from "@/features/cases/hooks/useCasesQuery";
import { Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";
import { EmptyState } from "@/shared/components/ui/empty-state";
import { Skeleton } from "@/shared/components/ui/skeleton";
import type { CaseDetail, CaseSummary } from "@/shared/types/api";
import {
  caseStatusLabel,
  formatDateTime,
  formatMoney,
} from "@/shared/utils/formatters";
import { caseStatusTone } from "@/shared/utils/status";

function CaseCard({ caseData }: { caseData: CaseSummary }) {
  return (
    <Link
      href={`/cases/${encodeURIComponent(caseData.id)}`}
      className="group block rounded-2xl focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/20"
    >
      <Card className="h-full p-5 transition duration-200 group-hover:-translate-y-0.5 group-hover:border-primary/30 group-hover:shadow-lg sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-sm font-black text-primary">
            {caseData.company_name.slice(0, 2).toUpperCase()}
          </div>
          <Badge tone={caseStatusTone(caseData.status)} showDot>
            {caseStatusLabel(caseData.status)}
          </Badge>
        </div>
        <h2 className="mt-5 line-clamp-2 text-lg font-bold tracking-tight group-hover:text-primary">
          {caseData.company_name}
        </h2>
        <p className="mt-2 text-2xl font-black tracking-tight text-foreground">
          {formatMoney(caseData.requested_amount, caseData.currency)}
        </p>
        <div className="mt-5 flex items-center justify-between border-t border-border pt-4 text-xs text-muted-foreground">
          <span>{formatDateTime(caseData.created_at)}</span>
          <span className="font-bold text-primary transition group-hover:translate-x-0.5">
            Chi tiết →
          </span>
        </div>
      </Card>
    </Link>
  );
}

function DashboardSkeleton() {
  return (
    <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
      {[0, 1, 2, 3, 4, 5].map((item) => (
        <Card key={item} className="p-6">
          <div className="flex justify-between">
            <Skeleton className="h-11 w-11" />
            <Skeleton className="h-7 w-28 rounded-full" />
          </div>
          <Skeleton className="mt-5 h-6 w-3/4" />
          <Skeleton className="mt-3 h-8 w-2/3" />
          <Skeleton className="mt-7 h-4 w-full" />
        </Card>
      ))}
    </div>
  );
}

export function CasesDashboard() {
  const router = useRouter();
  const query = useCasesQuery();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [search, setSearch] = useState("");

  const filteredCases = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("vi");
    if (!term) return query.cases;
    return query.cases.filter(
      (caseData) =>
        caseData.company_name.toLocaleLowerCase("vi").includes(term) ||
        caseData.id.toLocaleLowerCase().includes(term),
    );
  }, [query.cases, search]);

  const handleCreated = (createdCase: CaseDetail) => {
    setIsCreateOpen(false);
    router.push(`/cases/${encodeURIComponent(createdCase.id)}`);
  };

  return (
    <main className="page-container py-8 sm:py-10">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Loan assessment workspace</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
            Hồ sơ tín dụng
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
            Theo dõi quá trình phân tích đa tác tử và giữ quyết định cuối cùng trong tay chuyên viên ngân hàng.
          </p>
        </div>
        <Button size="lg" onClick={() => setIsCreateOpen(true)}>
          <span aria-hidden="true">＋</span>
          Tạo hồ sơ mới
        </Button>
      </div>

      <div className="mt-8 flex flex-col gap-3 rounded-2xl border border-border bg-white p-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <label className="relative block flex-1">
          <span className="sr-only">Tìm hồ sơ</span>
          <span className="pointer-events-none absolute inset-y-0 left-4 flex items-center text-muted-foreground">
            ⌕
          </span>
          <input
            className="h-11 w-full rounded-xl border-0 bg-slate-50 pl-10 pr-4 text-sm outline-none ring-1 ring-inset ring-border transition placeholder:text-slate-400 focus:bg-white focus:ring-2 focus:ring-primary"
            value={search}
            placeholder="Tìm theo doanh nghiệp hoặc mã hồ sơ…"
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <p className="px-2 text-sm font-semibold text-muted-foreground">
          {query.cases.length} hồ sơ
        </p>
      </div>

      <section className="mt-6" aria-live="polite">
        {query.isLoading ? <DashboardSkeleton /> : null}
        {!query.isLoading && query.error ? (
          <Alert tone="danger" title="Không thể tải dữ liệu">
            <p>{query.error}</p>
            <Button className="mt-3" size="sm" variant="outline" onClick={query.refresh}>
              Thử lại
            </Button>
          </Alert>
        ) : null}
        {!query.isLoading && !query.error && query.cases.length === 0 ? (
          <EmptyState
            title="Chưa có hồ sơ tín dụng"
            description="Khởi tạo hồ sơ đầu tiên, tải tài liệu và để Orchestrator phân công các chuyên gia thẩm định."
            action={<Button onClick={() => setIsCreateOpen(true)}>Tạo hồ sơ</Button>}
          />
        ) : null}
        {!query.isLoading && !query.error && query.cases.length > 0 && filteredCases.length === 0 ? (
          <EmptyState
            compact
            title="Không tìm thấy hồ sơ"
            description="Thử thay đổi từ khóa tìm kiếm."
            action={<Button variant="outline" onClick={() => setSearch("")}>Xóa tìm kiếm</Button>}
          />
        ) : null}
        {!query.isLoading && !query.error && filteredCases.length > 0 ? (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {filteredCases.map((caseData) => (
              <CaseCard key={caseData.id} caseData={caseData} />
            ))}
          </div>
        ) : null}
      </section>

      <CaseCreationModal
        open={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onCreated={handleCreated}
      />
    </main>
  );
}
